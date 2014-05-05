#!/usr/bin/python3.3 -O
# encoding: utf-8

"""
Created on April 23, 2013

A layer for local response normalization.
Detailed description given in article by Krizhevsky, Sutskever and Hinton:
"ImageNet Classification with Deep Convolutional Neural Networks"
"""

import numpy as np

from veles.znicz import nn_units
from veles import formats


class LocalResponseNormalizer(nn_units.Forward):
    """
    A base class for forward and backward units of local
    response normalization.
    """
    def __init__(self, workflow, **kwargs):
        self.alpha = kwargs.get("alpha", 0.0001)
        self.beta = kwargs.get("beta", 0.75)
        self.k = kwargs.get("k", 2)
        self.n = kwargs.get("n", 5)
        self._num_of_chans = None
        self.device = kwargs.get("device")

        super(LocalResponseNormalizer, self).__init__(workflow, **kwargs)

    def initialize(self, **kwargs):
        super(LocalResponseNormalizer, self).initialize(**kwargs)

    def _subsums(self, source_array, window_size):
        """
        For each channel calculates the sum of its neighbour channels.
        source_array must be a 4-dimensional array (channel dim is the last).
        """
        assert len(source_array.shape) == 4
        subsums = np.ndarray(shape=source_array.shape, dtype=np.float64)
        num_of_chans = source_array.shape[3]
        for i in range(num_of_chans):
            min_index = max(0, i - int(window_size / 2))
            max_index = min(i + int(window_size / 2), num_of_chans - 1)
            array_slice = source_array[:, :, :, min_index: max_index + 1]
            subsums[:, :, :, i] = np.sum(array_slice, axis=3)
        return subsums


class LRNormalizerForward(LocalResponseNormalizer):
    """
    Forward propagation of local response normalization.
    """
    def __init__(self, workflow, **kwargs):
        self.input = None  # input value of forward layer
        self.output = formats.Vector()  # output value of forward layer

        self.weights = None  # dummy attrs
        self.bias = None  # dummy attrs

        super(LRNormalizerForward, self).__init__(workflow, **kwargs)

    def init_unpickled(self):
        super(LRNormalizerForward, self).init_unpickled()
        self.cl_sources_["normalization.cl"] = {}
        self.krn_ = None

    def initialize(self, **kwargs):
        super(LRNormalizerForward, self).initialize(**kwargs)
        self.output.v = np.ndarray(shape=self.input.v.shape,
                                   dtype=self.input.v.dtype)

        self.input.initialize(self.device)
        self.output.initialize(self.device)

        self._num_of_chans = self.input.v.shape[3]

        defines = {"ALPHA": self.alpha, "BETA": self.beta, "K": self.k,
                   "N": self.n, "NUM_OF_CHANS": self._num_of_chans}

        self.build_program(defines, dtype=self.input.v.dtype)
        self.krn_ = self.get_kernel("forward")
        self.krn_.set_arg(0, self.input.v_)
        self.krn_.set_arg(1, self.output.v_)

        self._global_size_ = [self.output.v.size // self._num_of_chans]
        self._local_size_ = None

    def cpu_run(self):
        self.output.map_invalidate()
        self.input.map_read()

        assert(len(self.input.v.shape) == 4)
        input_squared = np.square(self.input.v)
        subsums = self._subsums(input_squared, self.n)
        subsums *= self.alpha
        subsums += self.k
        subsums **= self.beta

        np.copyto(self.output.v, self.input.v)
        self.output.v /= subsums

    def ocl_run(self):
        """Forward propagation from batch on GPU.
        """
        self.output.unmap()
        self.input.unmap()
        self.execute_kernel(self.krn_, self._global_size_,
                            self._local_size_).wait()


class LRNormalizerBackward(LocalResponseNormalizer):
    """
    Backward-propagation for local response normalization.
    """
    def __init__(self, workflow, **kwargs):
        self.y = None  # output of forward layer
        self.h = None  # input of forward layer
        self.err_y = None  # output error of fwd layer, our input error
        self.err_h = formats.Vector()  # input error of fwd layer, our output

        super(LRNormalizerBackward, self).__init__(workflow, **kwargs)

    def init_unpickled(self):
        super(LRNormalizerBackward, self).init_unpickled()
        self.cl_sources_["normalization.cl"] = {}
        self.krn_ = None

    def initialize(self, **kwargs):
        super(LRNormalizerBackward, self).initialize(**kwargs)
        self.err_h.v = np.ndarray(shape=self.err_y.v.shape,
                                  dtype=self.err_y.v.dtype)

        self.err_y.initialize(self.device)
        self.h.initialize(self.device)
        self.err_h.initialize(self.device)

        self._num_of_chans = self.h.v.shape[3]

        defines = {"ALPHA": self.alpha, "BETA": self.beta, "K": self.k,
                   "N": self.n, "NUM_OF_CHANS": self._num_of_chans}

        self.build_program(defines, dtype=self.h.v.dtype)
        self.krn_ = self.get_kernel("backward")
        self.krn_.set_arg(0, self.err_y.v_)
        self.krn_.set_arg(1, self.h.v_)
        self.krn_.set_arg(2, self.err_h.v_)

        self._global_size_ = [self.err_h.v.size // self._num_of_chans]
        self._local_size_ = None

    def cpu_run(self):
        self.err_h.map_invalidate()
        self.err_y.map_read()
        self.h.map_read()

        assert len(self.h.v.shape) == 4
        assert self.h.v.shape == self.err_y.v.shape

        num_of_chans = self.h.v.shape[3]
        self.err_h.v = np.zeros(shape=self.h.v.shape, dtype=np.float64)

        h_squared = np.square(self.h.v)

        h_subsums = self._subsums(h_squared, self.n)

        h_subsums *= self.alpha
        h_subsums += self.k

        h_subsums_powered = np.power(h_subsums, (self.beta + 1))

        delta_h = self.err_h.v
        delta_y = self.err_y.v

        for i in range(num_of_chans):
            min_index = max(0, i - int(self.n / 2))
            max_index = min(i + int(self.n / 2), num_of_chans - 1)

            dh = np.zeros(dtype=np.float64, shape=delta_h[:, :, :, i].shape)
            for j in range(min_index, max_index + 1):
                if i == j:
                    dh += h_subsums[:, :, :, j]
                dh -= (2 * self.beta * self.alpha * self.h.v[:, :, :, i] *
                       self.h.v[:, :, :, j])
                dh *= delta_y[:, :, :, j] / h_subsums_powered[:, :, :, j]
            delta_h[:, :, :, i] += dh

    def ocl_run(self):
        self.err_y.unmap()
        self.h.unmap()
        self.err_h.unmap()
        self.execute_kernel(self.krn_, self._global_size_,
                            self._local_size_).wait()
