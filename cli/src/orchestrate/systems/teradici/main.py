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

"""Deploy Teradici Cloud Access Software including broker and security gateway.
"""

import json
import logging
import os
import tempfile
from . import camapi
from orchestrate import base


log = logging.getLogger(__name__)


class InvalidConfigurationError(Exception):
  """Indicate errors with provided parameters."""
  pass


class CloudAccessSoftware(base.OrchestrateSystem):
  """Deploy Teradici CAS."""

  def __init__(self):
    super(CloudAccessSoftware, self).__init__()
    # Active Directory
    self.domain = 'cloud.demo'
    self.users_file = ''

    # CAM
    self.registration_code = None
    self.deployment_type = 'multi-region'
    self.deployment_name = None
    self.connector_name = None

    # SSH
    self.public_ssh_key_file = None

    # Network
    self.network = 'workstations'
    self.subnetwork = self.network
    self.workstations_cidr = '10.0.0.0/20'
    self.controller_cidr = '10.0.240.0/21'
    self.controller_ip = '10.0.240.2'
    self.connector_cidr = '10.0.248.0/21'

    # Connectors
    # region:instances:cidr|region:instances:cidr
    # us-west2-b:1:10.0.0.0/24|us-east4-b:1:10.0.0.0/24
    self.connectors = 'us-west2-b:1:10.0.232.0/21|us-east4-b:1:10.0.224.0/21'

    # Windows workstations
    self.windows_instance_count = 0
    self.windows_instance_name = 'win'
    self.windows_image = 'projects/windows-cloud/global/images/family/windows-2019'
    self.windows_disk_size = 200
    self.windows_machine_type = 'n1-standard-8'
    self.windows_accelerator_type = None
    self.windows_accelerator_count = 1

    # Overrides
    self.git_url = 'https://github.com/teradici/cloud_deployment_scripts'
    self.git_branch = 'master'
    self.deploy_dir = ''
    self.terraform_version = '0.12.7'

  @property
  def description(self):
    return """Deploys Teradici CAS along with a standalone Active Directory."""

  def run(self):
    """Executes system deployment.

    Returns:
      True if successful. False, otherwise.
    """
    log.info('Deploying Teradici CAS')

    self.enable_apis()
    self.create_connector_token()
    self.create_ssh_keys()

    roles = """
roles/editor
roles/cloudkms.cryptoKeyEncrypterDecrypter
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

    self.terraform_version = '0.12.7'

    self.users_file = os.path.expanduser(self.users_file)

    if self.deploy_dir:
      self.deploy_dir = os.path.expanduser(self.deploy_dir)
      command = 'mkdir -p {self.deploy_dir}'.format(self=self)
      self.run_command(command)
    else:
      self.deploy_dir = directory = tempfile.mkdtemp(
          prefix='orchestrate-{self.project}-{self.name}-'.format(self=self),
          dir='/var/tmp',
          )

    self.service_account_name = 'teradici'
    self.service_account_display_name = 'Teradici CAS'
    self.service_account = (
        '{self.service_account_name}@{self.project}.iam.gserviceaccount.com'
    ).format(self=self)
    self.credentials_file = (
        '{self.deploy_dir}/{self.project}-{self.service_account_name}.json'
    ).format(self=self)

    self.terraform_dir = '{self.deploy_dir}/{self.name}'.format(self=self)
    self.terraform_deployment_dir = (
        '{self.terraform_dir}/deployments/gcp/{self.deployment_type}'
        ).format(self=self)

    if not self.public_ssh_key_file:
      self.public_ssh_key_file = (
          '{self.deploy_dir}/{self.project}-{self.service_account_name}'
          ).format(self=self)

    self.connector_token = None

    if self.windows_accelerator_type is None:
      if self.region in ['us-west2', 'us-east4', 'northamerica-northeast1']:
        self.windows_accelerator_type = 'nvidia-tesla-p4-vws'
      else:
        self.windows_accelerator_type = 'nvidia-tesla-t4-vws'

    if not self.domain or len(self.domain.split('.')) < 2:
      message = (
          'The AD domain {domain} is not valid. Please provide one that is'
          ' composed of at least two parts separated by a dot, e.g. cloud.demo'
          ).format(domain=self.domain)
      raise InvalidConfigurationError(message)

    self.connector_regions = []
    self.connector_zones = []
    self.connector_cidrs = []
    self.connector_instances = []
    if self.connectors:
      connectors = self.connectors.split('|')
      for connector in connectors:
        parts = connector.split(':')
        zone, instances, cidr = parts
        region = '-'.join(zone.split('-')[:-1])
        self.connector_regions.append(region)
        self.connector_zones.append(zone)
        self.connector_cidrs.append(cidr)
        self.connector_instances.append(instances)

  def create_connector_token(self):
    """Create a CAM connector token for the deployment."""
    log.info('Creating connector token')
    deployment_name = self.deployment_name
    if not deployment_name:
      if self.prefix:
        deployment_name = '{}-{}'.format(self.project, self.prefix)
      else:
        deployment_name = self.project
    connector_name = self.connector_name or self.prefix or self.zone
    log.info('deployment: %s', deployment_name)
    log.info('connector : %s', connector_name)
    if self.dry_run:
      log.info('DRY-RUN get_connector_token')
      self.connector_token = None
      return
    self.connector_token = self.get_connector_token(
        deployment_name,
        connector_name,
        self.registration_code,
        )

  def get_connector_token(self, deployment_name, connector_name,
                          registration_code):
    """Returns a valid token for a Teradici CAM connector.

    Args:
      deployment_name:
      connector_name:
      registration_code:
    """
    cam = camapi.CloudAccessManager(project=self.project,
                                    deployment=deployment_name)

    # Get or create Deployment
    deployment = cam.deployments.get(deployment_name)
    if not deployment:
      deployment = cam.deployments.post(deployment_name, registration_code)

    # Get an authorization token for the connector that the broker will use
    connector_token = cam.auth.tokens.connector.post(deployment, connector_name)
    return connector_token

  def enable_apis(self):
    """Enable APIs."""
    log.info('Enabling APIs')
    command = (
        'gcloud services enable'
        ' cloudkms.googleapis.com'
        ' cloudresourcemanager.googleapis.com'
        ' compute.googleapis.com'
        ' dns.googleapis.com'
        ' deploymentmanager.googleapis.com'
        )
    self.run_command(command)

  def create_ssh_keys(self):
    """Create SSH keys."""
    log.info('Generating SSH keys')
    if not os.path.exists(self.public_ssh_key_file):
      command = 'ssh-keygen -f {self.public_ssh_key_file} -t rsa -q -N ""'.format(
          self=self,
          )
      self.run_command(command)
    else:
      log.info('Reusing existing SSH key at %s', self.public_ssh_key_file)

  def get_terraform_configuration(self):
    """Returns string with the contents of the tfvars to write."""
    log.info('Configuring Terraform')
    main = """
