#!/usr/bin/python3.3 -O
"""
Created on April 7, 2014

@author: Lyubov Podoynitsina <lyubov.p@samsung.com>
"""


import datetime
import glob
import logging
import numpy
import os
import shutil
import time
import unittest

from veles.config import root
import veles.formats as formats
import veles.rnd as rnd
import veles.znicz.image_saver as image_saver
import veles.tests.dummy_workflow as dummy_workflow


class TestImageSaver(unittest.TestCase):
    def setUp(self):
        root.common.unit_test = True

    def data(self):
        self.minibatch_data = formats.Vector()
        self.minibatch_data.v = numpy.zeros([20, 32, 32], dtype=numpy.float32)
        rnd.default.fill(self.minibatch_data.v)

        self.lbls = formats.Vector()
        self.lbls.v = numpy.array([1, 0, 0, 2, 4,
                                   7, 9, 3, 6, 8,
                                   6, 3, 5, 5, 5,
                                   9, 0, 1, 1, 0], dtype=numpy.int8)

        self.max_idx = formats.Vector()
        self.max_idx.v = numpy.array([1, 2, 1, 2, 4,
                                      7, 8, 3, 6, 8,
                                      6, 1, 5, 5, 9,
                                      9, 0, 1, 4, 0], dtype=self.lbls.v.dtype)

        self.indexes = formats.Vector()
        self.indexes.v = numpy.array([0, 1, 2, 3, 4,
                                      5, 6, 7, 8, 9,
                                      0, 1, 2, 3, 4,
                                      5, 6, 7, 8, 9], dtype=self.lbls.v.dtype)

        self.output = formats.Vector()
        self.output.v = numpy.zeros([20, 10], dtype=numpy.float32)
        rnd.default.fill(self.output.v)
        self.output.v -= self.output.v.max()
        numpy.exp(self.output.v, self.output.v)
        smm = self.output.v.sum()
        if smm != 0:
            self. output.v /= smm

    def remove_dir(self):

        for rt, dirs, files in os.walk(root.image_saver.out):
            for f in files:
                os.unlink(os.path.join(rt, f))
            for d in dirs:
                shutil.rmtree(os.path.join(rt, d))
            os.removedirs(root.image_saver.out)
            logging.info("Remove directory %s" % (root.image_saver.out))

    def test_image_saver(self):
        i = datetime.datetime.now()
        root.image_saver.out = os.path.join(
            root.common.cache_dir, "tmp/test_image_saver_%s" %
            (i.strftime('%Y_%m_%d_%H_%M_%S')))
        root.image_saver.limit = 7
        self.img_saver_SM = image_saver.ImageSaver(
            dummy_workflow.DummyWorkflow())

        self.data()

        self.img_saver_SM.input = self.minibatch_data
        self.img_saver_SM.labels = self.lbls
        self.img_saver_SM.indexes = self.indexes
        self.img_saver_SM.minibatch_size = [20]
        self.img_saver_SM.output = self.output

        self.do_image_saver_SM_t()
        self.do_image_saver_SM_validation()
        self.do_image_saver_SM_train()
        self.do_image_saver_limit()

    def test_image_saver_MSE_test(self):
        logging.info("Will test image_saver unit for MSE, test")
        i = datetime.datetime.now()
        root.image_saver.out = os.path.join(
            root.common.cache_dir, "tmp/test_image_saver_%s" %
            (i.strftime('%Y_%m_%d_%H_%M_%S')))
        root.image_saver.limit = 7
        self.img_saver_MSE = image_saver.ImageSaver(
            dummy_workflow.DummyWorkflow())
        self.data()
        self.img_saver_MSE.input = self.minibatch_data
        self.img_saver_MSE.labels = self.lbls
        self.img_saver_MSE.indexes = self.indexes
        self.img_saver_MSE.minibatch_size = [20]
        self.img_saver_MSE.output = self.output
        self.img_saver_MSE.this_save_time = [time.time()]
        self.target = formats.Vector()
        self.target.v = numpy.zeros([20, 10], dtype=numpy.float32)
        rnd.default.fill(self.target.v)
        self.img_saver_MSE.minibatch_class = [0]
        self.img_saver_MSE.target = self.target
        self.img_saver_MSE.initialize()
        self.img_saver_MSE.run()
        files_test = glob.glob("%s/*.png" % (os.path.join(root.image_saver.out,
                                                          "test")))
        logging.info("files in test: %s", files_test)
        logging.info("Number of files in test: %s", len(files_test))
        self.assertEqual(len(files_test), 7)
        logging.info("All Ok")
        self.remove_dir()

    def do_image_saver_SM_t(self):
        logging.info("Will test image_saver unit for Softmax, test")
        self.img_saver_SM.this_save_time = [time.time()]
        self.img_saver_SM.max_idx = self.max_idx
        self.img_saver_SM.minibatch_class = [0]
        self.img_saver_SM.initialize()
        self.img_saver_SM.run()
        files_test = glob.glob("%s/*.png" % (os.path.join(root.image_saver.out,
                                                          "test")))
        logging.info("files in test: %s", files_test)
        logging.info("Number of files in test: %s", len(files_test))
        self.assertEqual(len(files_test), 6)
        logging.info("All Ok")
        self.remove_dir()

    def do_image_saver_SM_validation(self):
        logging.info("Will test image_saver unit for Softmax, validation")
        self.img_saver_SM.this_save_time = [time.time()]
        self.img_saver_SM.max_idx = self.max_idx
        self.img_saver_SM.minibatch_class = [1]
        self.img_saver_SM.initialize()
        self.img_saver_SM.run()

        files_validation = glob.glob("%s/*.png" %
                                     (os.path.join(root.image_saver.out,
                                                   "validation")))
        logging.info("files in validation: %s", files_validation)
        logging.info("Number of files in validation: %s",
                     len(files_validation))
        self.assertEqual(len(files_validation), 6)
        logging.info("All Ok")
        self.remove_dir()

    def do_image_saver_SM_train(self):
        logging.info("Will test image_saver unit for Softmax, train")
        self.img_saver_SM.this_save_time = [time.time()]
        self.img_saver_SM.max_idx = self.max_idx
        self.img_saver_SM.minibatch_class = [2]
        self.img_saver_SM.initialize()
        self.img_saver_SM.run()

        files_train = glob.glob("%s/*.png" %
                                (os.path.join(root.image_saver.out, "train")))
        logging.info("files in train: %s", files_train)
        logging.info("Number of files in train: %s", len(files_train))
        self.assertEqual(len(files_train), 6)
        logging.info("All Ok")
        self.remove_dir()

    def do_image_saver_limit(self):
        logging.info("Will test image_saver unit for limit")
        self.img_saver_SM.this_save_time = [time.time()]
        self.img_saver_SM.max_idx = self.max_idx
        self.img_saver_SM.limit = 5
        self.img_saver_SM.initialize()
        self.img_saver_SM.run()

        files_train = glob.glob("%s/*.png" %
                                (os.path.join(root.image_saver.out, "train")))
        logging.info("files in train: %s", files_train)
        logging.info("Number of files in train: %s", len(files_train))
        self.assertGreaterEqual(root.image_saver.limit, len(files_train))
        logging.info("All Ok")
        self.remove_dir()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()