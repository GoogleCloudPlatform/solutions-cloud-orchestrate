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

r"""Registers a project so that Orchestrate can orchestrate its resources.

Usage: orchestrate projects register [OPTIONS]
"""

import logging
import subprocess

from orchestrate import base
from orchestrate.service.orchestrate_pb2 import RegisterProjectRequest

log = logging.getLogger(__name__)


def run(command, pii=False):
  """Runs given system command.

  Args:
    command: Command to run.
    pii: Logs command redacted to prevent any PII from leaking in plain text.
         By default it logs the command verbatim. Please make sure to set this
         to True if the command being executed contains passwords or any other
         sensitive information.
  """
  message = command if not pii else '[redacted due to pii]'
  log.debug('Executing: %(message)s', dict(message=message))
  subprocess.call(command, shell=True)


def run_commands(commands, pii=False):
  """Runs given list of system commands.

  Args:
    commands: List of commands to run.
    pii: Logs command redacted to prevent any PII from leaking in plain text.
         By default it logs the command verbatim. Please make sure to set this
         to True if the command being executed contains passwords or any other
         sensitive information.
  """
  for command in commands:
    run(command, pii=pii)


class Command(base.OrchestrateCommand):
  """Sets up service accounts, roles and permissions for Orchestrate orchestration.
  """

  @property
  def description(self):
    return """
Sets up service accounts, roles and permissions for Orchestrate orchestration.
""".lstrip()

  def run(self, options, arguments):
    """Executes command.

    Args:
      options: Command-line options.
      arguments: Command-line positional arguments

    Returns:
      True if successful. False, otherwise.
    """
    log.debug('projects register %(options)s %(arguments)s', dict(
        options=options, arguments=arguments))

    if arguments:
      log.error('Received unexpected arguments.')
      return False

    self.configure(options)
    self.register(options)

    return True

  def configure(self, options):
    """Configures project to be orchestrated by the main Orchestrate project.

    The following configuration changes are applied to the project:
    On project PROJECT_ID:
    - Create Orchestrate custom roles:
      - roles/orchestrate.devOps
      - roles/orchestrate.resourceManager
      - roles/orchestrate.user
    - Enable APIs:
      - compute engine
      - pubsub
      - cloud resource manager
    - Grant orchestrate@ORCHESTRATE_PROJECT service account roles:
      - Orchestrate DevOps
      - Service Account User
    - Create orchestrate@PROJECT_ID service account
    - Grant orchestrate@PROJECT_ID service account roles:
      - Service Account User
      - Logs Writer
      - Monitoring Metric Writer

    Args:
      options: Command-line options.
    """
    #
    # TODO(lartola) These operations are performed on the client side using
    # gcloud to make sure that the user running it has enough admin permissions
    # to perform them. If these were to be executed by Orchestrate in the API
    # backend, they would be performed under the Orchestrate service account.
    # Perhaps it is ok to do this in the backend, but at this point it seems
    # preferable to know that the user registering the project is indeed a
    # trusted admin of the project.
    #
    self.configure_roles(options)
    orchestrate_account = 'orchestrate@{project}.iam.gserviceaccount.com'.format(
        project=options.api_project)
    project_account = 'orchestrate@{project}.iam.gserviceaccount.com'.format(
        project=options.project)
    commands = """
gcloud services enable compute.googleapis.com --project={project}
gcloud services enable pubsub.googleapis.com --project={project}
gcloud services enable cloudresourcemanager.googleapis.com --project={project}
gcloud services enable dns.googleapis.com --project={project}
gcloud projects add-iam-policy-binding {project} --member="serviceAccount:{orchestrate_account}" --role="projects/{project}/roles/orchestrate.devOps"
gcloud projects add-iam-policy-binding {project} --member="serviceAccount:{orchestrate_account}" --role="roles/iam.serviceAccountUser"
gcloud iam service-accounts create orchestrate --display-name="Orchestrate project-level orchestration service account." --project={project}
gcloud projects add-iam-policy-binding {project} --member="serviceAccount:{project_account}" --role="roles/iam.serviceAccountUser"
gcloud projects add-iam-policy-binding {project} --member="serviceAccount:{project_account}" --role="roles/logging.logWriter"
gcloud projects add-iam-policy-binding {project} --member="serviceAccount:{project_account}" --role="roles/monitoring.metricWriter"
""".format(
    project=options.project,
    orchestrate_account=orchestrate_account,
    project_account=project_account,
    ).strip().split('\n')
    run_commands(commands)

  def configure_roles(self, options):
    """Creates or updates Orchestrate roles in the project.

    Args:
      options: Command-line options
    """
    roles = [
        {
            'name': 'orchestrate.devOps',
            'title': 'Orchestrate DevOps',
            'description': (
                'Orchestrate the creation and lifecycle of all resources'
                ' available to and created by users.'
                ),
            'includedPermissions': [
                'compute.acceleratorTypes.list',
                'compute.images.list',
                'compute.images.get',
                'compute.images.create',
                'compute.images.delete',
                'compute.images.getFromFamily',
                'compute.images.useReadOnly',
                'compute.instanceTemplates.list',
                'compute.instanceTemplates.get',
                'compute.instanceTemplates.create',
                'compute.instanceTemplates.delete',
                'compute.instances.list',
                'compute.instances.get',
                'compute.instances.create',
                'compute.instances.delete',
                'compute.instances.setDeletionProtection',
                'compute.instances.setLabels',
                'compute.instances.setMetadata',
                'compute.instances.setServiceAccount',
                'compute.instances.setTags',
                'compute.instances.stop',
                'compute.disks.create',
                'compute.disks.useReadOnly',
                'compute.networks.get',
                'compute.networks.addPeering',
                'compute.networks.updatePolicy',
                'compute.subnetworks.get',
                'compute.subnetworks.use',
                'compute.subnetworks.useExternalIp',
                'compute.globalOperations.get',
                'compute.regionOperations.get',
                'compute.zoneOperations.get'
            ],
            'stage': 'ALPHA'
        },
        {
            'name': 'orchestrate.resourceManager',
            'title': 'Orchestrate Resource Manager',
            'description': (
                'Create instance templates, instances, and manage the lifecycle'
                ' of resources created by users.'
                ),
            'includedPermissions': [
                'compute.acceleratorTypes.list',
                'compute.images.list',
                'compute.images.get',
                'compute.images.create',
                'compute.images.delete',
                'compute.images.getFromFamily',
                'compute.images.useReadOnly',
                'compute.instanceTemplates.list',
                'compute.instanceTemplates.get',
                'compute.instanceTemplates.create',
                'compute.instanceTemplates.delete',
                'compute.instances.list',
                'compute.instances.get',
                'compute.instances.create',
                'compute.instances.delete',
                'compute.instances.setLabels',
                'compute.instances.setMetadata',
                'compute.instances.setServiceAccount',
                'compute.instances.setTags',
                'compute.instances.stop',
                'compute.disks.create',
                'compute.subnetworks.use',
                'compute.subnetworks.useExternalIp'
            ],
            'stage': 'ALPHA'
        },
        {
            'name': 'orchestrate.user',
            'title': 'Orchestrate User',
            'description': (
                'Create instances and do basic lifecycle management of'
                ' resources they own.'
                ),
            'includedPermissions': [
                'compute.instanceTemplates.list',
                'compute.instanceTemplates.get',
                'compute.instances.list',
                'compute.instances.get',
                'compute.instances.create',
                'compute.instances.delete',
                'compute.instances.setDeletionProtection',
                'compute.instances.setLabels',
                'compute.instances.setMetadata',
                'compute.instances.setServiceAccount',
                'compute.instances.setTags',
                'compute.instances.stop',
                'compute.disks.create',
                'compute.subnetworks.use',
                'compute.subnetworks.useExternalIp'
            ],
            'stage': 'ALPHA'
        }
    ]
    for role in roles:
      permissions = ','.join(role['includedPermissions'])
      try:
        # Try to create first
        command = (
            'gcloud iam roles create {name} --project={project}'
            ' --title="{title}" --description="{description}"'
            ' --permissions={permissions} --stage={stage}').format(
                project=options.project,
                permissions=permissions,
                **role,
                )
        log.debug(command)
        subprocess.check_call(command, shell=True)
      except subprocess.CalledProcessError as exception:
        # if it fails, then try to update
        command = (
            'gcloud iam roles update {name} --project={project}'
            ' --title="{title}" --description="{description}"'
            ' --permissions={permissions} --stage={stage}').format(
                project=options.project,
                permissions=permissions,
                **role,
                )
        run(command)

  def register(self, options):
    """Registers project with main Orchestrate project.

    Project needs to be configured first. See `configure`.

    Args:
      options: Command-line options.
    """
    request = RegisterProjectRequest(
        project=options.project,
    )

    response = self.execute('RegisterProject', request, options)
    log.info('Response: status=%(status)s request_id=%(request_id)s', dict(
        status=response.status,
        request_id=response.request_id,
        ))