# Project
gcp_credentials_file = "{self.credentials_file}"
gcp_project_id       = "{self.project}"
gcp_service_account  = "{self.service_account}"
gcp_region           = "{self.region}"
gcp_zone             = "{self.zone}"

# Networking
vpc_name             = "{self.network}"
workstations_network = "{self.subnetwork}"
controller_network   = "controller"
connector_network    = "connector"
dc_subnet_cidr       = "{self.controller_cidr}"
dc_private_ip        = "{self.controller_ip}"
cac_subnet_cidr      = "{self.connector_cidr}"
ws_subnet_cidr       = "{self.workstations_cidr}"

# 20200521 Shared-VPC single subnet case
# Is this the right variable name moving forward?
# Should this be the same as workstations_network?
subnet_name          = "{self.subnetwork}"

# Domain
prefix               = "{self.prefix}"
domain_name          = "{self.domain}"
domain_users_list    = "{self.users_file}"

# Access
cac_token                     = "{self.connector_token}"
cac_admin_ssh_pub_key_file    = "{self.public_ssh_key_file}"
centos_admin_ssh_pub_key_file = "{self.public_ssh_key_file}"
dc_admin_password           = "SecuRe_pwd1"
safe_mode_admin_password    = "SecuRe_pwd2"
ad_service_account_password = "SecuRe_pwd3"

# License
pcoip_registration_code  = "{self.registration_code}"

# Workstations
win_gfx_instance_count = {self.windows_instance_count}
win_gfx_instance_name = "{self.windows_instance_name}"
win_gfx_disk_image = "{self.windows_image}"
win_gfx_disk_size_gb = {self.windows_disk_size}
win_gfx_machine_type = "{self.windows_machine_type}"
win_gfx_accelerator_type = "{self.windows_accelerator_type}"
win_gfx_accelerator_count = {self.windows_accelerator_count}

centos_gfx_instance_count = 0
""".lstrip().format(self=self)

    connectors = ''
    if self.connectors:
      connectors = """
# Connectors
cac_region_list         = {connector_regions}
cac_zone_list           = {connector_zones}
cac_subnet_cidr_list    = {connector_cidrs}
cac_instance_count_list = {connector_instances}
""".lstrip().format(
    # We need to do this because Terraform only accepts double quotes, and
    # the Python format function uses single-quotes (as it should)
    connector_regions=json.dumps(self.connector_regions),
    connector_zones=json.dumps(self.connector_zones),
    connector_cidrs=json.dumps(self.connector_cidrs),
    connector_instances=json.dumps(self.connector_instances),
    )

    return main + connectors
