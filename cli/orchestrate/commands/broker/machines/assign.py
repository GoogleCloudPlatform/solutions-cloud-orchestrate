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
import os
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

    if len(arguments) < 3:
      log.error('Expected deployment, machine, and at least one user name.')
      return False

    deployment_name = arguments[0]
    machine_name = arguments[1]
    user_names = arguments[2:]
    self.assign(deployment_name, machine_name, user_names)

  def assign(self, deployment_name, machine_name, user_names):
    """Assign machine to list of users.

    Args:
      deployment_name: Deployment.
      machine_name: Machine.
      user_names: List of user names. Currently requires full user name.

    Returns:
      True if it succeeded. False otherwise.
    """
    log.debug('Locating deployment: %s', deployment_name)
    cam = camapi.CloudAccessManager(os.environ['TERADICI_TOKEN'])
    deployment = cam.deployments.get(deployment_name)

    # Get or create machine
    log.debug('Locating machine in CAM: %s', machine_name)
    machines = cam.machines.get(deployment, machineName=machine_name)
    if machines:
      machine = machines[0]
    else:
      log.debug('Locating machine in AD: %s', machine_name)
      computers = cam.machines.entitlements.adcomputers.get(
          deployment, computerName=machine_name)
      if computers:
        log.debug('Creating machine in CAM: %s', machine_name)
        computer = computers[0]
        machine = cam.machines.post(deployment, computer)
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
