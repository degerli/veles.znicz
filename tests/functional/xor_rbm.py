#!/usr/bin/python3.3 -O
"""
Created on Mar 20, 2013

xor with rbm.

@author: Kazantsev Alexey <a.kazantsev@samsung.com>
"""
import logging
import sys
import os


def add_path(path):
    if path not in sys.path:
        sys.path.append(path)


this_dir = os.path.dirname(__file__)
if not this_dir:
    this_dir = "."
add_path("%s" % (this_dir))
add_path("%s/../.." % (this_dir))
add_path("%s/../../../src" % (this_dir))


import units
import numpy
import config
import rnd
import opencl
import plotters
import pickle
import time
import rbm
import mnist_ae
import loader
import decision


class Loader(loader.FullBatchLoader):
    """Loads xor dataset.
    """
    def load_data(self):
        """Here we will load data.
        """
        self.original_labels = numpy.array(
            [0, 1, 1, 0, 1, 0, 0, 1, 1, 1, 1], dtype=numpy.int8)
        self.original_data = numpy.array([
                [0, 0, 0],
                [0, 0, 1],
                [0, 1, 0],
                [0, 1, 1],
                [1, 0, 0],
                [1, 0, 1],
                [1, 1, 0],
                [1, 1, 1],
                [1, 0, 0],
                [0, 1, 0],
                [0, 0, 1]],
                dtype=config.dtypes[config.dtype])

        self.original_data[:] = numpy.where(self.original_data == 0, -1.0,
                                            1.0)[:]

        self.class_samples[0] = 0
        self.nextclass_offs[0] = 0
        self.class_samples[1] = 0
        self.nextclass_offs[1] = 0
        self.class_samples[2] = len(self.original_labels)
        self.nextclass_offs[2] = len(self.original_labels)

        self.total_samples[0] = len(self.original_labels)


import all2all
import evaluator
import gd


