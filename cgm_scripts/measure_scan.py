#
# Child Growth Monitor - Free Software for Zero Hunger
# Copyright (c) 2019 Tristan Behrens <tristan@ai-guru.de> for Welthungerhilfe
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

# python3 measure_scan.py /localssd/20190724_Standardization_AAH/RJ_BMZ_TEST_023/measure/1564044745615

import sys
sys.path.append("..")

import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "4"
from tensorflow.python.util import deprecation
deprecation._PRINT_DEPRECATION_WARNINGS = False
import tensorflow as tf
tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)
from absl import logging
logging._warn_preinit_stderr = 0

import json
import glob
from cgmcore import modelutils, utils
import h5py
import numpy as np
from bunch import Bunch

# Exit if not properly called.
if len(sys.argv) != 2:
    print("Please provide the path to a scan.")
    exit(1)

# Get the path to the scan.
scan_path = sys.argv[1]
scan_path_split = scan_path.split("/")
scan_qrcode = scan_path_split[-3]
scan_timestamp = scan_path_split[-1]

# Get the paths to the artifacts.
glob_search_path = os.path.join(scan_path, "pc", "*.pcd")
pcd_paths = glob.glob(glob_search_path)
if len(pcd_paths) == 0:
    print("No artifacts found. Aborting...")
    exit(1)

# Prepare results dictionary.
results = Bunch()
results.scan = Bunch()
results.scan.qrcode = scan_qrcode
results.scan.timestamp = scan_timestamp
results.model_results = []

# Go through the models from the models-file.
with open("/whhdata/models.json") as json_file:
    json_data = json.load(json_file)
    for entry in json_data["models"]:
        
        # Get the name of the model.
        model_name = entry["name"]
        
        # Skip model if it is disabled.
        if entry["active"] == False:
            continue
        
        # Locate the weights of the model.
        weights_search_path = os.path.join("/whhdata/models", model_name, "*")
        weights_paths = [x for x in glob.glob(weights_search_path) if "-weights" in x]
        if len(weights_paths) == 0:
            continue
        weights_path = weights_paths[0]
        
        # Get the model parameters.
        input_shape = entry["input_shape"]
        output_size = entry["output_size"]
        hidden_sizes = entry["hidden_sizes"]
        subsampling_method = entry["subsampling_method"]
        
        # Load the model.
        model = modelutils.load_pointnet(weights_path, input_shape, output_size, hidden_sizes)

        # Prepare the pointclouds.
        pointclouds = []
        for pcd_path in pcd_paths:
            pointcloud = utils.load_pcd_as_ndarray(pcd_path)
            pointcloud = utils.subsample_pointcloud(
                pointcloud,
                target_size=input_shape[0], 
                subsampling_method="sequential_skip")
            pointclouds.append(pointcloud)
        pointclouds = np.array(pointclouds)
        
        # Predict.
        predictions = model.predict(pointclouds)

        # Prepare model result.
        model_result = Bunch()
        model_result.model_name = model_name
        
        # Store measure result.
        model_result.measure_result = Bunch()
        model_result.measure_result.mean = str(np.mean(predictions))
        
        # Store artifact results.
        model_result.artifact_results = []
        for pcd_path, prediction in zip(pcd_paths, predictions):
            artifact_result = Bunch()
            artifact_result.path = pcd_path
            artifact_result.prediction = str(prediction[0])
            model_result.artifact_results.append(artifact_result)
        
        results.model_results.append(model_result)

# Return results.
results_json_string = json.dumps(results, indent=4)
print(results_json_string)
        