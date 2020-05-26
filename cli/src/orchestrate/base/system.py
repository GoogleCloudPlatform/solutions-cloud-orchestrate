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

"""Base Orchestrate system interface.
"""

import json
import logging
import os
import subprocess


log = logging.getLogger(__name__)


class OrchestrateSystem:
  """Orchestrate system deployment interface."""

  def __init__(self):
    # Basic deployment info
    self.name = None
    self.project = None
    self.region = None
    self.zone = None
    self.prefix = ''
    self.dry_run = False
    self.deploy_dir = ''
    self.others = dict()

    # Service account
    self.service_account = None
    self.service_account_name = None
    self.service_account_display_name = None
    self.credentials_file = None

    # Terraform
    self.git_url = None
    self.git_branch = 'master'
    self.terraform_version = '0.11.11'
    self.terraform_binary = None
    self.terraform_dir = ''
    self.terraform_deployment_dir = ''

  @property
  def description(self):
    raise NotImplementedError()

  @property
  def options(self):
    """Returns list of supported options."""
    excluded = ['others']
    return [name.replace('_', '-') for name in vars(self)
            if name not in excluded]

  @property
  def defaults(self):
    """Returns default option values."""
    return vars(self)

  @property
  def usage(self):
    """Returns details on how to invoke the deployment of this system.
    """
    formatted_options = []
    for option in self.options:
      default = self.defaults.get(option.replace('-', '_'))
      formatted_option = '  --{option:30} {default}'.format(
          option=option,
          default=default,
          )
      formatted_options.append(formatted_option)

    usage = """
Usage:
  {description}

Options:
{options}
""".format(
    description=self.description,
    options='\n'.join(formatted_options),
    )

    return usage

  def run(self, options):
    """Executes system deployment.

    Args:
      options: Command-line options for all systems organized by system name.

    Returns:
      True if successful. False, otherwise.
    """
    raise NotImplementedError()

  def create_service_account(self, roles):
    """Create a service account.

    Args:
      roles: List of roles to assign to service account.
    """
    log.info('Setting up service account and roles')
    command = (
        'gcloud iam service-accounts create {self.service_account_name}'
        '  --project={self.project}'
        '  --display-name="{self.service_account_display_name}"'
        ).format(self=self)
    self.run_command(command)

    for role in roles:
      log.info('Role: %s', role)
      command = (
          'gcloud projects add-iam-policy-binding {self.project}'
          '  --member="serviceAccount:{self.service_account}"'
          '  --role={role}'
          ).format(
              self=self,
              role=role,
              )
      self.run_command(command)

  def create_service_account_key(self):
    """Download the service account key to a file."""
    log.info('Generating service account key')
    command = (
        'gcloud iam service-accounts keys create {self.credentials_file}'
        '  --project={self.project}'
        '  --iam-account="{self.service_account}"'
        ).format(self=self)
    self.run_command(command)

  def install_terraform(self):
    """Install Terraform."""
    log.info('Installing Terraform')

    terraform_url = 'https://releases.hashicorp.com/terraform'
    terraform_zip_file = 'terraform_{self.terraform_version}_linux_amd64.zip'.format(
        self=self,
        )
    command = (
        'curl -o {self.deploy_dir}/{terraform_zip_file}'
        ' {terraform_url}/{self.terraform_version}/{terraform_zip_file}'
        ).format(
            self=self,
            terraform_url=terraform_url,
            terraform_zip_file=terraform_zip_file,
            )
    self.run_command(command)

    self.terraform_binary = '{self.deploy_dir}/terraform'.format(self=self)
    if not os.path.exists(self.terraform_binary):
      command = (
          'unzip {self.deploy_dir}/{terraform_zip_file}'
          ' -d {self.deploy_dir}'
          ).format(
              self=self,
              terraform_zip_file=terraform_zip_file,
              )
      self.run_command(command)
    else:
      log.info('Using existing terraform binary at %s', self.terraform_binary)

  def clone_terraform_repository(self):
    """Create Terraform configuration file."""
    log.info('Configuring Terraform')
    if not os.path.exists(self.terraform_dir):
      log.info('Cloning repository')
      command = (
          'git clone --branch {self.git_branch} {self.git_url}'
          ' {self.terraform_dir}'
          ).format(self=self)
      self.run_command(command)
    else:
      log.info('Pulling latest from repository')
      self.run_command('git pull', cwd=self.terraform_dir)

  def configure_terraform(self):
    """Writes contents of the tfvars to disk."""
    self.clone_terraform_repository()
    configuration = self.get_terraform_configuration()
    self.write_terraform_configuration(configuration)

  def get_terraform_configuration(self):
    """Returns string with the contents of the tfvars to write."""
    raise NotImplementedError()

  def write_terraform_configuration(self, configuration):
    """Write Terraform configuration file.

    Args:
      configuration: String with the contents of the tfvars file to write.
    """
    file_name = '{self.terraform_deployment_dir}/terraform.tfvars'.format(
        self=self,
        )
    if not self.dry_run:
      with open(file_name, 'w') as output_file:
        output_file.write(configuration)

  def apply_terraform(self):
    """Apply Terraform deployment."""
    log.info('Deploying with Terraform')
    command = self.terraform_binary + ' init'
    self.run_command(command, cwd=self.terraform_deployment_dir)
    command = self.terraform_binary + ' apply -auto-approve'
    self.run_command(command, cwd=self.terraform_deployment_dir)

  def remove_service_account_key(self):
    """Remove file containing service account key."""
    log.info('Removing service account key')
    if not self.dry_run:
      with open(self.credentials_file, 'r') as input_file:
        credentials = json.load(input_file)
        private_key_id = credentials['private_key_id']
    else:
      private_key_id = 'PRIVATE_KEY_ID'
    command = (
        'gcloud iam service-accounts keys delete {private_key_id}'
        '  --project={self.project}'
        '  --iam-account="{self.service_account}"'
        '  --quiet'
        ).format(
            self=self,
            private_key_id=private_key_id,
            )
    self.run_command(command)
    command = 'rm -f {self.credentials_file}'.format(self=self)
    self.run_command(command)

  def run_command(self, command, pii=False, cwd=None):
    """Runs given system command.

    Args:
      command: Command to run.
      pii: Logs command redacted to prevent any PII from leaking in plain text.
           By default it logs the command verbatim. Please make sure to set this
           to True if the command being executed contains passwords or any other
           sensitive information.
      cwd: Change directory to this if not None.
    """
    message = command if not pii else '[redacted due to pii]'
    if self.dry_run:
      log.info('DRY-RUN: %s', message)
    else:
      log.debug('Executing: %s', message)
      subprocess.call(command, shell=True, cwd=cwd)
