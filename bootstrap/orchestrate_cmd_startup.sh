#!/bin/sh -x

# Use this bootstrap script to install and initialize the 
# Cloud Orchestrate API on a Debian 10 VM. It performs
# The following tasks:
#   - Install core API dependencies.
#   - Install Cloud Orchestrate repository.
#   - Build and enter Cloud Orchestrate environment.
#   - Deploy Cloud Orchestrate components.

# TESTS
#  - assert user is Project Owner and 'Compute Network Admin'
#  - assert user can run sudo 

export PROJECT=$(curl -s "http://metadata.google.internal/computeMetadata/v1/project/project-id" -H "Metadata-Flavor: Google")
export ORCHESTRATE_HOME=/opt/solutions-cloud-orchestrate
export LOCAL_REPO_LOC=/opt/orchestrate
export REPO_LOC=https://github.com/GoogleCloudPlatform/solutions-cloud-orchestrate.git

# Build .profile.
echo 'export PROJECT=$(curl -s "http://metadata.google.internal/computeMetadata/v1/project/project-id" -H "Metadata-Flavor: Google")' >> $HOME/.profile
echo "export ORCHESTRATE_HOME=/opt/solutions-cloud-orchestrate" >> $HOME/.profile
echo "export LOCAL_REPO_LOC=/opt/orchestrate" >> $HOME/.profile

# Update OS.
sudo apt-get update
sudo apt-get install -y git virtualenv python3-pip kubectl software-properties-common unzip

#
# Build Cloud Orchestrate environment.
#

mkdir -m 0777 $LOCAL_REPO_LOC
mkdir -m 0777 $ORCHESTRATE_HOME

git clone $REPO_LOC $ORCHESTRATE_HOME
virtualenv -p `which python3` $LOCAL_REPO_LOC
source $REPO_LOC/bin/activate

pip install google google-cloud google-cloud-pubsub google-cloud-error-reporting google-api-python-client grpcio grpcio-tools requests oauth2client setuptools_scm

$ORCHESTRATE_HOME/scripts/set_project.py $PROJECT
