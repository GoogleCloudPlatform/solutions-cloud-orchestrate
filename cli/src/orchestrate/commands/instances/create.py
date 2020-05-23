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

r"""Creates instances using a simplified interface."""

import logging
import optparse

from orchestrate import base
from orchestrate.service.orchestrate_pb2 import CreateInstanceRequest
from orchestrate.service.orchestrate_pb2 import Metadata

log = logging.getLogger(__name__)


class Command(base.OrchestrateCommand):
  """Initializes a template with a default size.
  """

  @property
  def description(self):
    return """
Usage:
  orchestrate instances create [OPTIONS] TEMPLATE
Examples:

1. Create an instance from a given template using its default size and
   assigning a unique name automatically using the template's naming convention:

    orchestrate instances create editorial \
      --project=orchestrate-test-1 \
      --zone=us-central1-a

2. Create an instance with a specific size and name:

    orchestrate instances create editorial \
      --project=orchestrate-test-1 \
      --zone=us-central1-a \
      --size=large \
      --name=render_station
""".lstrip()

  @property
  def defaults(self):
    """Returns default option values."""
    return dict(
        size=None,
        name=None,
        use_external_ip=False,
        )

  @property
  def options(self):
    """Returns command parser options."""
    options = [
        optparse.Option('-s', '--size', help=(
            'Template size to use. If no size is specified, then Orchestrate will'
            ' locate and use the default size for the given template name.'
            ' Default is %default')),
        optparse.Option('-n', '--name', help=(
            'Provide an explicit name for the instance. By default it would'
            ' use either a unique name if not provided. Or, the'
            ' instance-name-pattern value stored in the template, if any.')),
        optparse.Option('-d', '--metadata', help=(
            'Metadata in the same format as gcloud compute instances'
            ' add-metadata.')),
        optparse.Option(
            '--no-latest-image', dest='use_latest_image', action='store_false',
            default=True, help=(
                'Use the image version at the time the template was created'
                ' instead of the latest version in the image family. It will'
                ' use the latest image by default unless this is specified.')),
        optparse.Option(
            '--external-ip', dest='use_external_ip', action='store_true',
            help=('Use an external IP address')),
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
    log.debug('instances create %(options)s %(arguments)s', dict(
        options=options, arguments=arguments))

    if len(arguments) != 1:
      log.error('Expected a template name.')
      return False

    template = arguments[0]

    metadata = []
    if options.metadata:
      for item in options.metadata.split(','):
        key, value = item.split('=')
        entry = Metadata(key=key, value=value)
        metadata.append(entry)

    request = CreateInstanceRequest(
        instance=CreateInstanceRequest.Instance(
            project=options.project,
            zone=options.zone,
            template=template,
            size=options.size,
            name=options.name,
            metadata=metadata,
            use_latest_image=options.use_latest_image,
            use_external_ip=options.use_external_ip,
        )
    )

    response = self.execute('CreateInstance', request, options)
    log.info('Response: status=%(status)s request_id=%(request_id)s', dict(
        status=response.status,
        request_id=response.request_id,
        ))
    log.info('Instance name: %(name)s', dict(name=response.name))

    return True
