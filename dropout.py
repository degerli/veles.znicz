# -*- coding: utf-8 -*-
"""
.. invisible:
     _   _ _____ _     _____ _____
    | | | |  ___| |   |  ___/  ___|
    | | | | |__ | |   | |__ \ `--.
    | | | |  __|| |   |  __| `--. \
    \ \_/ / |___| |___| |___/\__/ /
     \___/\____/\_____|____/\____/

Created on Apr 25, 2014

A dropout layer. It is a signal repeater with some repeating channels set to 0.
Inputs to be disabled are randomly selected each forward proparation.

Detailed description given in article by Krizhevsky, Sutskever and Hinton:
"ImageNet Classification with Deep Convolutional Neural Networks" (sec. 4.2).

███████████████████████████████████████████████████████████████████████████████

Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied.  See the License for the
specific language governing permissions and limitations
under the License.

███████████████████████████████████████████████████████████████████████████████
"""


from __future__ import division
import numpy
from zope.interface import implementer

from veles.accelerated_units import AcceleratedUnit, IOpenCLUnit, ICUDAUnit, \
    INumpyUnit
from veles.distributable import IDistributable, TriviallyDistributable
from veles.memory import eq_addr, ravel, Array
import veles.prng as random_generator
from veles.units import IUnit, Unit
from veles.znicz.nn_units import Forward, GradientDescentBase


class Dropout(AcceleratedUnit, TriviallyDistributable):
    hide_from_registry = True
    """
    A base class for forward and backward units of local
    response normalization.
    """
    def __init__(self, workflow, **kwargs):
        super(Dropout, self).__init__(workflow, **kwargs)
        self.dropout_ratio = kwargs.get("dropout_ratio")

    def init_unpickled(self):
        super(Dropout, self).init_unpickled()
        self.sources_["dropout"] = {}

    @property
    def dropout_ratio(self):
        """ Gets the relative amount of weights to disable.
        """
        return self._dropout_ratio

    @dropout_ratio.setter
    def dropout_ratio(self, value):
        """ Sets the relative amount of weights to disable.
        """
        assert value is None or 0. < value < 1.
        self._dropout_ratio = value


@implementer(IOpenCLUnit, ICUDAUnit, INumpyUnit)
class DropoutForward(Forward, Dropout):
    """
    Forward propagation of dropout layer.
    """
    __id__ = "c4117362-3c89-41bf-ba7d-a6b1bb0d8331"

    MIN_RANDOM_STATE = 0
    MAX_RANDOM_STATE = 0x100000000
    MAPPING = {"dropout"}

    def __init__(self, workflow, **kwargs):
        super(DropoutForward, self).__init__(workflow, **kwargs)
        self.mask = Array()  # dropout mask
        self.states = Array()
        self.rand = random_generator.get()
        self.demand("minibatch_class")

    @Dropout.dropout_ratio.setter
    def dropout_ratio(self, value):
        Dropout.dropout_ratio.fset(self, value)
        if hasattr(self, "input") and self.input is not None:
            self.calc_mask()

    def initialize(self, device, **kwargs):
        super(DropoutForward, self).initialize(device=device, **kwargs)
        self.mask.mem = numpy.empty_like(self.input.mem)
        self.states.mem = self.rand.randint(
            low=DropoutForward.MIN_RANDOM_STATE,
            high=DropoutForward.MAX_RANDOM_STATE,
            size=self.input.size * 4).astype(numpy.uint32)

        if self.output:
            assert self.output.shape[1:] == self.input.shape[1:]
        if not self.output or self.output.shape[0] != self.input.shape[0]:
            self.output.reset(numpy.zeros_like(self.input.mem))

        self.init_vectors(self.input, self.output, self.states, self.mask)

    def _gpu_init(self):
        self._threshold_arg_ = numpy.empty(1, dtype=numpy.uint64)
        self._pass_arg_ = numpy.empty(1, dtype=self.input.dtype)

        self.build_program({"OUTPUT_SIZE": self.input.size}, "%s_%s" %
                           (self.__class__.__name__,
                            "x".join(str(x) for x in self.input.shape)),
                           dtype=self.input.dtype)

        self.assign_kernel("dropout_forward")
        self.set_args(self.input, self.device.skip(2), self.states, self.mask,
                      self.output)

    def ocl_init(self):
        self._gpu_init()
        self._global_size = (self.input.size,)
        self._local_size = None

    def cuda_init(self):
        self._gpu_init()
        block_size = self.device.suggest_block_size(self._kernel_)
        self._global_size = (
            int(numpy.ceil(self.input.size / block_size)), 1, 1)
        self._local_size = (block_size, 1, 1)

    def calc_mask(self):
        leave_ratio = 1.0 - self.dropout_ratio
        self.rand.fill(self.mask.mem, -self.dropout_ratio, leave_ratio)
        numpy.maximum(self.mask.mem, 0, self.mask.mem)
        numpy.ceil(self.mask.mem, self.mask.mem)
        self.mask.mem[:] = (self.mask.mem.astype(self.input.dtype) /
                            leave_ratio)

    def numpy_run(self):
        self.output.map_invalidate()
        self.input.map_read()
        if not self.forward_mode and self.minibatch_class == 2:
            self.mask.map_invalidate()
            self.calc_mask()
            numpy.multiply(self.input.mem.ravel(), self.mask.mem.ravel(),
                           ravel(self.output.mem))
        else:
            self.output.mem[:] = self.input.mem

    def _gpu_run(self):
        self.unmap_vectors(self.input, self.output)
        if self.forward_mode or self.minibatch_class < 2:
            # Will copy input to output from outside (in cuda_run/ocl_run).
            return True
        self.unmap_vectors(self.states, self.mask)
        self._threshold_arg_[0] = ((1 << 64) - 1.0) * self.dropout_ratio
        self._pass_arg_[0] = 1.0 / (1.0 - self.dropout_ratio)
        self.set_arg(1, self._threshold_arg_)
        self.set_arg(2, self._pass_arg_)
        self.execute_kernel(self._global_size, self._local_size)
        return False

    def ocl_run(self):
        if self._gpu_run():
            self.device.queue_.copy_buffer(
                self.input.devmem, self.output.devmem, 0, 0,
                self.output.nbytes, need_event=False)

    def cuda_run(self):
        if self._gpu_run():
            self.output.devmem.from_device_async(self.input.devmem)


