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

# This dockerfile builds and installs the transfer learning CLI/API for TensorFlow
# The default command runs training based on environment variables specifying
# the model name, dataset information, output directory, etc.

ARG BASE_IMAGE="intel/intel-optimized-tensorflow"
ARG BASE_TAG="latest"

FROM ${BASE_IMAGE}:${BASE_TAG} as builder

COPY . /workspace
WORKDIR /workspace

ENV EXCLUDE_FRAMEWORK=True

RUN python setup.py bdist_wheel --universal

FROM ${BASE_IMAGE}:${BASE_TAG}

WORKDIR /workspace
ARG TLT_VERSION=0.1.0

COPY --from=builder /workspace/dist/intel_transfer_learning_tool-${TLT_VERSION}-py2.py3-none-any.whl .

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y build-essential libgl1 libglib2.0-0 python3.9-dev  && \
    pip install --upgrade pip && \
    pip install --no-cache-dir intel_transfer_learning_tool-${TLT_VERSION}-py2.py3-none-any.whl[tensorflow] && \
    pip install tensorflow-text==2.9.0 && \
    rm intel_transfer_learning_tool-${TLT_VERSION}-py2.py3-none-any.whl

ENV DATASET_DIR=/workspace/data
ENV OUTPUT_DIR=/workspace/output
ENV EPOCHS=1

CMD ["sh", "-c", \
     "tlt train --framework tensorflow --model-name ${MODEL_NAME} --output-dir ${OUTPUT_DIR} --dataset-dir ${DATASET_DIR} --epochs ${EPOCHS} --dataset-name \"${DATASET_NAME}\" "]
