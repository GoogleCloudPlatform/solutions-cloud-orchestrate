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

r"""Show list of machines visible to the broker.

Usage: orchestrate broker machines list [OPTIONS] <DEPLOYMENT>
"""

import logging
import optparse
import os

from orchestrate import base
from orchestrate.systems.teradici import camapi

log = logging.getLogger(__name__)


class Command(base.OrchestrateCommand):
  """Show list of machines visible to the broker.
  """

  @property
  def description(self):
    return """
Show list of machines visible to the broker.

Usage: orchestrate broker machines list [OPTIONS] <DEPLOYMENT>
""".lstrip()

  @property
  def defaults(self):
    """Returns default option values."""
    return dict(
        assigned=False,
        )

  @property
  def options(self):
    """Returns command parser options."""
    options = [
        optparse.Option('-a', '--assigned', action='store_true', help=(
            'Show only machines that are assigned to users.'
            ' Default is %default')),
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
    log.debug('broker machines list %(options)s %(arguments)s', dict(
        options=options, arguments=arguments))

    if len(arguments) != 1:
      log.error('Expected deployment name.')
      return False

    deployment_name = arguments[0]

    cam = camapi.CloudAccessManager(os.environ['TERADICI_TOKEN'])
    deployment = cam.deployments.get(deployment_name)

    if options.assigned:
      self.show_assigned_machines(cam, deployment)
    else:
      self.show_ad_computers(cam, deployment)

  def show_assigned_machines(self, cam, deployment):
    """Show CAM machines.

    Args:
      cam: Connection to CloudAccessManager API.
      deployment: Deployment name.
    """
    entitlements = cam.machines.entitlements.get(deployment)

    row_format = '{machineName:20} {userGuid:36} {entitlementId}'
    row = row_format.format(
        entitlementId='ENTITLEMENT ID', machineName='MACHINE',
        userGuid='USER GUID')
    log.info(row)
    for entitlement in entitlements:
      row = row_format.format(
          entitlementId=entitlement['entitlementId'],
          machineName=entitlement['machine']['machineName'],
          userGuid=entitlement['userGuid'],
          )
      log.info(row)

  def show_ad_computers(self, cam, deployment):
    """Show AD computers.

    Args:
      cam: Connection to CloudAccessManager API.
      deployment: Deployment name.
    """
    computers = cam.machines.entitlements.adcomputers.get(deployment)

    row_format = '{computerName:15} {operatingSystem} {operatingSystemVersion}'
    row = row_format.format(
        computerName='NAME', operatingSystem='OS',
        operatingSystemVersion='')
    log.info(row)
    for computer in computers:
      row = row_format.format(**computer)
      log.info(row)
