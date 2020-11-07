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

ROLES=$(cat ${current_dir}/required.roles.txt)

echo "Creating Orchestrate service account in project: $project"
gcloud iam service-accounts create orchestrate \
  --project=$project \
  --display-name="Orchestrate main orchestration service account."

key_file=$ORCHESTRATE_HOME/.private/$project.json
echo "Creating account key: $key_file"
mkdir -p $(dirname $key_file)
gcloud iam service-accounts keys create $key_file \
  --project=$project \
  --iam-account="orchestrate@$project.iam.gserviceaccount.com"
chmod 644 $key_file
chgrp adm $(dirname $key_file)

echo "Adding roles..."
for role in $ROLES; do
  gcloud projects add-iam-policy-binding $project \
    --member="serviceAccount:orchestrate@$project.iam.gserviceaccount.com" \
    --role="$role"
done

# gcloud projects add-iam-policy-binding $project \
#   --member="serviceAccount:orchestrate@$project.iam.gserviceaccount.com" \
#   --role="roles/pubsub.publisher"
# 
# gcloud projects add-iam-policy-binding $project \
#   --member="serviceAccount:orchestrate@$project.iam.gserviceaccount.com" \
#   --role="roles/errorreporting.writer"
# 
# gcloud projects add-iam-policy-binding $project \
#   --member="serviceAccount:orchestrate@$project.iam.gserviceaccount.com" \
#   --role="projects/$project/roles/orchestrate.securityAdmin"

echo "Done."

