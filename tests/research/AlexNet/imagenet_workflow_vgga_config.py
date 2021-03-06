# -*-coding: utf-8 -*-
"""
.. invisible:
     _   _ _____ _     _____ _____
    | | | |  ___| |   |  ___/  ___|
    | | | | |__ | |   | |__ \ `--.
    | | | |  __|| |   |  __| `--. \
    \ \_/ / |___| |___| |___/\__/ /
     \___/\____/\_____|____/\____/

Created on Nov 20, 2014

Configuration file with VGG 16 layers topology for Imagenet with pickle loader

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


import os

from veles.config import root

base_lr = 0.01
wd = 0.0005

root.common.engine.precision_type = "float"
root.common.engine.precision_level = 0
root.common.engine.backend = "cuda"

root.imagenet.root_name = "imagenet"
root.imagenet.series = "img"
root.imagenet.root_path = os.path.join(
    root.common.dirs.datasets, "AlexNet", "%s" % root.imagenet.root_name)

root.imagenet.lr_adjuster.lr_parameters = {
    "lrs_with_lengths":
    [(1, 100000), (0.1, 100000), (0.1, 100000), (0.01, 100000000)]}
root.imagenet.lr_adjuster.bias_lr_parameters = {
    "lrs_with_lengths":
    [(1, 100000), (0.1, 100000), (0.1, 100000), (0.01, 100000000)]}

root.imagenet.loader.update({
    "sx": 256,
    "sy": 256,
    "crop": (227, 227),
    "mirror": True,
    "channels": 3,
    "color_space": "RGB",
    "minibatch_size": 50,
    "normalization_type": "none",
    "shuffle_limit": 10000000,
    "original_labels_filename":
    os.path.join(
        root.imagenet.root_path,
        "original_labels_%s_%s.pickle"
        % (root.imagenet.root_name, root.imagenet.series)),
    "samples_filename":
    os.path.join(
        root.imagenet.root_path,
        "original_data_%s_%s.dat"
        % (root.imagenet.root_name, root.imagenet.series)),
    "matrixes_filename":
    os.path.join(
        root.imagenet.root_path,
        "matrixes_%s_%s.pickle"
        % (root.imagenet.root_name, root.imagenet.series)),
    "count_samples_filename":
    os.path.join(
        root.imagenet.root_path,
        "count_samples_%s_%s.json"
        % (root.imagenet.root_name, root.imagenet.series)),
})

root.imagenet.update({
    "decision": {"fail_iterations": 10000,
                 "max_epochs": 10000},
    "snapshotter": {"prefix": "imagenet", "interval": 1, "time_interval": 0},
    "add_plotters": True,
    "loss_function": "softmax",
    "lr_adjuster": {"lr_policy_name": "arbitrary_step",
                    "bias_lr_policy_name": "arbitrary_step"},
    "image_saver": {"out_dirs":
                    [os.path.join(root.common.dirs.datasets,
                                  "AlexNet/image_saver/test"),
                     os.path.join(root.common.dirs.datasets,
                                  "AlexNet/image_saver/validation"),
                     os.path.join(root.common.dirs.datasets,
                                  "AlexNet/image_saver/train")]},
    "loader_name": "imagenet_pickle_loader",
    "weights_plotter": {"limit": 256, "split_channels": False},
    "layers": [{"name": "conv_str1",
                "type": "conv_str",
                "->": {"n_kernels": 64, "kx": 3, "ky": 3,
                       "padding": (1, 1, 1, 1),
                       "weights_filling": "gaussian", "weights_stddev": 0.01,
                       "bias_filling": "constant", "bias_stddev": 0},
                "<-": {"learning_rate": 0.01, "learning_rate_bias": 0.02}},

               {"name": "conv_str2",
                "type": "conv_str",
                "->": {"n_kernels": 64, "kx": 3, "ky": 3,
                       "padding": (1, 1, 1, 1),
                       "weights_filling": "gaussian", "weights_stddev": 0.01,
                       "bias_filling": "constant", "bias_stddev": 0},
                "<-": {"learning_rate": 0.01, "learning_rate_bias": 0.02}},

               {"name": "max_pool2",
                "type": "max_pooling",
                "->": {"kx": 2, "ky": 2, "sliding": (2, 2)}},

               {"name": "conv_str3",
                "type": "conv_str",
                "->": {"n_kernels": 128, "kx": 3, "ky": 3,
                       "padding": (1, 1, 1, 1),
                       "weights_filling": "gaussian", "weights_stddev": 0.01,
                       "bias_filling": "constant", "bias_stddev": 0},
                "<-": {"learning_rate": 0.01, "learning_rate_bias": 0.02}},

               {"name": "conv_str4",
                "type": "conv_str",
                "->": {"n_kernels": 128, "kx": 3, "ky": 3,
                       "padding": (1, 1, 1, 1),
                       "weights_filling": "gaussian", "weights_stddev": 0.01,
                       "bias_filling": "constant", "bias_stddev": 0},
                "<-": {"learning_rate": 0.01, "learning_rate_bias": 0.02}},

               {"name": "max_pool4",
                "type": "max_pooling",
                "->": {"kx": 2, "ky": 2, "sliding": (2, 2)}},


               {"name": "conv_str5",
                "type": "conv_str",
                "->": {"n_kernels": 256, "kx": 3, "ky": 3,
                       "padding": (1, 1, 1, 1),
                       "weights_filling": "gaussian", "weights_stddev": 0.01,
                       "bias_filling": "constant", "bias_stddev": 0},
                "<-": {"learning_rate": 0.01, "learning_rate_bias": 0.02}},

               {"name": "conv_str6",
                "type": "conv_str",
                "->": {"n_kernels": 256, "kx": 3, "ky": 3,
                       "padding": (1, 1, 1, 1),
                       "weights_filling": "gaussian", "weights_stddev": 0.01,
                       "bias_filling": "constant", "bias_stddev": 0},
                "<-": {"learning_rate": 0.01, "learning_rate_bias": 0.02}},

               {"name": "conv_str7",
                "type": "conv_str",
                "->": {"n_kernels": 256, "kx": 3, "ky": 3,
                       "padding": (1, 1, 1, 1),
                       "weights_filling": "gaussian", "weights_stddev": 0.01,
                       "bias_filling": "constant", "bias_stddev": 0},
                "<-": {"learning_rate": 0.01, "learning_rate_bias": 0.02}},


               {"name": "max_pool7",
                "type": "max_pooling",
                "->": {"kx": 2, "ky": 2, "sliding": (2, 2)}},

               {"name": "conv_str8",
                "type": "conv_str",
                "->": {"n_kernels": 512, "kx": 3, "ky": 3,
                       "padding": (1, 1, 1, 1),
                       "weights_filling": "gaussian", "weights_stddev": 0.01,
                       "bias_filling": "constant", "bias_stddev": 0},
                "<-": {"learning_rate": 0.01, "learning_rate_bias": 0.02}},

               {"name": "conv_str9",
                "type": "conv_str",
                "->": {"n_kernels": 512, "kx": 3, "ky": 3,
                       "padding": (1, 1, 1, 1),
                       "weights_filling": "gaussian", "weights_stddev": 0.01,
                       "bias_filling": "constant", "bias_stddev": 0},
                "<-": {"learning_rate": 0.01, "learning_rate_bias": 0.02}},

               {"name": "conv_str10",
                "type": "conv_str",
                "->": {"n_kernels": 512, "kx": 3, "ky": 3,
                       "padding": (1, 1, 1, 1),
                       "weights_filling": "gaussian", "weights_stddev": 0.01,
                       "bias_filling": "constant", "bias_stddev": 0},
                "<-": {"learning_rate": 0.01, "learning_rate_bias": 0.02}},

               {"name": "max_pool10",
                "type": "max_pooling",
                "->": {"kx": 2, "ky": 2, "sliding": (2, 2)}},

               {"name": "conv_str11",
                "type": "conv_str",
                "->": {"n_kernels": 512, "kx": 3, "ky": 3,
                       "padding": (1, 1, 1, 1),
                       "weights_filling": "gaussian", "weights_stddev": 0.01,
                       "bias_filling": "constant", "bias_stddev": 0},
                "<-": {"learning_rate": 0.01, "learning_rate_bias": 0.02}},

               {"name": "conv_str12",
                "type": "conv_str",
                "->": {"n_kernels": 512, "kx": 3, "ky": 3,
                       "padding": (1, 1, 1, 1),
                       "weights_filling": "gaussian", "weights_stddev": 0.01,
                       "bias_filling": "constant", "bias_stddev": 0},
                "<-": {"learning_rate": 0.01, "learning_rate_bias": 0.02}},

               {"name": "conv_str13",
                "type": "conv_str",
                "->": {"n_kernels": 512, "kx": 3, "ky": 3,
                       "padding": (1, 1, 1, 1),
                       "weights_filling": "gaussian", "weights_stddev": 0.01,
                       "bias_filling": "constant", "bias_stddev": 0},
                "<-": {"learning_rate": 0.01, "learning_rate_bias": 0.02}},

               {"name": "max_pool13",
                "type": "max_pooling",
                "->": {"kx": 2, "ky": 2, "sliding": (2, 2)}},

               {"name": "fc_linear14",
                "type": "all2all",
                "->": {"output_sample_shape": 4096,
                       "weights_filling": "gaussian", "weights_stddev": 0.005,
                       "bias_filling": "constant", "bias_stddev": 0},
                "<-": {"learning_rate": 0.01, "learning_rate_bias": 0.02}},
               {"name": "relu14",
                "type": "activation_str"},
               {"name": "drop14",
                "type": "dropout", "dropout_ratio": 0.5},

               {"name": "fc_linear15",
                "type": "all2all",
                "->": {"output_sample_shape": 4096,
                       "weights_filling": "gaussian", "weights_stddev": 0.005,
                       "bias_filling": "constant", "bias_stddev": 0},
                "<-": {"learning_rate": 0.001, "learning_rate_bias": 0.002}},
               {"name": "relu15",
                "type": "activation_str"},
               {"name": "drop15",
                "type": "dropout", "dropout_ratio": 0.5},

               {"name": "fc_softmax16",
                "type": "softmax",
                "->": {"output_sample_shape": 1000,
                       "weights_filling": "gaussian", "weights_stddev": 0.01,
                       "bias_filling": "constant", "bias_stddev": 0},
                "<-": {"learning_rate": 0.001, "learning_rate_bias": 0.002}}]})
