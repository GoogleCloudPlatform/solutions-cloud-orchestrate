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

"""Test orchestrate images create."""

from unittest import mock

import orchestrate.commands.images.create
import orchestrate.main
from orchestrate.service.orchestrate_pb2 import CreateImageRequest
from orchestrate.service.orchestrate_pb2 import Metadata

import pytest


@mock.patch('orchestrate.base.command.OrchestrateCommand.execute')
def test_no_execution(execute):
  """Verify expected behaviour with incomplete options.

  Args:
    execute: Mock to verify calls.
  """
  # Bare command does not execute API call
  orchestrate.main.main(['images', 'create'])
  assert execute.call_count == 0

  # Help text exits program without executing API call
  with pytest.raises(SystemExit):
    orchestrate.main.main(['images', 'create', '--help'])
  assert execute.call_count == 0

  # Incorrect option exits program without executing API call
  with pytest.raises(SystemExit):
    orchestrate.main.main(['images', 'create', '--non-existent-option'])
  assert execute.call_count == 0


@mock.patch('orchestrate.base.command.OrchestrateCommand.execute')
def test_execution_with_defaults(execute):
  """Verify translation of CLI options into API call parameters.

  Args:
    execute: Mock to verify calls.
  """
  orchestrate.main.main([
      'images',
      'create',
      'test_image',
      'linux',
  ])
  assert execute.call_count == 1

  # Unpack and verify parameters to the API call
  arguments, optionals = execute.call_args
  assert arguments and not optionals
  endpoint, request, options = arguments
  assert endpoint and request and options

  # Get command and default values
  command = orchestrate.commands.images.create.Command()
  defaults = command.defaults

  # Verify API call parameters

  # endpoint
  assert endpoint == 'CreateImage'

  # request
  assert request.image.project == 'gcloud_project'
  assert request.image.zone == 'gcloud_zone'
  assert request.image.name == 'test_image'
  assert request.image.image_family == defaults['image_family']
  assert request.image.image_project == defaults['image_project']
  assert not request.image.steps
  assert not request.image.metadata
  assert request.image.disk_size == defaults['disk_size']
  assert request.image.network == defaults['network']
  os_type = CreateImageRequest.Image.OSType.Value('LINUX')
  assert request.image.os_type == os_type
  assert request.image.api_project == 'config_project'

  # options
  assert options.api_host == 'config_host'
  assert options.api_key == 'config_key'


@mock.patch('orchestrate.base.command.OrchestrateCommand.execute')
def test_execution_with_user_options(execute):
  """Verify translation of CLI options into API call parameters.

  Args:
    execute: Mock to verify calls.
  """
  orchestrate.main.main([
      'images',
      'create',
      'test_image',
      'windows',
      '--project=user_project',
      '--zone=user_zone',
      '--image-family=user_image_family',
      '--image-project=user_image_project',
      '--packages=user_package1:user_package2',
      '--metadata=user_key1=user_value1,user_key2=user_value2',
      '--disk-size=1234',
      '--network=user_network',
      '--api-project=user_api_project',
      '--api-host=user_api_host',
      '--api-key=user_api_key',
  ])
  assert execute.call_count == 1

  # Unpack and verify parameters to the API call
  arguments, optionals = execute.call_args
  assert arguments and not optionals
  endpoint, request, options = arguments
  assert endpoint and request and options

  # Verify API call parameters

  # endpoint
  assert endpoint == 'CreateImage'

  # request
  assert request.image.project == 'user_project'
  assert request.image.zone == 'user_zone'
  assert request.image.name == 'test_image'
  assert request.image.image_family == 'user_image_family'
  assert request.image.image_project == 'user_image_project'
  assert request.image.steps == ['user_package1:user_package2']
  assert len(request.image.metadata) == 2
  assert request.image.metadata[0].key == 'user_key1'
  assert request.image.metadata[0].value == 'user_value1'
  assert request.image.metadata[1].key == 'user_key2'
  assert request.image.metadata[1].value == 'user_value2'
  assert request.image.disk_size == 1234
  assert request.image.network == 'user_network'
  os_type = CreateImageRequest.Image.OSType.Value('WINDOWS')
  assert request.image.os_type == os_type
  assert request.image.api_project == 'user_api_project'

  # options
  assert options.api_host == 'user_api_host'
  assert options.api_key == 'user_api_key'
