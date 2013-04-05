"""
Created on Mar 20, 2013

File for MNIST dataset.

@author: Kazantsev Alexey <a.kazantsev@samsung.com>
"""
import filters
import struct
import error
import pickle
import numpy
import data_batch


class MNISTLoader(filters.GeneralFilter):
    """Loads MNIST data

    Attributes:
        output: State object holding MNIST training set as DataBatch object.
        labels: State object holding MNIST training set labels as Labels object.
    """
    def __init__(self, unpickling = 0):
        super(MNISTLoader, self).__init__(unpickling)
        if unpickling:
            return
        self.output = filters.State()
        self.labels = filters.State()

    def load_original(self):
        """Loads data from original MNIST files
        """
        print("One time relatively slow load from original MNIST files...")

        # Reading labels:
        fin = open("MNIST/train-labels.idx1-ubyte", "rb")

        header, = struct.unpack(">i", fin.read(4))
        if header != 2049:
            raise error.ErrBadFormat("Wrong header in train-labels")

        n_labels, = struct.unpack(">i", fin.read(4))
        if n_labels != 60000:
            raise error.ErrBadFormat("Wrong number of labels in train-labels")

        self.labels.data = data_batch.Labels()
        self.labels.data.data = numpy.fromfile(fin, dtype=numpy.byte, count=n_labels)
        if self.labels.data.data.size != n_labels:
            raise error.ErrBadFormat("EOF reached while reading labels from train-labels")
        if self.labels.data.data.min() != 0 or self.labels.data.data.max() != 9:
            raise error.ErrBadFormat("Wrong labels range in train-labels.")
        self.labels.data.n_classes = 10

        fin.close()

        # Reading images:
        fin = open("MNIST/train-images.idx3-ubyte", "rb")

        header, = struct.unpack(">i", fin.read(4))
        if header != 2051:
            raise error.ErrBadFormat("Wrong header in train-images")

        n_images, = struct.unpack(">i", fin.read(4))
        if n_images != n_labels:
            raise error.ErrBadFormat("Wrong number of images in train-images")

        n_rows, n_cols = struct.unpack(">2i", fin.read(8))
        if n_rows != 28 or n_cols != 28:
            raise error.ErrBadFormat("Wrong images size in train-images, should be 28*28")

        # 0 - white, 255 - black
        pixels = numpy.fromfile(fin, numpy.ubyte, n_images * n_rows * n_cols);
        if pixels.shape[0] != n_images * n_rows * n_cols:
            raise error.ErrBadFormat("EOF reached while reading images from train-images")

        fin.close()

        # Transforming images into float arrays and normalizing to [-1, 1]:
        images = pixels.astype(numpy.float32).reshape(n_images, n_rows, n_cols)
        print("Original range: [%.1f, %.1f]" % (images.min(), images.max()))
        for image in images:
            vle_min = image.min()
            vle_max = image.max()
            image += -vle_min
            image *= 2.0 / (vle_max - vle_min)
            image += -1.0
        print("Range after normalization: [%.1f, %.1f]" % (images.min(), images.max()))
        self.output.data = data_batch.DataBatch(data=images)
        print("Done")

        print("Saving to cache for later faster load...")
        fout = open("cache/MNIST-train.pickle", "wb")
        pickle.dump(self.output.data, fout)
        fout.close()
        print("Done")

    def run(self, endofjob_callback = None):
        """GeneralFilter method.
        
        Here we will load MNIST data.
        """
        try:
            fin = open("cache/MNIST-train.pickle", "rb")
            self.output.data = pickle.load(fin)
            fin.close()
        except IOError:
            self.load_original()
        self.output.update_mtime() 
        if endofjob_callback:
            endofjob_callback(self)
