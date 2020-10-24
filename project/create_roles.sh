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

if [[ -z $1 ]]; then
  if [[ -z $project ]]; then
    echo "Could not detect Orchestrate project ID. Check $orchestrate_dir/environ.sh"
    exit 1
  fi
  roles="project securityAdmin"
else
  project=$1
  roles="user resourceManager devOps prereleaseInstaller"
fi

if [[ -z $project ]]; then
  echo "Usage: $0 [project]"
  echo "Please specify a project or set a default one using: gcloud config set project PROJECT"
  exit 1
fi

echo "Creating or updating Orchestrate roles"
echo "   project: $project"
echo "   roles  : $roles"

for persona in $roles; do
  role="orchestrate.$persona"
  file="$current_dir/role.$role.json"
  echo "  role: $role"
  gcloud iam roles create --quiet $role --project $project --file $file \
    || gcloud iam roles update --quiet $role --project $project --file $file
done

echo "Done."

