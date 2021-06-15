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

# This bootstrap installs and initializes a VM to use as a Cloud Orchestrate
# command VM.  It performs The following tasks:
#
#   - Installs core Orchestrate dependencies.
#   - Installs Cloud Orchestrate repository.

DATE=`date`
SEP="------------------------------------------------------------------"
echo "*** START $0 $DATE ***"

export CMD_NAME=$(curl -sH Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/name)
export PROJECT=$(curl -sH Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/project/project-id)
export ZONE=$(curl -sH Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/zone | cut -d/ -f4)
export BOOTSTRAPPED=$(curl -sH Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/attributes/bootstrapped)
export ORCHESTRATE_HOME=/opt/solutions-cloud-orchestrate
export ORCHESTRATE_VIRTUALENV=/opt/orchestrate
export REPO_LOC=https://github.com/GoogleCloudPlatform/solutions-cloud-orchestrate.git
export PROFILE=/etc/profile.d/orchestrate.sh
export BRANCH=main
export BOOTSTRAP_VERSION=1.9

echo $SEP
echo "Running bootstrap version $BOOTSTRAP_VERSION..."

if [ $BOOTSTRAPPED = TRUE ]; then
  echo "Machine already provisioned, exiting."
  exit 0
fi

# Build profile for all users.
echo $SEP
echo "*** Building profile.d..." 
echo "export PROJECT=\$(curl -sH Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/project/project-id)" >> $PROFILE
echo "export ZONE=\$(curl -sH Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/zone | cut -d/ -f4)" >> $PROFILE
echo "export ORCHESTRATE_HOME=/opt/solutions-cloud-orchestrate" >> $PROFILE
echo "export ORCHESTRATE_VIRTUALENV=/opt/orchestrate" >> $PROFILE
echo "source \$ORCHESTRATE_VIRTUALENV/bin/activate" >> $PROFILE
echo "source /usr/lib/google-cloud-sdk/completion.bash.inc" >> $PROFILE

# Update OS.
echo $SEP
echo "*** Updating OS..."
apt-get update
apt-get install -y git virtualenv python3-pip kubectl \
  software-properties-common unzip acl jq

# Build Cloud Orchestrate environment.
echo $SEP
echo "*** Provisioning $ORCHESTRATE_HOME..."
mkdir --mode=0777 $ORCHESTRATE_HOME
setfacl -Rdm g:adm:rwx $ORCHESTRATE_HOME

# Build Cloud Orchestrate virtualenv.
echo $SEP
echo "*** Provisioning $ORCHESTRATE_VIRTUALENV..."
mkdir --mode=0777 $ORCHESTRATE_VIRTUALENV
setfacl -Rdm g:adm:rwx $ORCHESTRATE_VIRTUALENV
virtualenv -p `which python3` /opt/orchestrate
chgrp -R adm $ORCHESTRATE_VIRTUALENV

# Clone branch.
echo $SEP
echo "*** Cloning $REPO_LOC..."
git clone --branch $BRANCH $REPO_LOC $ORCHESTRATE_HOME
chgrp -R adm $ORCHESTRATE_HOME

# Finally, set metadata, marking machine as complete.
echo "*** Setting instance metadata..."
gcloud compute instances add-metadata $CMD_NAME \
  --metadata bootstrapped=TRUE \
  --zone=$ZONE

DATE=`date`
echo "*** END $0 $DATE ***"
echo $SEP
