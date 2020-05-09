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

current_dir=$(dirname $(realpath ${BASH_SOURCE[0]}))
orchestrate_dir=$(dirname $current_dir)
source $orchestrate_dir/environ.sh

if [[ -z $project ]]; then
  echo "Could not detect Orchestrate project ID. Check $orchestrate_dir/environ.sh"
  exit 1
fi

echo "Enabling APIs for Orchestrate in project: $project"

for service in `cat ${current_dir}/required.services.txt`; do
  echo "Service: $service"
  gcloud services enable $service --project=$project
done

echo "Done."

