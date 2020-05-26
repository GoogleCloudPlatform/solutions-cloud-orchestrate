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
                                    deployment=deployment_name)
    deployment = cam.deployments.get(deployment_name)
    users = cam.machines.entitlements.adusers.get(deployment)

    row_format = '{userName:20} {name:30} {userGuid:15}'
    row = row_format.format(userGuid='GUID', userName='USER', name='NAME')
    log.info(row)
    for user in users:
      row = row_format.format(**user)
      log.info(row)