@implementer(IOpenCLUnit, ICUDAUnit, INumpyUnit, IDistributable)
class DropoutBackward(GradientDescentBase, Dropout):
    """
    Backward propagation of droupout layer.
    """

    MAPPING = {"dropout"}

    def __init__(self, workflow, **kwargs):
        self.mask = None  # dropout mask (should be given from forward unit)
        super(DropoutBackward, self).__init__(workflow, **kwargs)
        self.undemand("input")

    def initialize(self, device, **kwargs):
        if not hasattr(self, "input"):
            self.input = self.err_output
        super(DropoutBackward, self).initialize(device=device, **kwargs)

    def _gpu_init(self):
        self.build_program({"OUTPUT_SIZE": self.err_output.size}, "%s_%s" %
                           (self.__class__.__name__,
                            "x".join(str(x) for x in self.err_input.shape)),
                           dtype=self.err_output.mem.dtype)
        self.assign_kernel("dropout_backward")
        self.set_args(self.mask, self.err_output, self.err_input)

    def ocl_init(self):
        self._gpu_init()
        self._global_size = (self.err_output.size,)
        self._local_size = None

    def cuda_init(self):
        self._gpu_init()
        block_size = self.device.suggest_block_size(self._kernel_)
        self._global_size = (
            int(numpy.ceil(self.err_output.size / block_size)), 1, 1)
        self._local_size = (block_size, 1, 1)

    def numpy_run(self):
        if eq_addr(self.err_input.mem, self.err_output.mem):
            self.err_output.map_write()
        else:
            self.err_output.map_read()
            self.err_input.map_invalidate()
        self.mask.map_read()
        numpy.multiply(self.err_output.mem.ravel(), self.mask.mem.ravel(),
                       ravel(self.err_input.mem))

    def _gpu_run(self):
        self.unmap_vectors(self.err_output, self.err_input, self.mask)
        self.execute_kernel(self._global_size, self._local_size)

    def ocl_run(self):
        self._gpu_run()

    def cuda_run(self):
        self._gpu_run()


@implementer(IUnit)
class DropoutFixer(Unit):
    # TODO: This is temporary fix. Need to remove it after fixing Dropout
    # TODO: for real
    def __init__(self, workflow, **kwargs):
        super(DropoutFixer, self).__init__(workflow, **kwargs)
        self.drops_ = None

    def initialize(self, **kwargs):
        self.drops_ = []
        for u in self.workflow:
            if isinstance(u, DropoutForward):
                self.drops_.append(u)

    def run(self):
        mode = (not self.workflow.loader.minibatch_class == 2)
        for u in self.drops_:
            u.forward_mode = mode
