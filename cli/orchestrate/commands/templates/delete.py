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

r"""Deletes a template by name.

Example:
orchestrate templates delete editorial
      --project=orchestrate-test-1
      --zone=us-central1-a
"""

import logging

from orchestrate import base
from orchestrate.service.orchestrate_pb2 import DeleteTemplateRequest

log = logging.getLogger(__name__)


class Command(base.OrchestrateCommand):
  """Initializes a template with a default size.
  """

  @property
  def description(self):
    return """
Templates in Orchestrate are more like a family of different instance sizes that
share common creation parameters. For instance, the template "vfx" could have
three sizes: small, medium, and large. Under the hood, Orchestrate will manage
individual instance-templates, i.e. one for each size. Therefore, users would
use Orchestrate to create templates and manage size because this is value added
functionality on top of GCP:

1. User would use Orchestrate to create template:

    orchestrate templates create ...

2. Use orchestrate to manage sizes provided by template:

    orchestrate templates add-size TEMPLATE ...
    orchestrate templates delete-size TEMPLATE ...
    orchestrate templates set-default-size TEMPLATE ...

3. Use Orchestrate to delete templates and all the underlying gcloud templates
   that collectively implement a Orchestrate template:

    orchestrate templates delete TEMPLATE
"""

  def run(self, options, arguments):
    """Executes command.

    Args:
      options: Command-line options.
      arguments: Command-line positional arguments

    Returns:
      True if successful. False, otherwise.
    """
    log.debug('templates delete %(options)s %(arguments)s', dict(
        options=options, arguments=arguments))

    if len(arguments) != 1:
      log.error('Expected template name.')
      return False

    name = arguments[0]

    request = DeleteTemplateRequest(
        project=options.project,
        name=name,
    )

    response = self.execute('DeleteTemplate', request, options)
    log.info('Response: status=%(status)s', dict(
        status=response.status,
        ))

    return True
