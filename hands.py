#!/usr/bin/python3.3 -O
"""
Created on Jun 14, 2013

File for Hands dataset.

@author: Kazantsev Alexey <a.kazantsev@samsung.com>
"""
import sys
import os


def add_path(path):
    if path not in sys.path:
        sys.path.append(path)


this_dir = os.path.dirname(__file__)
if not this_dir:
    this_dir = "."
add_path("%s/../src" % (this_dir, ))


import units
import formats
import error
import numpy
import config
import rnd
import opencl
import plotters
import glob
#import wavelet
import scipy.signal

import numpy as np
from scipy import sqrt, pi, arctan2, cos, sin
from scipy.ndimage import uniform_filter


# from pythonxy git
def hog(image, orientations=9, pixels_per_cell=(8, 8),
        cells_per_block=(3, 3), visualise=False, normalise=False):
    """Extract Histogram of Oriented Gradients (HOG) for a given image.

    Compute a Histogram of Oriented Gradients (HOG) by

        1. (optional) global image normalisation
        2. computing the gradient image in x and y
        3. computing gradient histograms
        4. normalising across blocks
        5. flattening into a feature vector

    Parameters
    ----------
    image : (M, N) ndarray
        Input image (greyscale).
    orientations : int
        Number of orientation bins.
    pixels_per_cell : 2 tuple (int, int)
        Size (in pixels) of a cell.
    cells_per_block  : 2 tuple (int,int)
        Number of cells in each block.
    visualise : bool, optional
        Also return an image of the HOG.
    normalise : bool, optional
        Apply power law compression to normalise the image before
        processing.

    Returns
    -------
    newarr : ndarray
        HOG for the image as a 1D (flattened) array.
    hog_image : ndarray (if visualise=True)
        A visualisation of the HOG image.

    References
    ----------
    * http://en.wikipedia.org/wiki/Histogram_of_oriented_gradients

    * Dalal, N and Triggs, B, Histograms of Oriented Gradients for
      Human Detection, IEEE Computer Society Conference on Computer
      Vision and Pattern Recognition 2005 San Diego, CA, USA

    """
    image = np.atleast_2d(image)

    """
    The first stage applies an optional global image normalisation
    equalisation that is designed to reduce the influence of illumination
    effects. In practice we use gamma (power law) compression, either
    computing the square root or the log of each colour channel.
    Image texture strength is typically proportional to the local surface
    illumination so this compression helps to reduce the effects of local
    shadowing and illumination variations.
    """

    if image.ndim > 3:
        raise ValueError("Currently only supports grey-level images")

    if normalise:
        image = sqrt(image)

    """
    The second stage computes first order image gradients. These capture
    contour, silhouette and some texture information, while providing
    further resistance to illumination variations. The locally dominant
    colour channel is used, which provides colour invariance to a large
    extent. Variant methods may also include second order image derivatives,
    which act as primitive bar detectors - a useful feature for capturing,
    e.g. bar like structures in bicycles and limbs in humans.
    """

    gx = np.zeros(image.shape)
    gy = np.zeros(image.shape)
    gx[:, :-1] = np.diff(image, n=1, axis=1)
    gy[:-1, :] = np.diff(image, n=1, axis=0)

    """
    The third stage aims to produce an encoding that is sensitive to
    local image content while remaining resistant to small changes in
    pose or appearance. The adopted method pools gradient orientation
    information locally in the same way as the SIFT [Lowe 2004]
    feature. The image window is divided into small spatial regions,
    called "cells". For each cell we accumulate a local 1-D histogram
    of gradient or edge orientations over all the pixels in the
    cell. This combined cell-level 1-D histogram forms the basic
    "orientation histogram" representation. Each orientation histogram
    divides the gradient angle range into a fixed number of
    predetermined bins. The gradient magnitudes of the pixels in the
    cell are used to vote into the orientation histogram.
    """

    magnitude = sqrt(gx ** 2 + gy ** 2)
    orientation = arctan2(gy, (gx + 1e-15)) * (180 / pi) + 90

    sy, sx = image.shape
    cx, cy = pixels_per_cell
    bx, by = cells_per_block

    n_cellsx = int(np.floor(sx // cx))  # number of cells in x
    n_cellsy = int(np.floor(sy // cy))  # number of cells in y

    # compute orientations integral images
    orientation_histogram = np.zeros((n_cellsy, n_cellsx, orientations))
    for i in range(orientations):
        #create new integral image for this orientation
        # isolate orientations in this range

        temp_ori = np.where(orientation < 180 / orientations * (i + 1),
                            orientation, 0)
        temp_ori = np.where(orientation >= 180 / orientations * i,
                            temp_ori, 0)
        # select magnitudes for those orientations
        cond2 = temp_ori > 0
        temp_mag = np.where(cond2, magnitude, 0)

        orientation_histogram[:,:,i] = uniform_filter(temp_mag, size=(cy, cx))[cy/2::cy, cx/2::cx]


    # now for each cell, compute the histogram
    #orientation_histogram = np.zeros((n_cellsx, n_cellsy, orientations))

    radius = min(cx, cy) // 2 - 1
    hog_image = None
    if visualise:
        hog_image = np.zeros((sy, sx), dtype=float)

    if visualise:
        from skimage import draw
       
        for x in range(n_cellsx):
            for y in range(n_cellsy):
                for o in range(orientations):
                    centre = tuple([y * cy + cy // 2, x * cx + cx // 2])
                    dx = radius * cos(float(o) / orientations * np.pi)
                    dy = radius * sin(float(o) / orientations * np.pi)
                    rr, cc = draw.bresenham(centre[0] - dx, centre[1] - dy,
                                            centre[0] + dx, centre[1] + dy)
                    hog_image[rr, cc] += orientation_histogram[y, x, o]

    """
    The fourth stage computes normalisation, which takes local groups of
    cells and contrast normalises their overall responses before passing
    to next stage. Normalisation introduces better invariance to illumination,
    shadowing, and edge contrast. It is performed by accumulating a measure
    of local histogram "energy" over local groups of cells that we call
    "blocks". The result is used to normalise each cell in the block.
    Typically each individual cell is shared between several blocks, but
    its normalisations are block dependent and thus different. The cell
    thus appears several times in the final output vector with different
    normalisations. This may seem redundant but it improves the performance.
    We refer to the normalised block descriptors as Histogram of Oriented
    Gradient (HOG) descriptors.
    """

    n_blocksx = (n_cellsx - bx) + 1
    n_blocksy = (n_cellsy - by) + 1
    normalised_blocks = np.zeros((n_blocksy, n_blocksx,
                                  by, bx, orientations))

    for x in range(n_blocksx):
        for y in range(n_blocksy):
            block = orientation_histogram[y:y + by, x:x + bx, :]
            eps = 1e-5
            normalised_blocks[y, x, :] = block / sqrt(block.sum() ** 2 + eps)

    """
    The final step collects the HOG descriptors from all blocks of a dense
    overlapping grid of blocks covering the detection window into a combined
    feature vector for use in the window classifier.
    """

    if visualise:
        return normalised_blocks.ravel(), hog_image
    else:
        return normalised_blocks.ravel()


def borders(a):
    mx = numpy.array([[1.0, 1.0, 1.0],
                      [1.0, -8.0, 1.0],
                      [1.0, 1.0, 1.0]], dtype=a.dtype)
    res = scipy.signal.convolve(a, mx, "same")
    a[:] = res[:]


def normalize(a):
    a -= a.min()
    m = a.max()
    if m:
        a /= m
        a *= 2.0
        a -= 1.0


class Loader(units.Unit):
    """Loads Hands data and provides mini-batch output interface.

    Attributes:
        rnd: rnd.Rand().

        minibatch_data: Hands images scaled to [-1, 1].
        minibatch_indexes: global indexes of images in minibatch.
        minibatch_labels: labels for indexes in minibatch.

        minibatch_class: class of the minibatch: 0-test, 1-validation, 2-train.
        minibatch_last: if current minibatch is last in it's class.

        minibatch_offs: offset of the current minibatch in all samples,
                        where first come test samples, then validation, with
                        train ones at the end.
        minibatch_size: size of the current minibatch.
        total_samples: total number of samples in the dataset.
        class_samples: number of samples per class.
        minibatch_maxsize: maximum size of minibatch in samples.
        nextclass_offs: offset in samples where the next class begins.

        original_data: original Hands images scaled to [-1, 1] as single batch.
        original_labels: original Hands labels as single batch.
        width: width of the input image.
    """
    def __init__(self,
                 validation_paths=["../../Hands/Positive/Testing/*.raw",
                                   "../../Hands/Negative/Testing/*.raw"],
                 train_paths=["../../Hands/Positive/Training/*.raw",
                              "../../Hands/Negative/Training/*.raw"],
                 classes=[0, 10000, 60000], minibatch_max_size=180,
                 rnd=rnd.default, unpickling=0):
        """Constructor.

        Parameters:
            classes: [test, validation, train],
                ints - in samples,
                floats - relative from (0 to 1).
            minibatch_size: minibatch max size.
        """
        super(Loader, self).__init__(unpickling=unpickling)
        if unpickling:
            return
        self.width = None

        self.validation_paths = validation_paths
        self.train_paths = train_paths

        self.rnd = [rnd]

        self.minibatch_data = formats.Batch()
        self.minibatch_indexes = formats.Labels(70000)
        self.minibatch_labels = formats.Labels(10)

        self.minibatch_class = [0]
        self.minibatch_last = [0]

        self.total_samples = [70000]
        self.class_samples = classes.copy()
        if type(self.class_samples[2]) == float:
            smm = 0
            for i in range(0, len(self.class_samples) - 1):
                self.class_samples[i] = int(
                numpy.round(self.total_samples[0] * self.class_samples[i]))
                smm += self.class_samples[i]
            self.class_samples[-1] = self.total_samples[0] - smm
        self.minibatch_offs = [self.total_samples[0]]
        self.minibatch_size = [0]
        self.minibatch_maxsize = [minibatch_max_size]
        self.nextclass_offs = [0, 0, 0]
        offs = 0
        for i in range(0, len(self.class_samples)):
            offs += self.class_samples[i]
            self.nextclass_offs[i] = offs
        if self.nextclass_offs[-1] != self.total_samples[0]:
            raise error.ErrBadFormat("Sum of class samples (%d) differs from "
                "total number of samples (%d)" % (self.nextclass_offs[-1],
                                                  self.total_samples))

        self.original_data = None
        self.original_labels = None

        self.shuffled_indexes = None

    def load_original(self, pathname):
        """Loads data from original Hands files.
        """
        print("Loading from %s..." % (pathname, ))
        files = glob.glob(pathname)
        files.sort()
        n_files = len(files)
        if not n_files:
            raise error.ErrNotExists("No files fetched as %s" % (pathname, ))
        a = numpy.fromfile(files[0], dtype=numpy.byte)
        if self.width == None:
            self.width = int(numpy.sqrt(a.size))
        if self.width * self.width != a.size:
            raise error.ErrBadFormat("Found non square file %s" % (files[0], ))
        aa = numpy.zeros([n_files, 324], #self.width, self.width],
                         dtype=config.dtypes[config.dtype])
        a = a.reshape([self.width, self.width])
        b = hog(a)
        aa[0][:] = b[:]
        normalize(aa[0])
        #borders(aa[0])
        #tmp = aa[0].copy()
        #wavelet.transform(aa[0], tmp, 32, 32, 8, 10, 1)
        #aa[0][0:32, 16:32] = 0.0
        #aa[0][16:32, 0:16] = 0.0
        #normalize(aa[0])
        for i in range(1, n_files):
            a = numpy.fromfile(files[i], dtype=numpy.byte)
            if a.size != self.width * self.width:
                raise error.ErrBadFormat("Found file with different "
                                         "size than first: %s", files[i])
            a = a.reshape([self.width, self.width])
            b = hog(a)
            aa[i][:] = b[:]
            normalize(aa[i])
            #borders(aa[i])
            #wavelet.transform(aa[i], tmp, 32, 32, 8, 10, 1)
            #aa[i][0:32, 16:32] = 0.0
            #aa[i][16:32, 0:16] = 0.0
            #normalize(aa[i])
        return aa

    def initialize(self):
        """Here we will load Hands data.
        """
        # Load validation set.
        self.class_samples[0] = 0
        self.nextclass_offs[0] = 0
        a = self.load_original(self.validation_paths[0])
        self.original_data = a
        self.original_labels = numpy.zeros(a.shape[0], dtype=numpy.int8)
        for i in range(1, len(self.validation_paths)):
            a = self.load_original(self.validation_paths[i])
            self.original_data = numpy.append(self.original_data, a, 0)
            l = numpy.zeros(a.shape[0], dtype=numpy.int8)
            l[:] = i
            self.original_labels = numpy.append(self.original_labels, l, 0)
        self.class_samples[1] = self.original_data.shape[0]
        self.nextclass_offs[1] = self.nextclass_offs[0] + self.class_samples[1]
        # Load train set.
        for i in range(0, len(self.train_paths)):
            a = self.load_original(self.train_paths[i])
            self.original_data = numpy.append(self.original_data, a, 0)
            l = numpy.zeros(a.shape[0], dtype=numpy.int8)
            l[:] = i
            self.original_labels = numpy.append(self.original_labels, l, 0)
        self.total_samples[0] = self.original_data.shape[0]
        self.class_samples[2] = self.total_samples[0] - self.class_samples[1]
        self.nextclass_offs[2] = self.total_samples[0]

        self.shuffled_indexes = numpy.arange(self.total_samples[0],
                                             dtype=numpy.int32)

        self.minibatch_maxsize[0] = min(self.minibatch_maxsize[0],
                                        max(self.class_samples[2],
                                            self.class_samples[1],
                                            self.class_samples[0]))

        sh = [self.minibatch_maxsize[0]]
        for i in self.original_data.shape[1:]:
            sh.append(i)
        self.minibatch_data.batch = numpy.zeros(
            sh, dtype=config.dtypes[config.dtype])
        self.minibatch_labels.batch = numpy.zeros(
            [self.minibatch_maxsize[0]], dtype=numpy.int8)
        self.minibatch_indexes.batch = numpy.zeros(
            [self.minibatch_maxsize[0]], dtype=numpy.int32)

        self.minibatch_indexes.n_classes = self.total_samples[0]
        self.minibatch_labels.n_classes = len(self.validation_paths)

        if self.class_samples[0]:
            self.shuffle_validation_train()
        else:
            self.shuffle_train()

    def shuffle_validation_train(self):
        """Shuffles original train dataset
            and allocates 10000 for validation,
            so the layout will be:
                0:10000: test,
                10000:20000: validation,
                20000:70000: train.
        """
        self.rnd[0].shuffle(self.shuffled_indexes[self.nextclass_offs[0]:\
                                                  self.nextclass_offs[2]])

    def shuffle_train(self):
        """Shuffles used train dataset
            so the layout will be:
                0:10000: test,
                10000:20000: validation,
                20000:70000: randomized train.
        """
        self.rnd[0].shuffle(self.shuffled_indexes[self.nextclass_offs[1]:\
                                                  self.nextclass_offs[2]])

    def shuffle(self):
        """Shuffle the dataset after one epoch.
        """
        self.shuffle_train()

    def run(self):
        """Prepare the minibatch.
        """
        t1 = time.time()

        self.minibatch_offs[0] += self.minibatch_size[0]
        # Reshuffle when end of data reached.
        if self.minibatch_offs[0] >= self.total_samples[0]:
            self.shuffle()
            self.minibatch_offs[0] = 0

        # Compute minibatch size and it's class.
        for i in range(0, len(self.nextclass_offs)):
            if self.minibatch_offs[0] < self.nextclass_offs[i]:
                self.minibatch_class[0] = i
                minibatch_size = min(self.minibatch_maxsize[0],
                    self.nextclass_offs[i] - self.minibatch_offs[0])
                if self.minibatch_offs[0] + minibatch_size >= \
                   self.nextclass_offs[self.minibatch_class[0]]:
                    self.minibatch_last[0] = 1
                else:
                    self.minibatch_last[0] = 0
                break
        else:
            raise error.ErrNotExists("Could not determine minibatch class.")
        self.minibatch_size[0] = minibatch_size

        # Sync from GPU if neccessary.
        self.minibatch_data.sync()

        # Fill minibatch data labels and indexes according to current shuffle.
        idxs = self.minibatch_indexes.batch
        idxs[0:minibatch_size] = self.shuffled_indexes[self.minibatch_offs[0]:\
            self.minibatch_offs[0] + minibatch_size]

        self.minibatch_labels.batch[0:minibatch_size] = \
            self.original_labels[idxs[0:minibatch_size]]

        self.minibatch_data.batch[0:minibatch_size] = \
            self.original_data[idxs[0:minibatch_size]]

        # Fill excessive indexes.
        if minibatch_size < self.minibatch_maxsize[0]:
            self.minibatch_data.batch[minibatch_size:] = 0.0
            self.minibatch_labels.batch[minibatch_size:] = -1
            self.minibatch_indexes.batch[minibatch_size:] = -1

        # Set update flag for GPU operation.
        self.minibatch_data.update()
        self.minibatch_labels.update()
        self.minibatch_indexes.update()

        if __debug__:
            print("%s in %.2f sec" % (self.__class__.__name__,
                                      time.time() - t1))


import all2all
import evaluator
import gd


class Decision(units.Unit):
    """Decides on the learning behavior.

    Attributes:
        complete: completed.
        minibatch_class: current minibatch class.
        minibatch_last: if current minibatch is last in it's class.
        gd_skip: skip gradient descent or not.
        epoch_number: epoch number.
        epoch_min_err: minimum number of errors by class per epoch.
        n_err: current number of errors per class.
        minibatch_n_err: number of errors for minibatch.
        n_err_pt: n_err in percents.
        class_samples: number of samples per class.
        epoch_ended: if an epoch has ended.
        fail_iterations: number of consequent iterations with non-decreased
            validation error.
        confusion_matrix: confusion matrix.
    """
    def __init__(self, fail_iterations=250, unpickling=0):
        super(Decision, self).__init__(unpickling=unpickling)
        if unpickling:
            return
        self.complete = [0]
        self.minibatch_class = None  # [0]
        self.minibatch_last = None  # [0]
        self.gd_skip = [0]
        self.epoch_number = [0]
        self.epoch_min_err = [1.0e30, 1.0e30, 1.0e30]
        self.n_err = [0, 0, 0]
        self.minibatch_n_err = None  # [0]
        self.fail_iterations = [fail_iterations]
        self.epoch_ended = [0]
        self.n_err_pt = [100.0, 100.0, 100.0]
        self.class_samples = None  # [0, 0, 0]
        self.min_validation_err = 1.0e30
        self.min_validation_err_epoch_number = -1
        #self.prev_train_err = 1.0e30
        self.workflow = None
        self.fnme = None
        self.t1 = None
        self.confusion_matrix = None

    def run(self):
        if self.t1 == None:
            self.t1 = time.time()
        self.complete[0] = 0
        self.epoch_ended[0] = 0

        minibatch_class = self.minibatch_class[0]
        self.n_err[minibatch_class] += self.minibatch_n_err[0]

        if self.minibatch_last[0]:
            self.epoch_min_err[minibatch_class] = \
                min(self.n_err[minibatch_class],
                    self.epoch_min_err[minibatch_class])

        # Compute errors in percents
        for i in range(0, len(self.n_err_pt)):
            if self.class_samples[i]:
                self.n_err_pt[i] = self.n_err[i] / self.class_samples[i]
                self.n_err_pt[i] *= 100.0

        # Check skip gradient descent or not
        if self.minibatch_class[0] < 2:
            self.gd_skip[0] = 1
        else:
            self.gd_skip[0] = 0

        if self.minibatch_last[0]:
            # Test and Validation sets processed
            if self.minibatch_class[0] == 1:
                if self.epoch_min_err[1] < self.min_validation_err:
                    self.min_validation_err = self.epoch_min_err[1]
                    self.min_validation_err_epoch_number = self.epoch_number[0]
                    if self.n_err_pt[1] < 4.5:
                        global this_dir
                        if self.fnme != None:
                            try:
                                os.unlink(self.fnme)
                            except FileNotFoundError:
                                pass
                        self.fnme = "%s/hands_%.2f_%.2f_%.2f.pickle" % \
                            (this_dir, self.n_err_pt[1],
                             self.confusion_matrix.v[0, 1] /
                             (self.class_samples[0] +
                              self.class_samples[1]) * 100,
                             self.confusion_matrix.v[1, 0] /
                             (self.class_samples[0] +
                              self.class_samples[1]) * 100)
                        print("                                        "
                              "Snapshotting to %s" % (self.fnme, ))
                        fout = open(self.fnme, "wb")
                        pickle.dump(self.workflow, fout)
                        fout.close()
                self.confusion_matrix.v[:] = 0
                # Stop condition
                if self.epoch_number[0] - \
                   self.min_validation_err_epoch_number > \
                   self.fail_iterations[0]:
                    self.complete[0] = 1

            # Print some statistics
            t2 = time.time()
            print("Epoch %d Class %d Errors %d in %.2f sec" % \
                  (self.epoch_number[0], self.minibatch_class[0],
                   self.n_err[self.minibatch_class[0]],
                   t2 - self.t1))
            self.t1 = t2

            # Training set processed
            if self.minibatch_class[0] == 2:
                """
                this_train_err = self.n_err[2]
                if self.prev_train_err:
                    k = this_train_err / self.prev_train_err
                else:
                    k = 1.0
                if k < 1.04:
                    ak = 1.05
                else:
                    ak = 0.7
                self.prev_train_err = this_train_err
                for gd in self.workflow.gd:
                    gd.global_alpha = max(min(ak * gd.global_alpha, 0.9999),
                                          0.0001)
                print("new global_alpha: %.4f" % \
                      (self.workflow.gd[0].global_alpha, ))
                """
                self.epoch_ended[0] = 1
                self.epoch_number[0] += 1
                # Reset n_err
                for i in range(0, len(self.n_err)):
                    self.n_err[i] = 0
                # Reset confusion matrix
                self.confusion_matrix.v[:] = 0


class Workflow(units.OpenCLUnit):
    """Sample workflow for Hands dataset.

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
    def __init__(self, layers=None, device=None, unpickling=None):
        super(Workflow, self).__init__(device=device, unpickling=unpickling)
        if unpickling:
            return
        self.start_point = units.Unit()

        self.rpt = units.Repeater()
        self.rpt.link_from(self.start_point)

        self.loader = Loader()
        self.loader.link_from(self.rpt)

        # Add forward units
        self.forward = []
        for i in range(0, len(layers)):
            #if not i:
            #    amp = 9.0 / 784
            #else:
            #    amp = 9.0 / 1.7159 / layers[i - 1]
            amp = 0.05
            if i < len(layers) - 1:
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

        # Add decision unit
        self.decision = Decision()
        self.decision.link_from(self.ev)
        self.decision.minibatch_class = self.loader.minibatch_class
        self.decision.minibatch_last = self.loader.minibatch_last
        self.decision.minibatch_n_err = self.ev.n_err
        self.decision.class_samples = self.loader.class_samples
        self.decision.confusion_matrix = self.ev.confusion_matrix
        self.decision.workflow = self

        # Add gradient descent units
        self.gd = list(None for i in range(0, len(self.forward)))
        self.gd[-1] = gd.GDSM(device=device)
        self.gd[-1].link_from(self.decision)
        self.gd[-1].err_y = self.ev.err_y
        self.gd[-1].y = self.forward[-1].output
        self.gd[-1].h = self.forward[-1].input
        self.gd[-1].weights = self.forward[-1].weights
        self.gd[-1].bias = self.forward[-1].bias
        self.gd[-1].gate_skip = self.decision.gd_skip
        self.gd[-1].batch_size = self.loader.minibatch_size
        for i in range(len(self.forward) - 2, -1, -1):
            self.gd[i] = gd.GDTanh(device=device)
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

        # Plotter here
        self.plt = []
        styles = ["r-", "b-", "k-"]
        for i in range(0, 3):
            self.plt.append(plotters.SimplePlotter(device=device,
                            figure_label="num errors",
                            plot_style=styles[i]))
            self.plt[-1].input = self.decision.n_err_pt
            self.plt[-1].input_field = i
            self.plt[-1].link_from(self.decision)
            self.plt[-1].gate_block = self.decision.epoch_ended
            self.plt[-1].gate_block_not = [1]

    def initialize(self):
        retval = self.start_point.initialize_dependent()
        if retval:
            return retval

    def run(self, threshold, threshold_low, global_alpha, global_lambda):
        self.ev.threshold = threshold
        self.ev.threshold_low = threshold_low
        for gd in self.gd:
            gd.global_alpha = global_alpha
            gd.global_lambda = global_lambda
        retval = self.start_point.run_dependent()
        if retval:
            return retval
        self.end_point.wait()


import inline
import pickle
import time
#import matplotlib.pyplot as pp
#import matplotlib.cm as cm


def main():
    """
    fin = open("mnist.1.86.2layer100neurons.pickle", "rb")
    w = pickle.load(fin)
    fin.close()

    fout = open("w100.txt", "w")
    weights = w.forward[0].weights.v
    for row in weights:
        fout.write(" ".join("%.6f" % (x, ) for x in row))
        fout.write("\n")
    fout.close()
    fout = open("b100.txt", "w")
    bias = w.forward[0].bias.v
    fout.write(" ".join("%.6f" % (x, ) for x in bias))
    fout.write("\n")
    fout.close()

    fout = open("w10.txt", "w")
    weights = w.forward[1].weights.v
    for row in weights:
        fout.write(" ".join("%.6f" % (x, ) for x in row))
        fout.write("\n")
    fout.close()
    fout = open("b10.txt", "w")
    bias = w.forward[1].bias.v
    fout.write(" ".join("%.6f" % (x, ) for x in bias))
    fout.write("\n")
    fout.close()

    print("Done")
    sys.exit(0)
    """

    global this_dir
    rnd.default.seed(numpy.fromfile("%s/scripts/seed" % (this_dir, ),
                                    numpy.int32, 1024))
    #rnd.default.seed(numpy.fromfile("/dev/urandom", numpy.int32, 1024))
    unistd = inline.Inline()
    unistd.sources.append("#include <unistd.h>")
    unistd.function_descriptions = {"_exit": "iv"}
    unistd.compile()
    try:
        cl = opencl.DeviceList()
        device = cl.get_device()
        w = Workflow(layers=[30, 2], device=device)
        w.initialize()
    except KeyboardInterrupt:
        unistd.execute("_exit", 0)
    try:
        w.run(threshold=1.0, threshold_low=1.0,
              global_alpha=0.05, global_lambda=0.0)
    except KeyboardInterrupt:
        w.gd[-1].gate_block = [1]
    print("Will snapshot after 15 seconds...")
    time.sleep(5)
    print("Will snapshot after 10 seconds...")
    time.sleep(5)
    print("Will snapshot after 5 seconds...")
    time.sleep(5)
    fnme = "%s/hands.pickle" % (this_dir, )
    print("Snapshotting to %s" % (fnme, ))
    fout = open(fnme, "wb")
    pickle.dump(w, fout)
    fout.close()

    try:
        plotters.Graphics().wait_finish()
    except:
        pass
    print("Will now exit")
    unistd.execute("_exit", 0)


if __name__ == "__main__":
    main()
