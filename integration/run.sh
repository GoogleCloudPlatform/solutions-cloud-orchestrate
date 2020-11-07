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
integration_dir=$current_dir
orchestrate_dir=$(dirname $integration_dir)
source $orchestrate_dir/environ.sh

export ORCHESTRATE_API_HOST=localhost:50051
export GOOGLE_APPLICATION_CREDENTIALS=$ORCHESTRATE_HOME/.private/${ORCHESTRATE_PROJECT}.json

echo "Running integration tests..."
echo "ORCHESTRATE_PROJECT           : $ORCHESTRATE_PROJECT"
echo "ORCHESTRATE_API_HOST          : $ORCHESTRATE_API_HOST"
echo "GOOGLE_APPLICATION_CREDENTIALS: $GOOGLE_APPLICATION_CREDENTIALS"
if [[ ! -e ${GOOGLE_APPLICATION_CREDENTIALS} ]]; then
  echo "Unable to find service account keys for project $project at $GOOGLE_APPLICATION_CREDENTIALS"
  exit 1
fi

py.test $integration_dir --log-cli-level=INFO

echo "Done."
