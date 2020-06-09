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

r"""Show list of users visible to the broker.

Usage: orchestrate broker users list [OPTIONS]
"""

import logging
import optparse

from orchestrate import base
from orchestrate.systems.teradici import camapi

log = logging.getLogger(__name__)


class Command(base.OrchestrateCommand):
  """Show list of users visible to the broker.
  """

  @property
  def description(self):
    return """
Show list of users visible to the broker.
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
    log.debug('broker machines list %(options)s %(arguments)s', dict(
        options=options, arguments=arguments))

    if arguments:
      log.error('Unexpected arguments. See --help for more options.')
      return False

    deployment_name = options.deployment or options.project
    cam = camapi.CloudAccessManager(project=options.project,
                                    scope=camapi.Scope.DEPLOYMENT)
    deployment = cam.deployments.get(deployment_name)
    users = camapi.RequestIterator(cam.machines.entitlements.adusers.get,
                                   deployment)
    visitor = UserPrinter()
    for user in users:
      visitor.visit(user)


class UserPrinter:
  """Print user data in columns.
  """

  def __init__(self):
    self.row_format = '{userName:20} {name:30} {userGuid:15}'
    self.first = True

  def visit(self, user):
    """Print details of given user.

    Args:
      user: AD User object.
    """
    if self.first:
      self.first = False
      row = self.row_format.format(userGuid='GUID', userName='USER',
                                   name='NAME')
      log.info(row)
    row = self.row_format.format(**user)
    log.info(row)

