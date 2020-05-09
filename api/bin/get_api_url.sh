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

# Run the following command a few times until you see an external IP assigned
# to LB, e.g.:
# NAME         TYPE           CLUSTER-IP    EXTERNAL-IP    PORT(S)        AGE
# grpc-hello   LoadBalancer   10.0.10.187   10.20.30.123   80:30586/TCP   43m
echo "Getting load balancer's external IP..."
while [[ -n `kubectl --context=$gke_context get svc orchestrate | grep '^orchestrate.*<pending>'` ]]; do
  echo -n "."
  sleep 2
done
echo
ip=`kubectl --context=$gke_context get svc orchestrate | grep '^orchestrate.*' | tr -s ' ' | cut -d ' ' -f 4`
export ORCHESTRATE_API_HOST=$ip:80

echo "ORCHESTRATE_API_HOST=$ORCHESTRATE_API_HOST"
echo
echo "Sample usage:"
echo "orchestrate ... --api-project=$project --api-host=$ORCHESTRATE_API_HOST --api_key=\$ORCHESTRATE_API_KEY"
echo "orchestrate ... --api-project=\$ORCHESTRATE_PROJECT --api-host=\$ORCHESTRATE_API_HOST --api_key=\$ORCHESTRATE_API_KEY"
echo
