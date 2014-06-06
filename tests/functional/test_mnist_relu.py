#!/usr/bin/python3.3 -O
"""
Created on April 2, 2014

Copyright (c) 2013 Samsung Electronics Co., Ltd.
"""


import logging
import numpy
import os
import unittest

from veles.config import root
import veles.opencl as opencl
import veles.random_generator as rnd
# TODO(a.kazantsev): fix timeout.
#from veles.tests import timeout
import veles.znicz.tests.research.mnist as mnist_relu
import veles.tests.dummy_workflow as dummy_workflow


class TestWine(unittest.TestCase):
    def setUp(self):
        root.common.unit_test = True
        root.common.plotters_disabled = True
        self.device = opencl.Device()

    # TODO(a.kazantsev): uncomment when timeout is fixed.
    #@timeout
    def test_wine(self):
        logging.info("Will test loader, decision, evaluator units")
        rnd.get().seed(numpy.fromfile("%s/veles/znicz/tests/research/seed" %
                                      root.common.veles_dir,
                                      dtype=numpy.int32, count=1024))
        mnist_dir = os.path.join(os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))), "samples/MNIST")
        test_image_dir = os.path.join(mnist_dir, "t10k-images.idx3-ubyte")
        test_label_dir = os.path.join(mnist_dir, "t10k-labels.idx1-ubyte")
        train_image_dir = os.path.join(mnist_dir, "train-images.idx3-ubyte")
        train_label_dir = os.path.join(mnist_dir, "train-labels.idx1-ubyte")
        root.update = {
            "learning_rate_adjust": {"do": False},
            "all2all": {"weights_stddev": 0.05},
            "decision": {"fail_iterations": (0)},
            "snapshotter": {"prefix": "mnist_test_relu"},
            "loader": {"minibatch_maxsize": 60},
            "weights_plotter": {"limit": 64},
            "mnist_test": {"learning_rate": 0.03,
                           "weights_decay": 0.0,
                           "layers":
                           [{"type": "all2all_relu", "output_shape": 100},
                            {"type": "softmax", "output_shape": 10}],
                           "data_paths": {"test_images": test_image_dir,
                                          "test_label": test_label_dir,
                                          "train_images": train_image_dir,
                                          "train_label": train_label_dir}}}
        self.w = mnist_relu.Workflow(dummy_workflow.DummyWorkflow(),
                                     layers=root.mnist_test.layers,
                                     device=self.device)
        self.w.initialize(learning_rate=root.mnist_test.learning_rate,
                          weights_decay=root.mnist_test.weights_decay,
                          device=self.device)
        self.w.run()

        err = self.w.decision.epoch_n_err[1]
        self.assertEqual(err, 345)
        logging.info("All Ok")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()