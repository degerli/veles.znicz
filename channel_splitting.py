import numpy
from zope.interface import implementer

from veles.opencl_units import IOpenCLUnit
from veles.znicz.nn_units import Forward


@implementer(IOpenCLUnit)
class ChannelSplitter(Forward):

    def __init__(self, workflow, **kwargs):
        super(ChannelSplitter, self).__init__(workflow, **kwargs)

    def init_unpickled(self):
        super(ChannelSplitter, self).init_unpickled()
        self.cl_sources_["channel_splitting.cl"] = {}

    def initialize(self, device, **kwargs):
        super(ChannelSplitter, self).initialize(device=device, **kwargs)
        if (self.output.mem is None or
                self.output.mem.size != self.input.mem.size):
            self.output.reset()
            self.output.mem = numpy.zeros(
                dtype=self.input.mem.dtype,
                shape=(self.input.mem.shape[0], self.input.mem.shape[3],
                       self.input.mem.shape[1], self.input.mem.shape[2]))

        self.input.initialize(self)
        self.output.initialize(self)

        if device is not None:
            self.ocl_init(device)

    def ocl_init(self, device):
        self.build_program({}, "channel_splitting.cl",
                           dtype=self.input.mem.dtype)

        self.assign_kernel("split_channels")
        self.set_args(self.input, self.output,
                      numpy.array([self.input.shape[0]], dtype=numpy.int32),
                      numpy.array([self.input.shape[3]], dtype=numpy.int32),
                      numpy.array([self.input.shape[1]], dtype=numpy.int32),
                      numpy.array([self.input.shape[2]], dtype=numpy.int32))

        self._global_size = [self.input.shape[1]]

    def cpu_run(self):
        self.output.map_invalidate()
        self.input.map_read()
        self.output.mem[:] = self.input.mem.swapaxes(3, 2).swapaxes(2, 1)[:]

    def ocl_run(self):
        """Forward propagation from batch on GPU.
        """
        self.output.unmap()
        self.input.unmap()
        self.execute_kernel(self._global_size, None)
