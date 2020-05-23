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

r"""Initializes a template with one or more sizes.

Examples:

1. Create template with a single size:

    orchestrate templates create editorial
      --project=orchestrate-test-1
      --zone=us-central1-a
      --image-project=orchestrate-test-1
      --image-family=orchestrate-test-1-centos-7-visual-core
      --memory=32
      --cpus=12
      --gpu-type=nvidia-tesla-t4-vws
      --gpu-count=1
      --disk-size=200
      --static-ip

2. Create template with multiple sizes:

    orchestrate templates create vfx \
      --project=orchestrate-test-1 \
      --zone=us-central1-a \
      --image-project=orchestrate-test-1 \
      --image-family=orchestrate-test-1-centos-7-visual-core \
      --sizes=\
name=small,cpus=4,memory=16,disk_size=200,gpu_type=nvidia-tesla-t4-vws,gpu_count=1\
:name=medium,cpus=8,memory=32,disk_size=200,gpu_type=nvidia-tesla-t4-vws,gpu_count=2\
:name=large,cpus=16,memory=48,disk_size=200,gpu_type=nvidia-tesla-t4-vws,gpu_count=4
"""

import logging
import optparse

import grpc

from orchestrate import base
from orchestrate import utils
from orchestrate.service.orchestrate_pb2 import CreateTemplateRequest
from orchestrate.service.orchestrate_pb2 import Metadata

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

  @property
  def defaults(self):
    """Returns default option values."""
    common_defaults = utils.get_common_option_defaults()
    values = dict(
        image_project=common_defaults['project'],
        static_ip=False,
        network='default',
        size_name='regular',
        instance_name_pattern=None,
        )
    values.update(self.default_size)
    return values

  @property
  def default_size(self):
    """Returns default size option values."""
    return dict(
        memory=8,
        cpus=2,
        disk_size=200,
        gpu_type=None,
        gpu_count=1,
        )

  @property
  def options(self):
    """Returns command parser options."""
    options = [
        optparse.Option('-e', '--image-project', help=(
            'Project where image family lives. Default is %default')),
        optparse.Option('-f', '--image-family', help='Base image family.'),
        optparse.Option('-n', '--size-name', help=(
            'Size name. Default is %default')),
        optparse.Option('-m', '--memory', help=(
            'Amount of RAM. Default is %defaultgb')),
        optparse.Option('-c', '--cpus', help=(
            'Number of vCPUS. Default is %default')),
        optparse.Option('-k', '--disk-size', help=(
            'Disk size. Default is %defaultgb')),
        optparse.Option('-a', '--gpu-type', help=(
            'Accelerator type, note the -vws suffix for Visual Worksations vs'
            ' no prefix for regular GPU, e.g. nvidia-tesla-t4-vws,'
            ' nvidia-tesla-t4, etc.')),
        optparse.Option('-g', '--gpu-count', help=(
            'Number of GPUs. Default is %default')),
        optparse.Option('-s', '--sizes', help=(
            'A size definition is a comma-separated list of size parameters.'
            ' Separate multiple size definitions with a colon using the'
            ' following format: name=NAME,memory=MEMORY,cpus=CPUS'
            ',disk_size=DISK_SIZE,gpu_type=GPU_TYPE,gpu_count=GPU_COUNT'
            '[:name=NAME,memory=...]. This is a convenience method to'
            ' specify more than one size for a template. If you only need one'
            ' size, you could either use this option or the individual options'
            ' --cpus, --memory, --disk-size, --gpu-type and --gpu-count.'
            ' If both methods are used, the --size option takes precedence')),
        optparse.Option('-u', '--default-size-name', help=(
            'Default size name. Applicable only when --size is specified.')),
        optparse.Option('-o', '--scopes', help=(
            'Comma-separated list of scopes. Uses GCP default if none'
            ' specified.')),
        optparse.Option('-i', '--static-ip', action='store_true', help=(
            'Reserve a static IP address. Default is %default')),
        optparse.Option('-r', '--instance-name-pattern', help=(
            'Pattern for generating instances names automatically.'
            ' The following variables are available for substitution:'
            ' zone, gpu_type, gpu_count, user')),
        optparse.Option('-d', '--metadata', help=(
            'Metadata to override the instance metadata. Same format as gcloud'
            ' compute instances add-metadata.')),
        optparse.Option('-w', '--network', help=(
            'Network to use. Default is %default')),
        optparse.Option('--subnetwork', help=(
            'Subnetwork to use. Default is the same as --network.')),
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
    log.debug('templates create %(options)s %(arguments)s', dict(
        options=options, arguments=arguments))

    if len(arguments) != 1:
      log.error('Expected template name.')
      return False

    name = arguments[0]

    scopes = options.scopes.split(',') if options.scopes else []

    metadata = []
    if options.metadata:
      for item in options.metadata.split(','):
        key, value = item.split('=')
        entry = Metadata(key=key, value=value)
        metadata.append(entry)

    sizes = self.build_sizes(options)
    default_size_name = options.default_size_name
    if not default_size_name:
      # Grab first size as the defuault
      default_size_name = sizes[0].name

    request = CreateTemplateRequest(
        template=CreateTemplateRequest.Template(
            project=options.project,
            zone=options.zone,
            name=name,
            image_project=options.image_project,
            image_family=options.image_family,
            static_ip=options.static_ip,
            network=options.network,
            subnetwork=options.subnetwork,
            scopes=scopes,
            metadata=metadata,
            sizes=sizes,
            default_size_name=default_size_name,
            instance_name_pattern=options.instance_name_pattern,
        )
    )

    response = self.execute('CreateTemplate', request, options)
    log.info('Response: status=%(status)s', dict(
        status=response.status,
        ))

    return True

  def build_sizes(self, options):
    """Builds sizes from command-line options.

    Uses individual size options like --cpus, --memory, etc., or parses size
    definitions from the --size option if specified.

    Args:
      options: Command-line options.

    Returns:
      List of Template.Size instances.
    """
    if options.sizes:
      sizes = []
      for size_definition in options.sizes.split(':'):
        size_parameters = dict(self.default_size)
        for pair in size_definition.split(','):
          key, value = pair.split('=')
          key = key.replace('-', '_')
          size_parameters[key] = value
        size = CreateTemplateRequest.Template.Size(
            name=size_parameters['name'],
            memory=int(size_parameters['memory']),
            cpus=int(size_parameters['cpus']),
            gpu_type=size_parameters['gpu_type'],
            gpu_count=int(size_parameters['gpu_count']),
            disk_size=int(size_parameters['disk_size']),
            )
        sizes.append(size)
      return sizes
    else:
      return [
          CreateTemplateRequest.Template.Size(
              name=options.size_name,
              memory=int(options.memory),
              cpus=int(options.cpus),
              gpu_type=options.gpu_type,
              gpu_count=int(options.gpu_count),
              disk_size=int(options.disk_size),
              ),
      ]
