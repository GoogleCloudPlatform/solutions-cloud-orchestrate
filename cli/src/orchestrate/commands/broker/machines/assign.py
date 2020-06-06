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

r"""Assign machines to users in connection broker.

Usage: orchestrate broker machines assign <MACHINE> <USER1>[ <USER2>[ ...]]
"""

import logging
import optparse
import requests.exceptions

from orchestrate import base
from orchestrate.systems.teradici import camapi

log = logging.getLogger(__name__)


class Command(base.OrchestrateCommand):
  """Assign machines to users in connection broker.
  """

  @property
  def description(self):
    return """
Assign machines to users in connection broker.

Usage: orchestrate broker machines assign <DEPLOYMENT> <MACHINE> <USER1>[ <USER2>[ ...]]
""".lstrip()

  @property
  def defaults(self):
    """Returns default option values."""
    return dict(
        deployment=None,
        )

  @property
  def options(self):
    """Returns command parser options."""
    options = [
        optparse.Option('--deployment', help=(
            'Deployment name. Uses project name by default if not explicitly'
            ' provided')),
        ]
    return options

  def run(self, options, arguments):
    """Executes command.

    Args:
      options: Command-line options.
      arguments: Command-line positional arguments

    Returns:
      True if successful. False, otherwise.
    """
    log.debug('broker machines assign %(options)s %(arguments)s', dict(
        options=options, arguments=arguments))

    if len(arguments) < 2:
      log.error('Expected machine name and at least one user name.')
      return False

    if not options.zone:
      log.error(
          'Please provide --zone explicitly, or set the default zone via'
          ' gcloud config set-value compute/zone'
          )
      return False

    machine_name = arguments[0]
    user_names = arguments[1:]
    deployment_name = options.deployment or options.project

    self.assign(options.project, options.zone, deployment_name, machine_name,
                user_names)

  def assign(self, project, zone, deployment_name, machine_name, user_names):
    """Assign machine to list of users.

    Args:
      project: GCP project.
      zone: GCP zone.
      deployment_name: Deployment.
      machine_name: Machine.
      user_names: List of user names. Currently requires full user name.

    Returns:
      True if it succeeded. False otherwise.
    """
    log.debug('Locating deployment: %s', deployment_name)
    cam = camapi.CloudAccessManager(project=project,
                                    scope=camapi.Scope.DEPLOYMENT)
    deployment = cam.deployments.get(deployment_name)

    # Get or create machine
    # https://github.com/GoogleCloudPlatform/solutions-cloud-orchestrate/issues/35
    # Use the right case when locating machines by name, otherwise CAM API
    # requests will fail with 400 errors. Feels like this should be handled by
    # CAM itself in the backend. But, for the time being guidelines are:
    # - CAM machines: lowercase
    # - AD computers: uppercase
    cam_machine_name = machine_name.lower()
    ad_computer_name = machine_name.upper()
    log.debug('Locating machine in CAM: %s', cam_machine_name)
    machines = cam.machines.get(deployment, machineName=cam_machine_name)
    if machines:
      machine = machines[0]
    else:
      log.debug('Locating machine in AD: %s', ad_computer_name)
      computers = cam.machines.entitlements.adcomputers.get(
          deployment, computerName=ad_computer_name)
      if computers:
        log.debug('Creating machine in CAM: %s', cam_machine_name)
        machine = cam.machines.post(deployment, cam_machine_name, project, zone)
      else:
        message = (
            'Could not locate computer {machine_name}. Check whether it exists'
            ' and that it joined the AD domain.'
            ).format(machine_name=machine_name)
        log.error(message)
        return False

    # Create entitlement for every user
    for user_name in user_names:
      log.debug('Locating user %s', user_name)
      users = cam.machines.entitlements.adusers.get(deployment, name=user_name)
      if users:
        user = users[0]
        log.info('Assigning %s to %s (%s)', machine_name, user['name'],
                 user['userName'])
        try:
          entitlement = cam.machines.entitlements.post(machine, user)
        except requests.exceptions.HTTPError as exception:
          if exception.response.status_code == 409:
            log.info('Machine %s was already assigned to %s. Skipping',
                     machine_name, user_name)
            continue
          else:
            raise
        message = 'Assigned {machine} to {user} ({user_name}) with id {id}'.format(
            machine=machine_name,
            user=user_name,
            user_name=user['userName'],
            id=entitlement['entitlementId'],
            )
        log.info(message)
      else:
        message = (
            'Could not locate user {user_name}. Check whether it exists in the'
            ' AD domain. Skipping for now.'
            ).format(user_name=user_name)
        log.warning(message)

    return True
