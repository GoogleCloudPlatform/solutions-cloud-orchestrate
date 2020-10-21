#!/bin/sh

# Use this bootstrap script to install and initialize the 
# Cloud Orchestrate API on a Debian 10 VM. It performs
# The following tasks:
#   - Install core API dependencies.
#   - Install Cloud Orchestrate repository.
#   - Build and enter Cloud Orchestrate environment.
#   - Deploy Cloud Orchestrate components.

export PROJECT=$(curl -sH Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/project/project-id)
export ZONE=$(curl -sH Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/zone | cut -d/ -f4)
export BOOTSTRAPPED=$(curl -sH Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/attributes/bootstrapped)
export ORCHESTRATE_HOME=/opt/solutions-cloud-orchestrate
#export VIRTUALENV=/opt/orchestrate
export REPO_LOC=https://github.com/GoogleCloudPlatform/solutions-cloud-orchestrate.git

if [ $BOOTSTRAPPED = TRUE ]; then
  echo "Machine already provisioned, exiting."
  exit 0
fi

# Build .profile.
echo "export PROJECT=$(curl -sH Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/project/project-id)" >> /etc/skel/.profile
echo "export ZONE=$(curl -sH Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/zone | cut -d/ -f4)" >> /etc/skel/.profile
echo "export ORCHESTRATE_HOME=/opt/solutions-cloud-orchestrate" >> /etc/skel/.profile
#echo "export VIRTUALENV=/opt/orchestrate" >> /etc/skel/.profile

# Update OS.
sudo apt-get update
sudo apt-get install -y git python3-pip kubectl software-properties-common unzip

#
# Build Cloud Orchestrate environment.
#

#mkdir -m 0777 $VIRTUALENV
mkdir -m 0777 $ORCHESTRATE_HOME

# TEMP: clone 'bootstrap' branch.
git clone --branch bootstrap $REPO_LOC $ORCHESTRATE_HOME
#virtualenv -p `which python3` $VIRTUALENV
#source $REPO_LOC/bin/activate

pip3 install --upgrade pip
pip3 install google google-cloud google-cloud-pubsub google-cloud-error-reporting google-api-python-client grpcio grpcio-tools requests oauth2client setuptools_scm

$ORCHESTRATE_HOME/scripts/set_project.py $PROJECT
#$ORCHESTRATE_HOME/project/enable_apis.sh
#$ORCHESTRATE_HOME/project/create_buckets.sh
#$ORCHESTRATE_HOME/project/create_roles.sh
#$ORCHESTRATE_HOME/project/create_service_accounts.sh
#$ORCHESTRATE_HOME/project/create_topics.sh

# Finally, set metadata, marking machine as complete.
gcloud compute instances add-metadata orchestrate-cmd \
  --metadata bootstrapped=TRUE \
  --zone=$ZONE