class Workflow(units.OpenCLUnit):
    """Sample workflow for MNIST dataset.

    Attributes:
        start_point: start point.
        rpt: repeater.
        loader: loader.
        forward: list of all-to-all forward units.
        ev: evaluator softmax.
        stat: stat collector.
        decision: Decision.
        gd: list of gradient descent units.
    """
    def __init__(self, layers=None, device=None):
        super(Workflow, self).__init__(device=device)
        self.start_point = units.Unit()

        self.rpt = units.Repeater()
        self.rpt.link_from(self.start_point)

        self.loader = Loader()
        self.loader.link_from(self.rpt)

        # Add forward units
        self.forward = []
        for i in range(0, len(layers)):
            if not i:
                amp = None
            else:
                amp = 9.0 / 1.7159 / layers[i - 1]
            if not i:
                aa = rbm.RBMTanh([layers[i]], device=device,
                             weights_amplitude=amp)
            else:
                aa = all2all.All2AllTanh([layers[i]], device=device,
                             weights_amplitude=amp,
                             weights_transposed=True)
                aa.weights = self.forward[0].weights
            self.forward.append(aa)
            if i:
                self.forward[i].link_from(self.forward[i - 1])
                self.forward[i].input = self.forward[i - 1].output
            else:
                self.forward[i].link_from(self.loader)
                self.forward[i].input = self.loader.minibatch_data

        # Add evaluator for single minibatch
        self.ev = evaluator.EvaluatorMSE(device=device)
        self.ev.link_from(self.forward[-1])
        self.ev.y = self.forward[-1].output
        self.ev.batch_size = self.loader.minibatch_size
        self.ev.target = self.loader.minibatch_data
        self.ev.max_samples_per_epoch = self.loader.total_samples

        # Add decision unit
        self.decision = decision.Decision(snapshot_prefix="xor_rbm",
                                          store_samples_mse=True,
                                          use_dynamic_alpha=True)
        self.decision.link_from(self.ev)
        self.decision.minibatch_class = self.loader.minibatch_class
        self.decision.minibatch_last = self.loader.minibatch_last
        self.decision.minibatch_n_err = self.ev.n_err_skipped
        self.decision.minibatch_metrics = self.ev.metrics
        self.decision.minibatch_mse = self.ev.mse
        self.decision.minibatch_offs = self.loader.minibatch_offs
        self.decision.minibatch_size = self.loader.minibatch_size
        self.decision.class_samples = self.loader.class_samples
        self.decision.workflow = self

        # Add Image Saver unit
        self.image_saver = mnist_ae.ImageSaverAE(["/tmp/img/test",
                                                  "/tmp/img/validation",
                                                  "/tmp/img/train"])
        self.image_saver.link_from(self.decision)
        self.image_saver.input = self.loader.minibatch_data
        self.image_saver.output = self.forward[-1].output
        self.image_saver.indexes = self.loader.minibatch_indexes
        self.image_saver.labels = self.loader.minibatch_labels
        self.image_saver.minibatch_class = self.loader.minibatch_class
        self.image_saver.minibatch_size = self.loader.minibatch_size
        self.image_saver.this_save_date = self.decision.snapshot_time
        self.image_saver.gate_skip = [0]  # self.decision.just_snapshotted
        self.image_saver.gate_skip_not = [1]

        # Add gradient descent units
        self.gd = list(None for i in range(0, len(self.forward)))
        self.gd[-1] = gd.GD(device=device, weights_transposed=True)
        # self.gd[-1].link_from(self.decision)
        self.gd[-1].err_y = self.ev.err_y
        self.gd[-1].y = self.forward[-1].output
        self.gd[-1].h = self.forward[-1].input
        self.gd[-1].weights = self.forward[-1].weights
        self.gd[-1].bias = self.forward[-1].bias
        self.gd[-1].gate_skip = self.decision.gd_skip
        self.gd[-1].batch_size = self.loader.minibatch_size
        for i in range(len(self.forward) - 2, -1, -1):
            if False:
                self.gd[i] = gd.GD(device=device)
            elif i:
                self.gd[i] = gd.GDTanh(device=device)
            else:
                self.gd[i] = gd.GDTanh(device=device)
                # self.gd[i] = rbm.GDTanh(device=device,
                #                        rnd_window_size=1.0)
                # self.gd[i].y_rand = self.forward[i].output_rand
            self.gd[i].link_from(self.gd[i + 1])
            self.gd[i].err_y = self.gd[i + 1].err_h
            self.gd[i].y = self.forward[i].output
            self.gd[i].h = self.forward[i].input
            self.gd[i].weights = self.forward[i].weights
            self.gd[i].bias = self.forward[i].bias
            self.gd[i].gate_skip = self.decision.gd_skip
            self.gd[i].batch_size = self.loader.minibatch_size
        self.rpt.link_from(self.gd[0])

        self.end_point = units.EndPoint()
        self.end_point.link_from(self.decision)
        self.end_point.gate_block = self.decision.complete
        self.end_point.gate_block_not = [1]

        self.loader.gate_block = self.decision.complete

        # MSE plotter
        self.plt = []
        styles = ["r-", "b-", "k-"]
        for i in range(2, 3):
            self.plt.append(plotters.SimplePlotter(figure_label="mse",
                                                   plot_style=styles[i]))
            self.plt[-1].input = self.decision.epoch_metrics
            self.plt[-1].input_field = i
            self.plt[-1].link_from(self.decision if i == 2 else
                                   self.plt[-2])
            self.plt[-1].gate_skip = self.decision.epoch_ended
            self.plt[-1].gate_skip_not = [1]
        # self.plt[-1].clear_plot = True
        # Weights plotter
        self.decision.vectors_to_sync[self.gd[0].weights] = 1
        self.plt_mx = []
        self.plt_mx.append(
            plotters.Weights2D(figure_label="First Layer Weights", limit=16))
        self.plt_mx[-1].input = self.gd[0].weights
        self.plt_mx[-1].input_field = "v"
        self.plt_mx[-1].get_shape_from = self.forward[0].input
        self.plt_mx[-1].link_from(self.decision)
        self.plt_mx[-1].gate_block = [0]  # self.decision.epoch_ended
        self.plt_mx[-1].gate_block_not = [1]
        # Weights plotter
        self.decision.vectors_to_sync[self.gd[-1].weights] = 1
        self.plt_mx.append(
            plotters.Weights2D(figure_label="Last Layer Weights", limit=16))
        self.plt_mx[-1].input = self.gd[-1].weights
        self.plt_mx[-1].input_field = "v"
        # self.plt_mx[-1].transposed = True
        self.plt_mx[-1].get_shape_from = self.forward[0].input
        self.plt_mx[-1].link_from(self.plt_mx[-2])
        # Max plotter
        self.plt_max = []
        styles = ["r--", "b--", "k--"]
        for i in range(2, 3):
            self.plt_max.append(plotters.SimplePlotter(figure_label="mse",
                                                       plot_style=styles[i]))
            self.plt_max[-1].input = self.decision.epoch_metrics
            self.plt_max[-1].input_field = i
            self.plt_max[-1].input_offs = 1
            self.plt_max[-1].link_from(self.plt[-1] if i == 2 else
                                       self.plt_max[-2])
            self.plt_max[-1].gate_skip = self.decision.epoch_ended
            self.plt_max[-1].gate_skip_not = [1]
        # self.plt_max[0].clear_plot = True
        # Min plotter
        self.plt_min = []
        styles = ["r:", "b:", "k:"]
        for i in range(2, 3):
            self.plt_min.append(plotters.SimplePlotter(figure_label="mse",
                                                       plot_style=styles[i]))
            self.plt_min[-1].input = self.decision.epoch_metrics
            self.plt_min[-1].input_field = i
            self.plt_min[-1].input_offs = 2
            self.plt_min[-1].link_from(self.plt_max[-1] if i == 2 else
                                       self.plt_min[-2])
            self.plt_min[-1].gate_skip = self.decision.epoch_ended
            self.plt_min[-1].gate_skip_not = [1]
        # self.plt_min[0].clear_plot = True
        # Image plotter
        self.decision.vectors_to_sync[self.forward[0].input] = 1
        self.decision.vectors_to_sync[self.forward[-1].output] = 1
        self.plt_img = plotters.Image(figure_label="output sample")
        self.plt_img.inputs.append(self.decision)
        self.plt_img.input_fields.append("sample_input")
        self.plt_img.inputs.append(self.decision)
        self.plt_img.input_fields.append("sample_output")
        self.plt_img.link_from(self.decision)
        self.plt_img.gate_block = [0]  # self.decision.epoch_ended
        self.plt_img.gate_block_not = [1]
        # Histogram plotter
        self.plt_hist = [None, None, plotters.MSEHistogram(
                                        figure_label="Histogram Train")]
        self.plt_hist[2].link_from(self.plt_min[-1])
        self.plt_hist[2].mse = self.decision.epoch_samples_mse[2]
        self.plt_hist[2].gate_skip = self.decision.epoch_ended
        self.plt_hist[2].gate_skip_not = [1]
        self.gd[-1].link_from(self.plt_hist[2])

    def initialize(self):
        retval = self.start_point.initialize_dependent()
        if retval:
            return retval

    def run(self, threshold_ok, threshold_skip, global_alpha, global_lambda):
        self.ev.threshold_ok = threshold_ok
        self.ev.threshold_skip = threshold_skip
        self.decision.threshold_ok = threshold_ok
        for gd in self.gd:
            gd.global_alpha = global_alpha
            gd.global_lambda = global_lambda
        retval = self.start_point.run_dependent()
        if retval:
            return retval
        self.end_point.wait()


