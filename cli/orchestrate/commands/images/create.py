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

r"""Orchestrates image provisioning and lyfe cycle.

Example:
orchestrate images create test-centos-visual-1 \
  --project=orchestrate-test-1 \
  --zone=us-central1-a \
  --image-project=centos-cloud \
  --image-family=centos-7 \
  --packages=stackdriver,tools \
  --metadata \
teradici_registration_code="123456789012@ABCD-EFGH-IJKL-MNOP",\
maya_license_server="maya_license.local",\
vray_license_server="vray_license.local:30304",\
nuke_license="4101@nuke.license.local",\
rv_license="rv_license.local:5436",\
elastifile_server="elastifile.local"
"""

import logging
import optparse

from orchestrate import base
from orchestrate.service.orchestrate_pb2 import CreateImageRequest
from orchestrate.service.orchestrate_pb2 import Metadata

log = logging.getLogger(__name__)


class Command(base.OrchestrateCommand):
  """Creates and provisions an image with user-domain software."""

  @property
  def description(self):
    return """Creates an image provisioned with user-domain software ready
to use. Third-party software is either open-source or BYOL.

Install the essential packages below plus open-source and only third-party
software already licensed and/or otherwise bundled by GCP. See "Default" section
below for complete list. Use --packages to specify a colon-separated list of
package names from the following list:

Essentials:
- core                   Basic system-level libraries required to install others.
- stackdriver            Integration with StackDriver monitoring and logging.
- tools                  Essential tools required to install others.
- chrome                 Chrome browser.
- nvidia                 NVIDIA GRID driver.
- teradici               PCoIP agent.
- teradici_registration  Registers the agent.

Storage:
- storage                NFS utils for remote storage clusters.
- storage_environment    Remote storage cluster environment configuration.
- gcsfuse                GCS Fuse configuration.

Open Source:
- opencue                OpenCue: A render manager.
- opencue_environment    OpenCue environment.
- blender                Blender.
- djv                    Professional review software.
- djv_environment        DJV environment.

BYOL:
- maya                   AutoDesk's Maya.
- maya_license           Maya network license configuration.
- vray                   ChaosGroup's V-Ray renderer.
- vray_license           V-Ray network license configuration.
- vray_environment       V-Ray environment.
- arnold                 AutoDesk's Arnold renderer.
- zync                   Google Cloud Zync Render.
- zync_environment       Zync environment.
- nuke                   The Foundry's Nuke.
- nuke_license           Nuke license configuration.
- houdini                SideFX's Houdini.
- houdini_license        Houdini license configuration.
- resolve                DaVinci's Resolve
- resolve_environment    DaVinci's Resolve environment.

Default packages when no `--packages` option is provided in the command line:
- core
- stackdriver
- tools
- chrome
- nvidia
- teradici
- storage
- storage_environment
"""

  @property
  def defaults(self):
    """Returns default option values."""
    return dict(
        image_project='centos-cloud',
        image_family='centos-7',
        packages=None,
        metadata='',
        # b/147450711 At 30GB we can install all currently supported packages
        # and leaving 20% disk available. In the end, instances will very likely
        # use a larger disk specified in the template. And, the majority of the
        # actual storage for the end user will be mounted from an external
        # cluster. So, it's ok to keep disk tight for baked images.
        disk_size=30,
        network='default',
        )

  @property
  def options(self):
    """Returns command parser options."""
    options = [
        optparse.Option('-e', '--image-project', help=(
            'Project where image family lives. Default is %default')),
        optparse.Option('-f', '--image-family', help=(
            'Base image family. Default is %default')),
        optparse.Option('-k', '--packages', help=(
            'Software packages to install. Provide a colon-separated list of'
            ' package names from the list in the description above in this help'
            ' text. If not provided, Orchestrate will install all packages by'
            ' default.')),
        optparse.Option('-m', '--metadata', help=(
            'Configuration parameters passed as instance metadata. Use to send'
            ' registration code, license servers, etc. Use same format as'
            ' gcloud compute instances add-metadata.')),
        optparse.Option('--disk-size', type='int', help=(
            'Disk size in GB for the temporary provisioning image.'
            ' Default is %default')),
        optparse.Option('--network', help=(
            'Network where the temporary provisioning image will be created.'
            ' Default is: %default')),
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
    log.debug('images create %(options)s %(arguments)s', dict(
        options=options, arguments=arguments))

    if len(arguments) != 2:
      log.error('Expected image name and OS type. e.g. editorial windows')
      return False

    name, os_type = arguments
    try:
      os_type = CreateImageRequest.Image.OSType.Value(os_type.upper())
    except ValueError:
      message = (
          '%(os_type)s is not a supported OS type. Please select from:'
          ' %(os_types)s'
          )
      os_types = map(str.lower, CreateImageRequest.Image.OSType.keys()[1:])
      os_types = ', '.join(os_types)
      log.error(message, dict(os_type=os_type, os_types=os_types))
      return False

    if options.packages:
      steps = options.packages.split(',')
    else:
      steps = []

    metadata = []
    if options.metadata:
      for item in options.metadata.split(','):
        key, value = item.split('=')
        key = key.replace('-', '_')
        entry = Metadata(key=key, value=value)
        metadata.append(entry)

    request = CreateImageRequest(
        image=CreateImageRequest.Image(
            project=options.project,
            zone=options.zone,
            name=name,
            image_family=options.image_family,
            image_project=options.image_project,
            steps=steps,
            metadata=metadata,
            disk_size=options.disk_size,
            network=options.network,
            os_type=os_type,
            api_project=options.api_project,
        )
    )

    response = self.execute('CreateImage', request, options)
    log.info('Response: status=%(status)s request_id=%(request_id)s', dict(
        status=response.status,
        request_id=response.request_id,
        ))
    return True

