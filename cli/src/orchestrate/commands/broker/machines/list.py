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
        deployment=None,
        )

  @property
  def options(self):
    """Returns command parser options."""
    options = [
        optparse.Option('--assigned', action='store_true', help=(
            'Show only machines that are assigned to users.'
            ' Default is %default')),
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
    log.debug('broker machines list %(options)s %(arguments)s', dict(
        options=options, arguments=arguments))

    if arguments:
      log.error('Unexpected arguments. See --help for more information.')
      return False

    deployment_name = options.deployment or options.project

    cam = camapi.CloudAccessManager(project=options.project,
                                    scope=camapi.Scope.DEPLOYMENT)
    deployment = cam.deployments.get(deployment_name)

    if options.assigned:
      entitlements = camapi.RequestIterator(cam.machines.entitlements.get,
                                            deployment)
      visitor = EntitlementPrinter()
      for entitlement in entitlements:
        visitor.visit(entitlement)
    else:
      computers = camapi.RequestIterator(
          cam.machines.entitlements.adcomputers.get, deployment)
      visitor = ADComputerPrinter()
      for computer in computers:
        visitor.visit(computer)


class EntitlementPrinter:
  """Print entitlement data in columns.
  """

  def __init__(self):
    self.row_format = '{machineName:20} {userGuid:36} {entitlementId}'
    self.first = True

  def visit(self, entitlement):
    """Print details of given entitlement.

    Args:
      entitlement: Entitlement object.
    """
    if self.first:
      self.first = False
      row = self.row_format.format(
          entitlementId='ENTITLEMENT ID', machineName='MACHINE',
          userGuid='USER GUID')
      log.info(row)
    row = self.row_format.format(
        entitlementId=entitlement['entitlementId'],
        machineName=entitlement['machine']['machineName'],
        userGuid=entitlement['userGuid'],
        )
    log.info(row)


class ADComputerPrinter:
  """Print computer data in columns.
  """

  def __init__(self):
    self.row_format = (
        '{computerName:15} {operatingSystem} {operatingSystemVersion}'
        )
    self.first = True

  def visit(self, computer):
    """Print details of given computer.

    Args:
      computer: AD Computer object.
    """
    if self.first:
      self.first = False
      row = self.row_format.format(
          computerName='NAME', operatingSystem='OS',
          operatingSystemVersion='')
      log.info(row)
    row = self.row_format.format(**computer)
    log.info(row)
