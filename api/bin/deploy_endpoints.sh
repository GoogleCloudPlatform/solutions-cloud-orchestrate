#!/bin/bash
# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

echo "Deploying API endpoints service..."

current_dir=$(dirname $(realpath ${BASH_SOURCE[0]}))
api_dir=$(dirname $current_dir)
orchestrate_dir=$(dirname $api_dir)
source $orchestrate_dir/environ.sh

pushd $api_dir && \
  gcloud --project=$project endpoints services deploy api_descriptor.pb api_config.yaml && \
  gcloud --project=$project services enable orchestrate.endpoints.$project.cloud.goog && \
  popd

echo "Done."
