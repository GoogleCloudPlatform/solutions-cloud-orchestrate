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
api_dir=$(dirname $current_dir)
orchestrate_dir=$(dirname $api_dir)
source $orchestrate_dir/environ.sh

cluster=orchestrate
tag=$(date +%Y%m%dt%H%M%S)

echo "Updating Kubernetes cluster for API..."

source $current_dir/compile_protos.sh
source $current_dir/deploy_endpoints.sh

echo "Building image $tag..."
gcloud --project=$project builds submit --tag gcr.io/$project/orchestrate:$tag $api_dir

echo "Updating deployment image..."
kubectl --context=$gke_context set image deployment orchestrate orchestrate=gcr.io/$project/orchestrate:$tag

echo "Getting rollout status..."
kubectl --context=$gke_context rollout status deployment orchestrate

echo "Done."
