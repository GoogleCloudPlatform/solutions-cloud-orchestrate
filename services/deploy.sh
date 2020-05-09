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

path=$1
if [[ -z $path ]]; then
  echo "Usage: $(basename $0) <function_name>"
  exit 1
fi

current_dir=$(dirname $(realpath ${BASH_SOURCE[0]}))
orchestrate_dir=$(dirname $current_dir)
source $orchestrate_dir/environ.sh

source_path=$(realpath $path)
name=$(basename $path)
topic=$name

echo "Deploying $project.$name triggered by $topic from $source_path"

gcloud --project=$project functions deploy $name \
  --entry-point=main \
  --runtime=python37 \
  --trigger-topic=$topic \
  --service-account="orchestrate@$project.iam.gserviceaccount.com" \
  --source=$source_path \
  --timeout=540s

echo "Done."
