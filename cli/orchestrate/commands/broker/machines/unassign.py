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

r"""Unassign machines from users in connection broker.

Usage: orchestrate broker machines unassign <DEPLOYMENT> <MACHINE>
"""

import logging
import os

from orchestrate import base
from orchestrate.systems.teradici import camapi

log = logging.getLogger(__name__)


class Command(base.OrchestrateCommand):
  """Unassign machines from users in connection broker.
  """

  @property
  def description(self):
    return """
Unassign all users from a given macines in connection broker.

Usage: orchestrate broker machines unassign <DEPLOYMENT> <MACHINE1> [ <MACHINE2>[ ...]]
""".lstrip()

  def run(self, options, arguments):
    """Executes command.

    Args:
      options: Command-line options.
      arguments: Command-line positional arguments

    Returns:
      True if successful. False, otherwise.
    """
    log.debug('broker machines unassign %(options)s %(arguments)s', dict(
        options=options, arguments=arguments))

    if len(arguments) < 2:
      log.error('Expected deployment and at least one machine name.')
      return False

    deployment_name = arguments[0]
    machine_names = arguments[1:]
    self.unassign(deployment_name, machine_names)

  def unassign(self, deployment_name, machine_names):
    """Unassign all users from given machines.

    Args:
      deployment_name: Deployment.
      machine_names: Machine names.

    Returns:
      True if it succeeded. False otherwise.
    """
    log.debug('Locating deployment: %s', deployment_name)
    cam = camapi.CloudAccessManager(os.environ['TERADICI_TOKEN'])
    deployment = cam.deployments.get(deployment_name)

    # Get machine ids
    all_machines = []
    for machine_name in machine_names:
      log.debug('Locating machine in CAM: %s', machine_name)
      machines = cam.machines.get(deployment, machineName=machine_name)
      if machines:
        machine = machines[0]
        log.debug('Found machine %s with ID %s', machine_name,
                  machine['machineId'])
        all_machines.append(machine)
      else:
        message = (
            'Could not locate machine {machine_name}. Check whether it exists'
            ' and that it was assigned to users. Skipping for now.'
            ).format(machine_name=machine_name)
        log.warning(message)

    # Find all entitlements for all machine ids collected and remove them
    for machine in all_machines:
      log.info(
          'Locating entitlements for machine %(machineName)s %(machineId)s',
          machine)
      entitlements = cam.machines.entitlements.get(
          deployment, machineName=machine['machineName'])
      for entitlement in entitlements:
        log.info('Removing entitlement %(entitlementId)s', entitlement)
        cam.machines.entitlements.delete(entitlement)

    return True
