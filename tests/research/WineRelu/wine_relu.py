# -*-coding: utf-8 -*-
"""
.. invisible:
     _   _ _____ _     _____ _____
    | | | |  ___| |   |  ___/  ___|
    | | | | |__ | |   | |__ \ `--.
    | | | |  __|| |   |  __| `--. \
    \ \_/ / |___| |___| |___/\__/ /
     \___/\____/\_____|____/\____/

Created on August 4, 2013

Model created for class of wine recognition. Database - Wine.
Model - fully-connected Neural Network with SoftMax loss function with RELU
activation.

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


from veles.config import root
from .loader_wine import WineLoader  # pylint: disable=W0611
from veles.znicz.standard_workflow import StandardWorkflow


class WineReluWorkflow(StandardWorkflow):
    """
    Model created for class of wine recognition. Database - Wine.
    Model - fully-connected Neural Network with SoftMax loss function with RELU
    activation.
    """
    def create_workflow(self):
        self.link_downloader(self.start_point)
        self.link_repeater(self.downloader)
        self.link_loader(self.repeater)
        self.link_forwards(("input", "minibatch_data"), self.loader)
        self.link_evaluator(self.forwards[-1])
        self.link_decision(self.evaluator)
        self.link_snapshotter(self.decision)
        self.link_loop(self.link_gds(self.snapshotter))
        self.link_end_point(self.gds[0])


def run(load, main):
    load(WineReluWorkflow, layers=root.wine_relu.layers,
         loader_name=root.wine_relu.loader_name,
         loader_config=root.wine_relu.loader,
         snapshotter_config=root.wine_relu.snapshotter,
         downloader_config=root.wine_relu.downloader,
         loss_function="softmax")
    main()
