#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: EPL-2.0
#

import os

from datasets import load_dataset, concatenate_datasets
from datasets.arrow_dataset import Dataset

from tlt import TLT_BASE_DIR
from tlt.utils.file_utils import read_json_file
from tlt.datasets.hf_dataset import HFDataset
from tlt.datasets.text_classification.text_classification_dataset import TextClassificationDataset

DATASET_CONFIG_DIR = os.path.join(TLT_BASE_DIR, "datasets/configs")


class HFTextClassificationDataset(TextClassificationDataset, HFDataset):
    """
    A text classification dataset from the Hugging Face datasets catalog
    """

    def __init__(self, dataset_dir, dataset_name, split=['train'], num_workers=0, shuffle_files=True,
                 distributed=False):
        if not isinstance(split, list):
            raise ValueError("Value of split argument must be a list.")

        TextClassificationDataset.__init__(self, dataset_dir, dataset_name, "huggingface")
        self._preprocessed = {}
        self._split = split
        self._data_loader = None
        self._train_loader = None
        self._test_loader = None
        self._validation_loader = None
        self._train_subset = None
        self._test_subset = None
        self._validation_subset = None
        self._num_workers = num_workers
        self._shuffle = shuffle_files
        self._distributed = distributed
        self._info = {
            'name': dataset_name
        }

        if len(split) == 1:
            self._validation_type = 'recall'  # Train & evaluate on the whole dataset

            # If only one split is given use it as the main dataset object
            self._dataset = self.load_hf_dataset(dataset_name, split=split[0])

        else:
            self._validation_type = 'defined_split'  # Defined by user or huggingface
            if 'train' in split:
                self._dataset = self.load_hf_dataset(dataset_name, split='train')
                self._train_indices = range(len(self._dataset))
                self._train_subset = self.train_subset

            if 'test' in split:
                test_dataset = self.load_hf_dataset(dataset_name, split='test')
                test_length = len(test_dataset)
                if self._dataset:
                    current_length = len(self._dataset)
                    self._dataset = concatenate_datasets([self._dataset, test_dataset])
                    self._test_indices = range(current_length, current_length + test_length)
                else:
                    self._dataset = test_dataset
                    self._test_indices = range(test_length)

                self._test_subset = self.test_subset

            if 'validation' in split:
                validation_dataset = self.load_hf_dataset(dataset_name, split='validation')
                validation_length = len(validation_dataset)
                if self._dataset:
                    current_length = len(self._dataset)
                    self._dataset = concatenate_datasets([self._dataset, validation_dataset])
                    self._validation_indices = range(current_length, current_length + validation_length)
                else:
                    self._dataset = validation_dataset
                    self._validation_indices = range(validation_length)

                self._validation_subset = self.validation_subset

            if 'unsupervised' in split:
                unsupervised_dataset = self.load_hf_dataset(dataset_name, split='unsupervised')
                if self._dataset:
                    self._dataset = concatenate_datasets([self._dataset, unsupervised_dataset])
                else:
                    self._dataset = unsupervised_dataset

    def load_hf_dataset(self, dataset_name: str, split: str) -> Dataset:
        """
        Helper function to load the dataset from hugging face catalog
        """
        main_dataset = dataset_name
        subset = None
        config_file = os.path.join(DATASET_CONFIG_DIR, "hf_text_classification_datasets.json")
        config_dict = read_json_file(config_file)
        available_datasets = list(config_dict.keys())

        if dataset_name not in available_datasets:
            raise ValueError("Dataset is not supported. Choose from: {}".format(available_datasets))

        # We separate the dataset_name by checking whether it has the format of "dataset/subset"
        if '/' in dataset_name:
            main_dataset = dataset_name.split('/')[0]
            subset = dataset_name.split('/')[1]

        if subset is not None:
            return load_dataset(main_dataset, subset, split=split)
        else:
            return load_dataset(main_dataset, split=split)

    @property
    def dataset(self) -> Dataset:
        """
        Returns datasets.arrow_dataset.Dataset object
        """
        return self._dataset

    @property
    def class_names(self) -> list:
        """
        Returns a list of class labels
        """
        try:
            names = self.dataset.features['label'].names
        except KeyError:
            names = self.dataset.features['labels'].names

        return names

    @property
    def info(self):
        """
        Returns a dictionary of information about the dataset
        """
        return {'dataset_info': self._info, 'preprocessing_info': self._preprocessed}

    def __len__(self):
        return len(self._dataset)