class Workflow2(units.OpenCLUnit):
    """Sample workflow for MNIST dataset.

    Attributes:
        start_point: start point.
        rpt: repeater.
        loader: loader.
        forward: list of all-to-all forward units.
        ev: evaluator softmax.
        stat: stat collector.
        decision: Decision.
        gd: list of gradient descent units.
    """
    def __init__(self, layers=None, device=None):
        super(Workflow2, self).__init__(device=device)
        self.start_point = units.Unit()

        self.rpt = units.Repeater()
        self.rpt.link_from(self.start_point)

        self.loader = Loader()
        self.loader.link_from(self.rpt)

        # Add forward units
        self.forward = []
        for i in range(0, len(layers)):
            if not i:
                amp = None
            else:
                amp = 9.0 / 1.7159 / layers[i - 1]
            if i < len(layers) - 1:
                if not i:
                    aa = rbm.RBMTanh([layers[i]], device=device,
                                 weights_amplitude=amp)
                else:
                    aa = all2all.All2AllTanh([layers[i]], device=device,
                                 weights_amplitude=amp)
            else:
                aa = all2all.All2AllSoftmax([layers[i]], device=device,
                                            weights_amplitude=amp)
            self.forward.append(aa)
            if i:
                self.forward[i].link_from(self.forward[i - 1])
                self.forward[i].input = self.forward[i - 1].output
            else:
                self.forward[i].link_from(self.loader)
                self.forward[i].input = self.loader.minibatch_data

        # Add evaluator for single minibatch
        self.ev = evaluator.EvaluatorSoftmax(device=device)
        self.ev.link_from(self.forward[-1])
        self.ev.y = self.forward[-1].output
        self.ev.batch_size = self.loader.minibatch_size
        self.ev.labels = self.loader.minibatch_labels
        self.ev.max_idx = self.forward[-1].max_idx
        self.ev.max_samples_per_epoch = self.loader.total_samples

        # Add decision unit
        self.decision = decision.Decision(snapshot_prefix="xor_rbm",
                                          store_samples_mse=False,
                                          use_dynamic_alpha=True)
        self.decision.link_from(self.ev)
        self.decision.minibatch_class = self.loader.minibatch_class
        self.decision.minibatch_last = self.loader.minibatch_last
        self.decision.minibatch_n_err = self.ev.n_err_skipped
        self.decision.minibatch_confusion_matrix = self.ev.confusion_matrix
        self.decision.minibatch_max_err_y_sum = self.ev.max_err_y_sum
        self.decision.class_samples = self.loader.class_samples
        self.decision.workflow = self

        # Add gradient descent units
        self.gd = list(None for i in range(0, len(self.forward)))
        self.gd[-1] = gd.GDSM(device=device)
        # self.gd[-1].link_from(self.decision)
        self.gd[-1].err_y = self.ev.err_y
        self.gd[-1].y = self.forward[-1].output
        self.gd[-1].h = self.forward[-1].input
        self.gd[-1].weights = self.forward[-1].weights
        self.gd[-1].bias = self.forward[-1].bias
        self.gd[-1].gate_skip = self.decision.gd_skip
        self.gd[-1].batch_size = self.loader.minibatch_size
        """
        for i in range(len(self.forward) - 2, -1, -1):
            if i:
                self.gd[i] = gd.GDTanh(device=device)
            else:
                self.gd[i] = gd.GDTanh(device=device)
                #self.gd[i].y_rand = self.forward[i].output_rand
            self.gd[i].link_from(self.gd[i + 1])
            self.gd[i].err_y = self.gd[i + 1].err_h
            self.gd[i].y = self.forward[i].output
            self.gd[i].h = self.forward[i].input
            self.gd[i].weights = self.forward[i].weights
            self.gd[i].bias = self.forward[i].bias
            self.gd[i].gate_skip = self.decision.gd_skip
            self.gd[i].batch_size = self.loader.minibatch_size
        """
        self.rpt.link_from(self.gd[-1])

        self.end_point = units.EndPoint()
        self.end_point.link_from(self.decision)
        self.end_point.gate_block = self.decision.complete
        self.end_point.gate_block_not = [1]

        self.loader.gate_block = self.decision.complete

        # Error plotter
        self.plt = []
        styles = ["r-", "b-", "k-"]
        for i in range(2, 3):
            self.plt.append(plotters.SimplePlotter(figure_label="num errors",
                                                   plot_style=styles[i]))
            self.plt[-1].input = self.decision.epoch_n_err_pt
            self.plt[-1].input_field = i
            self.plt[-1].link_from(self.decision if i == 2 else self.plt[-2])
            self.plt[-1].gate_skip = self.decision.epoch_ended
            self.plt[-1].gate_skip_not = [1]
        # self.plt[0].clear_plot = True
        # Confusion matrix plotter
        self.plt_mx = []
        for i in range(2, 3):
            self.plt_mx.append(plotters.MatrixPlotter(
                figure_label=(("Test", "Validation", "Train")[i] + " matrix")))
            self.plt_mx[-1].input = self.decision.confusion_matrixes
            self.plt_mx[-1].input_field = i
            self.plt_mx[-1].link_from(self.plt[-1] if i == 2
                                      else self.plt_mx[-2])
            self.plt_mx[-1].gate_skip = self.decision.epoch_ended
            self.plt_mx[-1].gate_skip_not = [1]
        # err_y plotter
        self.plt_err_y = []
        for i in range(2, 3):
            self.plt_err_y.append(plotters.SimplePlotter(
                figure_label="Last layer max gradient sum",
                plot_style=styles[i]))
            self.plt_err_y[-1].input = self.decision.max_err_y_sums
            self.plt_err_y[-1].input_field = i
            self.plt_err_y[-1].link_from(self.plt_mx[-1] if i == 2
                                         else self.plt_err_y[-2])
            self.plt_err_y[-1].gate_skip = self.decision.epoch_ended
            self.plt_err_y[-1].gate_skip_not = [1]
        # self.plt_err_y[0].clear_plot = True
        self.gd[-1].link_from(self.plt_err_y[-1])

    def initialize(self):
        retval = self.start_point.initialize_dependent()
        if retval:
            return retval

    def run(self, threshold, threshold_low, global_alpha, global_lambda):
        self.ev.threshold = threshold
        self.ev.threshold_low = threshold_low
        for gd in self.gd:
            if gd == None:
                continue
            gd.global_alpha = global_alpha
            gd.global_lambda = global_lambda
        retval = self.start_point.run_dependent()
        if retval:
            return retval
        self.end_point.wait()


