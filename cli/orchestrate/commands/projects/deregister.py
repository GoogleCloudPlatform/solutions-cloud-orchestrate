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

r"""Deregisters a project from Orchestrate orchestration.

Usage: orchestrate projects deregister [OPTIONS]
"""

import logging
import subprocess

from orchestrate import base
from orchestrate.service.orchestrate_pb2 import DeregisterProjectRequest

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
Removes service accounts, roles and permissions for Orchestrate orchestration.
""".lstrip()

  def run(self, options, arguments):
    """Executes command.

    Args:
      options: Command-line options.
      arguments: Command-line positional arguments

    Returns:
      True if successful. False, otherwise.
    """
    log.debug('projects deregister %(options)s %(arguments)s', dict(
        options=options, arguments=arguments))

    if arguments:
      log.error('Received unexpected arguments.')
      return False

    self.remove_configuration(options)
    self.deregister(options)

    return True

  def remove_configuration(self, options):
    """Removes configuration from project to stop Orchestrate orchestration.

    The following configuration changes are applied to the project:
    On project PROJECT_ID:
    - Revoke orchestrate@ORCHESTRATE_PROJECT service account roles:
      - Orchestrate DevOps
      - Service Account User
    - Delete orchestrate@PROJECT_ID service account

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
    orchestrate_account = 'orchestrate@{project}.iam.gserviceaccount.com'.format(
        project=options.api_project)
    project_account = 'orchestrate@{project}.iam.gserviceaccount.com'.format(
        project=options.project)
    commands = """
gcloud projects remove-iam-policy-binding {project} --member="serviceAccount:{orchestrate_account}" --role="projects/{project}/roles/orchestrate.devOps"
gcloud projects remove-iam-policy-binding {project} --member="serviceAccount:{orchestrate_account}" --role="roles/iam.serviceAccountUser"
gcloud projects remove-iam-policy-binding {project} --member="serviceAccount:{project_account}" --role="roles/iam.serviceAccountUser"
gcloud iam service-accounts delete {project_account} --project={project}
""".format(
    project=options.project,
    orchestrate_account=orchestrate_account,
    project_account=project_account,
    ).strip().split('\n')
    run_commands(commands)

  def deregister(self, options):
    """Deregisters project from the main Orchestrate project.

    Project configuration needs to be removed first. See `remove_configuration`.

    Args:
      options: Command-line options.
    """
    request = DeregisterProjectRequest(
        project=options.project,
    )

    response = self.execute('DeregisterProject', request, options)
    log.info('Response: status=%(status)s request_id=%(request_id)s', dict(
        status=response.status,
        request_id=response.request_id,
        ))
