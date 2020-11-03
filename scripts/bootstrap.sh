#!/bin/sh

# Use this bootstrap script to install and initialize the 
# Cloud Orchestrate API on a Debian 10 VM. It performs
# The following tasks:
#   - Install core API dependencies.
#   - Install Cloud Orchestrate repository.
#   - Build and enter Cloud Orchestrate environment.
#   - Deploy Cloud Orchestrate components.

DATE=`date`
echo "*** START $0 $DATE ***"

BRANCH=bootstrap #main

export PROJECT=$(curl -sH Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/project/project-id)
export ZONE=$(curl -sH Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/zone | cut -d/ -f4)
export BOOTSTRAPPED=$(curl -sH Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/attributes/bootstrapped)
export ORCHESTRATE_HOME=/opt/solutions-cloud-orchestrate
export REPO_LOC=https://github.com/GoogleCloudPlatform/solutions-cloud-orchestrate.git
export PROFILE=/etc/profile.d/orchestrate.sh

if [ $BOOTSTRAPPED = TRUE ]; then
  echo "Machine already provisioned, exiting."
  exit 0
fi

# Build profile.d.

echo "*** Building profile.d..." 
echo "export PROJECT=\$(curl -sH Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/project/project-id)" >> $PROFILE
echo "export ZONE=\$(curl -sH Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/zone | cut -d/ -f4)" >> $PROFILE
echo "export ORCHESTRATE_HOME=/opt/solutions-cloud-orchestrate" >> $PROFILE
echo "source /usr/lib/google-cloud-sdk/completion.bash.inc" >> $PROFILE

# Update OS.
echo "*** Updating OS..."
apt-get update
apt-get install -y git python3-pip kubectl software-properties-common unzip acl jq

# Build Cloud Orchestrate environment.
echo "*** Provisioning $ORCHESTRATE_HOME..."
mkdir --mode=0775 $ORCHESTRATE_HOME
setfacl -Rdm g:adm:rw $ORCHESTRATE_HOME

# Clone based on branch.
echo "*** Cloning $REPO_LOC..."
git clone --branch $BRANCH $REPO_LOC $ORCHESTRATE_HOME
chgrp -R adm $ORCHESTRATE_HOME

echo "*** Installing Python libs with pip3..."
pip3 install --upgrade pip
pip3 install google google-cloud google-cloud-pubsub google-cloud-error-reporting google-api-python-client grpcio grpcio-tools requests oauth2client setuptools_scm

echo
echo "$ORCHESTRATE_HOME/scripts/set_project.py $PROJECT"
$ORCHESTRATE_HOME/scripts/set_project.py $PROJECT

echo
echo "$ORCHESTRATE_HOME/project/enable_apis.sh"
$ORCHESTRATE_HOME/project/enable_apis.sh

echo
echo "$ORCHESTRATE_HOME/project/create_buckets.sh"
$ORCHESTRATE_HOME/project/create_buckets.sh

echo
echo "$ORCHESTRATE_HOME/project/create_roles.sh"
$ORCHESTRATE_HOME/project/create_roles.sh

echo
echo "$ORCHESTRATE_HOME/project/create_service_accounts.sh"
$ORCHESTRATE_HOME/project/create_service_accounts.sh

echo
echo "$ORCHESTRATE_HOME/project/create_topics.sh"
$ORCHESTRATE_HOME/project/create_topics.sh

echo
echo "$ORCHESTRATE_HOME/api/bin/create_cluster.sh"
$ORCHESTRATE_HOME/api/bin/create_cluster.sh

echo
echo "$ORCHESTRATE_HOME/scripts/deploy.sh"
$ORCHESTRATE_HOME/scripts/deploy.sh

echo
echo "$ORCHESTRATE_HOME/services/deploy.sh \
  $ORCHESTRATE_HOME/services/image_provisioning_start"
$ORCHESTRATE_HOME/services/deploy.sh \
  $ORCHESTRATE_HOME/services/image_provisioning_start

echo
echo "$ORCHESTRATE_HOME/services/deploy.sh \
  $ORCHESTRATE_HOME/services/image_provisioning_end"
$ORCHESTRATE_HOME/services/deploy.sh \
  $ORCHESTRATE_HOME/services/image_provisioning_end

# Create API Key.
echo "*** Creating API key..."
gcloud alpha services api-keys create \
  --api-target=service=orchestrate.endpoints.$PROJECT.cloud.goog \
  --display-name="Orchestrate API key"

# Query values for config.
echo "*** Getting values for API key..."
KEY=`gcloud alpha services api-keys list --format=json --filter=displayName:"Orchestrate API" | jq -r '.[0].name'`
API_KEY=`gcloud alpha services api-keys get-key-string --format=json $KEY | jq -r '.keyString'`
LB_IP=$($ORCHESTRATE_HOME/api/bin/get_api_url.sh)

# Build .config file.
echo "*** Building Orchestrate .config file..."
mkdir -p /etc/skel/.config/orchestrate
cat << EOF > /etc/skel/.config/orchestrate/config_default
[api]
project = $PROJECT
host = $LB_IP
key = $API_KEY
EOF

echo "*** Compileing protos..."
$ORCHESTRATE_HOME/bin/compile_protos.sh
cd $ORCHESTRATE_HOME/cli
python setup.py develop

echo "*** Registering project..."
orchestrate projects register

# Finally, set metadata, marking machine as complete.
echo "*** Setting instance metadata..."
gcloud compute instances add-metadata orchestrate-cmd \
  --metadata bootstrapped=TRUE \
  --zone=$ZONE

DATE=`date`
echo "*** END $0 $DATE ***"
