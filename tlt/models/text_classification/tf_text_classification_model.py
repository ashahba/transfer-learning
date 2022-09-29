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
import tensorflow as tf
import tensorflow_hub as hub

from tlt import TLT_BASE_DIR
from tlt.models.tf_model import TFModel
from tlt.models.text_classification.text_classification_model import TextClassificationModel
from tlt.datasets.text_classification.text_classification_dataset import TextClassificationDataset
from tlt.utils.file_utils import read_json_file, verify_directory
from tlt.utils.types import FrameworkType, UseCaseType

# Note that tensorflow_text isn't used directly but the import is required to register ops used by the
# BERT text preprocessor
import tensorflow_text


class TFTextClassificationModel(TextClassificationModel, TFModel):
    """
    Class used to represent a TF pretrained model that can be used for binary text classification
    fine tuning.
    """

    def __init__(self, model_name: str, model=None):
        # extra properties that should become configurable in the future
        self._dropout_layer_rate = 0.1
        self._epsilon = 1e-08
        self._generate_checkpoints = True

        # placeholder for model definition
        self._model = None
        self._num_classes = None

        TFModel.__init__(self, model_name, FrameworkType.TENSORFLOW, UseCaseType.TEXT_CLASSIFICATION)
        TextClassificationModel.__init__(self, model_name, FrameworkType.TENSORFLOW, UseCaseType.TEXT_CLASSIFICATION,
                                         dropout_layer_rate=self._dropout_layer_rate)

        if model is None:
            self._model = None
        elif isinstance(model, str):
            self.load_from_directory(model)
            self._num_classes = self._model.output.shape[-1]
        elif isinstance(model, tf.keras.Model):
            self._model = model
            self._num_classes = self._model.output.shape[-1]
        else:
            raise TypeError("The model input must be a keras Model, string, or None but found a {}".format(type(model)))

    @property
    def num_classes(self):
        return self._num_classes

    def _get_train_callbacks(self, dataset, output_dir, initial_checkpoints, do_eval, lr_decay, dataset_num_classes):
        loss = tf.keras.losses.BinaryCrossentropy(from_logits=True) if dataset_num_classes == 2 else \
            tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True)

        metrics = tf.metrics.BinaryAccuracy() if dataset_num_classes == 2 else tf.keras.metrics.Accuracy()

        self._model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=self._learning_rate, epsilon=self._epsilon),
            loss=loss, metrics=metrics)

        if initial_checkpoints:
            if os.path.isdir(initial_checkpoints):
                initial_checkpoints = tf.train.latest_checkpoint(initial_checkpoints)

            self._model.load_weights(initial_checkpoints)


        class CollectBatchStats(tf.keras.callbacks.Callback):
            def __init__(self):
                self.batch_losses = []
                self.batch_acc = []

            def on_train_batch_end(self, batch, logs=None):
                if logs and isinstance(logs, dict):

                    # Find the name of the accuracy key
                    accuracy_key = None
                    for log_key in logs.keys():
                        if 'acc' in log_key:
                            accuracy_key = log_key
                            break

                    self.batch_losses.append(logs['loss'])

                    if accuracy_key:
                        self.batch_acc.append(logs[accuracy_key])
                self.model.reset_metrics()


        batch_stats_callback = CollectBatchStats()

        callbacks = [batch_stats_callback]

        # Create a callback for generating checkpoints
        if self._generate_checkpoints:
            checkpoint_dir = os.path.join(output_dir, "{}_checkpoints".format(self.model_name))
            verify_directory(checkpoint_dir)
            checkpoint_callback = tf.keras.callbacks.ModelCheckpoint(
                filepath=os.path.join(checkpoint_dir, self.model_name.replace('/', '_')), save_weights_only=True)
            print("Checkpoint directory:", checkpoint_dir)
            callbacks.append(checkpoint_callback)

        # Create a callback for learning rate decay
        if do_eval and lr_decay:
            callbacks.append(tf.keras.callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.2,
                patience=5,
                verbose=2,
                mode='auto',
                cooldown=1,
                min_lr=0.0000000001))

        train_data = dataset.train_subset if dataset.train_subset else dataset.dataset
        validation_data = dataset.validation_subset if do_eval else None

        return callbacks, train_data, validation_data

    def train(self, dataset: TextClassificationDataset, output_dir, epochs=1, initial_checkpoints=None,
              do_eval=True, lr_decay=True, enable_auto_mixed_precision=None, shuffle_files=True, seed=None):
        """
           Trains the model using the specified binary text classification dataset. If a path to initial checkpoints is
           provided, those weights are loaded before training.
           
           Args:
               dataset (TextClassificationDataset): The dataset to use for training. If a train subset has been
                                                    defined, that subset will be used to fit the model. Otherwise, the
                                                    entire non-partitioned dataset will be used.
               output_dir (str): A writeable output directory to write checkpoint files during training
               epochs (int): The number of training epochs [default: 1]
               initial_checkpoints (str): Path to checkpoint weights to load. If the path provided is a directory, the
                    latest checkpoint will be used.
               do_eval (bool): If do_eval is True and the dataset has a validation subset, the model will be evaluated
                    at the end of each epoch.
               lr_decay (bool): If lr_decay is True and do_eval is True, learning rate decay on the validation loss
                    is applied at the end of each epoch.
               enable_auto_mixed_precision (bool or None): Enable auto mixed precision for training. Mixed precision
                    uses both 16-bit and 32-bit floating point types to make training run faster and use less memory.
                    It is recommended to enable auto mixed precision training when running on platforms that support
                    bfloat16 (Intel third or fourth generation Xeon processors). If it is enabled on a platform that
                    does not support bfloat16, it can be detrimental to the training performance. If
                    enable_auto_mixed_precision is set to None, auto mixed precision will be automatically enabled when
                    running with Intel fourth generation Xeon processors, and disabled for other platforms.
               shuffle_files (bool): Boolean specifying whether to shuffle the training data before each epoch.
               seed (int): Optionally set a seed for reproducibility.

           Returns:
               History object from the model.fit() call

           Raises:
               FileExistsError if the output directory is a file
               TypeError if the dataset specified is not a TextClassificationDataset
               TypeError if the output_dir parameter is not a string
               TypeError if the epochs parameter is not a integer
               TypeError if the initial_checkpoints parameter is not a string
               NotImplementedError if the specified dataset has more than 2 classes
        """
        self._check_train_inputs(output_dir, dataset, TextClassificationDataset, epochs, initial_checkpoints)

        dataset_num_classes = len(dataset.class_names)

        if dataset_num_classes != 2:
            raise NotImplementedError("Training is only supported for binary text classification. The specified dataset"
                                      " has {} classes, but expected 2 classes.".format(dataset_num_classes))

        self._set_seed(seed)

        # Set auto mixed precision
        self.set_auto_mixed_precision(enable_auto_mixed_precision)

        callbacks, train_data, val_data = self._get_train_callbacks(dataset, output_dir, initial_checkpoints, do_eval,
                                                                    lr_decay, dataset_num_classes)

        return self._model.fit(train_data, validation_data=val_data, epochs=epochs, shuffle=shuffle_files,
                               callbacks=callbacks)

    def evaluate(self, dataset: TextClassificationDataset, use_test_set=False):
        """
           If there is a validation set, evaluation will be done on it (by default) or on the test set (by setting 
           use_test_set=True). Otherwise, the entire non-partitioned dataset will be used for evaluation.
        
           Args:
               dataset (TextClassificationDataset): The dataset to use for evaluation. 
               use_test_set (bool): Specify if the test partition of the dataset should be used for evaluation.
                                    [default: False)

           Returns:
               Dictionary with loss and accuracy metrics

           Raises:
               TypeError if the dataset specified is not a TextClassificationDataset
               ValueError if the use_test_set=True and no test subset has been defined in the dataset.
               ValueError if the model has not been trained or loaded yet.
        """
        if not isinstance(dataset, TextClassificationDataset):
            raise TypeError("The dataset must be a TextClassificationDataset but found a {}".format(type(dataset)))

        if use_test_set:
            if dataset.test_subset:
                eval_dataset = dataset.test_subset
            else:
                raise ValueError("No test subset is defined")
        elif dataset.validation_subset:
            eval_dataset = dataset.validation_subset
        else:
            eval_dataset = dataset.dataset

        if self._model is None:
            raise ValueError("The model must be trained or loaded before evaluation.")

        return self._model.evaluate(eval_dataset)

    def predict(self, input_samples):
        """
           Generates predictions for the specified input samples.
        
           Args:
               input_samples (str, list, numpy array, tensor, tf.data dataset or a generator keras.utils.Sequence):
                    Input samples to use to predict. These will be sent to the tf.keras.Model predict() function.

           Returns:
               Numpy array of scores

           Raises:
               ValueError if the model has not been trained or loaded yet.
               ValueError if there is a mismatch between the input_samples and the model's expected input.
        """
        if self._model is None:
            raise ValueError("The model must be trained or loaded before predicting.")

        # If a single string is passed in, make it a list so that it's compatible with the keras model predict
        if isinstance(input_samples, str):
            input_samples = [input_samples]

        return tf.sigmoid(self._model.predict(input_samples)).numpy()