def main():
    # if __debug__:
    #    logging.basicConfig(level=logging.DEBUG)
    # else:
    logging.basicConfig(level=logging.INFO)
    """This is a test for correctness of a particular trained 2-layer network.
    fin = open("%s/mnist_rbm.pickle" % (config.snapshot_dir), "rb")
    w = pickle.load(fin)
    fin.close()

    weights = w.forward[0].weights.v
    i = 0
    for row in weights:
        img = row.reshape(28, 28).copy()
        img -= img.min()
        m = img.max()
        if m:
            img /= m
            img *= 255.0
        scipy.misc.imsave("/tmp/img/%03d.png" % (i), img.astype(numpy.uint8))
        i += 1

    logging.info("Done")
    sys.exit(0)
    """

    global this_dir
    rnd.default.seed(numpy.fromfile("%s/seed" % (this_dir),
                                    numpy.int32, 1024))
    # rnd.default.seed(numpy.fromfile("/dev/urandom", numpy.int32, 1024))
    try:
        cl = opencl.DeviceList()
        device = cl.get_device()
        try:
            fin = open("%s/xor_rbm.pickle" % (config.snapshot_dir), "rb")
            w0 = pickle.load(fin)
            fin.close()
            layers = []
            for i in range(0, len(w0.forward) - 1):
                layers.append(w0.forward[i].output.v.size //
                              w0.forward[i].output.v.shape[0])
            layers.append(2)
            w = Workflow2(layers=layers, device=device)
            w.initialize()
            for i in range(0, len(w0.forward) - 1):
                w.forward[i].weights.v[:] = w0.forward[i].weights.v[:]
                w.forward[i].weights.update()
                w.forward[i].bias.v[:] = w0.forward[i].bias.v[:]
                w.forward[i].bias.update()
            w.run(threshold=1.0, threshold_low=1.0,
                  global_alpha=0.001, global_lambda=0.00005)
        except FileNotFoundError:
            w = Workflow(layers=[8, 3], device=device)
            w.initialize()
            w.run(threshold_ok=0.0005, threshold_skip=0.0,
                  global_alpha=0.001, global_lambda=0.00005)
    except KeyboardInterrupt:
        w.gd[-1].gate_block = [1]
    logging.info("Will snapshot in 15 seconds...")
    time.sleep(5)
    logging.info("Will snapshot in 10 seconds...")
    time.sleep(5)
    logging.info("Will snapshot in 5 seconds...")
    time.sleep(5)
    fnme = "%s/xor_stop.pickle" % (config.snapshot_dir)
    logging.info("Snapshotting to %s" % (fnme))
    fout = open(fnme, "wb")
    pickle.dump(w, fout)
    fout.close()

    plotters.Graphics().wait_finish()
    logging.debug("End of job")


if __name__ == "__main__":
    main()
    sys.exit()