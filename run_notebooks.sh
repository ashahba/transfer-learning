#!/usr/bin/env bash
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

tf_notebooks=(
    "notebooks/image_classification/tf_image_classification/Image_Classification_Transfer_Learning.ipynb"
    "notebooks/question_answering/tfhub_question_answering/BERT_Question_Answering.ipynb"
    "notebooks/text_classification/tfhub_text_classification/BERT_Binary_Text_Classification.ipynb"
    "notebooks/text_classification/tfhub_text_classification/BERT_Multi_Text_Classification.ipynb"
)

pyt_notebooks=(
    "notebooks/image_classification/pytorch_image_classification/PyTorch_Image_Classification_Transfer_Learning.ipynb"
    "notebooks/text_classification/pytorch_text_classification/PyTorch_Text_Classifier_fine_tuning.ipynb"
)

if [[ $# -eq 0 ]] ; then
    echo "No argument supplied. Please input tensorflow, pytorch, a notebook path, or a directory containing one or more notebooks."
    exit 1
fi

CURDIR=$PWD
INPUT=$1

if [[ $INPUT == "tensorflow" ]] ; then
    notebooks=${tf_notebooks[*]}
elif [[ $INPUT == "pytorch" ]] ; then
    notebooks=${pyt_notebooks[*]}
else
    # Parse the filename from the path
    DIR=${INPUT%/*}
    FILE="${INPUT##*/}"

    # If no file was given, find all notebooks in the directory
    if [ -z "$FILE" ] ; then
        readarray -d '' notebooks < <(find ${DIR} -maxdepth 1 -name *.ipynb -print0)
    else
        notebooks=($1)
    fi
fi

echo "Notebooks: ${notebooks[*]}"
for notebook in ${notebooks[*]}; do
    DIR=${notebook%/*}
    echo "Running ${notebook}..."

    if [[ $# -eq 2 ]] ; then
        echo "Stripping tag ${2}..."
        jupyter nbconvert --to script \
            --TagRemovePreprocessor.enabled=True \
            --TagRemovePreprocessor.remove_cell_tags $2 \
            --output notebook_test ${notebook}
    else
        jupyter nbconvert --to script --output notebook_test ${notebook}
    fi

    pushd ${DIR}
    PYTHONPATH=${CURDIR} ipython notebook_test.py
    rm notebook_test.py
    popd
done
