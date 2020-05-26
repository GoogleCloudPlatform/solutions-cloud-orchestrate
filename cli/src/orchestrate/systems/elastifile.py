# python3
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

"""Deploy Elastifile cluster.
"""

import logging
import tempfile
from orchestrate import base


log = logging.getLogger(__name__)


class Elastifile(base.OrchestrateSystem):
  """Deploy Elastifile cluster."""

  def __init__(self):
    super(Elastifile, self).__init__()
    # Network
    self.network = 'elastifile'
    self.cidr = '172.16.0.0/24'
    self.ip = '172.16.255.1'
    self.volumes = 'projects:/projects/root|tools:/tools/root'

    # Admin
    self.email = 'elastifile@example.com'

    # Overrides
    self.git_url = 'https://github.com/Elastifile/gcp-automation.git'

  @property
  def description(self):
    return """Deploys an Elastifile cluster."""

  def run(self):
    """Executes system deployment.

    Returns:
      True if successful. False, otherwise.
    """
    log.info('Deploying Elastifile')

    self.create_vpc()
    self.create_firewall_rules()

    roles = """
roles/compute.instanceAdmin.v1
roles/compute.networkAdmin
roles/compute.securityAdmin
roles/iam.serviceAccountUser
roles/iam.serviceAccountUser
roles/storage.admin
roles/storage.objectAdmin
""".strip().split()
    self.create_service_account(roles)
    self.create_service_account_key()

    self.install_terraform()
    self.configure_terraform()
    self.apply_terraform()

    self.remove_service_account_key()

  def configure(self):
    """Configure."""
    self.region = '-'.join(self.zone.split('-')[:-1])

    if self.prefix:
      self.prefix += '-'

    self.network = self.prefix + self.network

    self.first_volume = self.volumes.split('|')[0].split(':')[0]

    if self.deploy_dir:
      command = 'mkdir -p {self.deploy_dir}'.format(self=self)
      self.run_command(command)
    else:
      self.deploy_dir = tempfile.mkdtemp(
          prefix='orchestrate-{self.project}-{self.name}-'.format(self=self),
          dir='/var/tmp',
          )

    self.service_account_name = 'elastifile'
    self.service_account_display_name = 'Elastifile cluster'
    self.service_account = (
        '{self.service_account_name}@{self.project}.iam.gserviceaccount.com'
    ).format(self=self)
    self.credentials_file = (
        '{self.deploy_dir}/{self.project}-{self.service_account_name}.json'
    ).format(self=self)

    self.terraform_dir = '{self.deploy_dir}/{self.name}'.format(self=self)
    self.terraform_deployment_dir = self.terraform_dir

  def create_vpc(self):
    """Create VPC networks."""
    log.info('Creating VPC networks')
    command = (
        'gcloud compute networks create {self.network}'
        '  --project={self.project}'
        '  --subnet-mode=custom'
        ).format(self=self)
    self.run_command(command)

    command = (
        'gcloud compute networks subnets create {self.network}'
        '  --project={self.project}'
        '  --network={self.network}'
        '  --range={self.cidr}'
        '  --region={self.region}'
        '  --enable-flow-logs'
        '  --enable-private-ip-google-access'
        ).format(self=self)
    self.run_command(command)

  def create_firewall_rules(self):
    """Create firewall rules."""
    log.info('Creating firewall rules')
    command = (
        'gcloud compute firewall-rules create {self.network}-elastifile'
        '  --project={self.project}'
        '  --network={self.network}'
        '  --allow=tcp:22,tcp:80,tcp:443'
        '  --enable-logging'
        '  --priority=1000'
        ).format(self=self)
    self.run_command(command)

  def get_terraform_configuration(self):
    """Returns string with the contents of the tfvars to write."""
    log.info('Configuring Terraform')
    return """
# Contact info - No spaces allowed
COMPANY_NAME = "Google"
CONTACT_PERSON_NAME = "Orchestrate"
EMAIL_ADDRESS = "{self.email}"

# Cluster info
PROJECT = "{self.project}"
CLUSTER_NAME = "{self.network}"
NETWORK = "{self.network}"
SUBNETWORK = "{self.network}"
REGION = "{self.region}"
EMS_ZONE = "{self.zone}"
NUM_OF_VMS = "3"                # number of vheads exclusive of EMS
VM_CONFIG = "4_60"              # format: <cpucores>_<ram> default: 4_42
DISK_TYPE = "persistent"        # types: local, persistent, hdd
DISK_CONFIG = "4_1000"          # format: <num_of_disks>_<disk_size>

# Template types:
# "small", "medium", "medium-plus", "large",
# "standard", "small standard",
# "local", "small local",
# "custom"
TEMPLATE_TYPE = "small"

# GCP service account credential filename
CREDENTIALS = "{self.credentials_file}"
SERVICE_EMAIL = "{self.service_account}"

# Load balancer
LB_TYPE = "elastifile"          # types: none, dns, elastifile, google
LB_VIP = "{self.ip}"            # "auto" or IP address, e.g. "172.16.255.1"
USE_PUBLIC_IP = true
DEPLOYMENT_TYPE = "single"      # types: single, dual, multizone
# availability zones for multi-zone selection, e.g.: us-central1-a,us-central1-b
NODES_ZONES = "{self.zone}"

# Name first data container and shared volume, e.g. data and /data/root
DATA_CONTAINER = "{self.first_volume}"

# Advanced
EMS_ONLY = "false"
SETUP_COMPLETE = "false"        # false for initial deployment, true to add/remove nodes
ILM = "false"                   # Clear Tier
ASYNC_DR = "false"
KMS_KEY = ""                    # customer managed encryption key

# Elastifile image version
IMAGE = "elastifile-storage-3-1-0-31-ems"
IMAGE_PROJECT = "elastifle-public-196717"
""".lstrip().format(self=self)
