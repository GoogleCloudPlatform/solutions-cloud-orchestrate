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

"""Test orchestrate instances create."""

from unittest import mock

import orchestrate.commands.instances.create
import orchestrate.main
from orchestrate.service.orchestrate_pb2 import CreateInstanceRequest
from orchestrate.service.orchestrate_pb2 import Metadata

import pytest


@mock.patch('orchestrate.base.command.OrchestrateCommand.execute')
def test_no_execution(execute):
  """Verify expected behaviour with incomplete options.

  Args:
    execute: Mock to verify calls.
  """
  # Bare command does not execute API call
  orchestrate.main.main(['instances', 'create'])
  assert execute.call_count == 0

  # Help text exits program without executing API call
  with pytest.raises(SystemExit):
    orchestrate.main.main(['instances', 'create', '--help'])
  assert execute.call_count == 0

  # Incorrect option exits program without executing API call
  with pytest.raises(SystemExit):
    orchestrate.main.main(['instances', 'create', '--non-existent-option'])
  assert execute.call_count == 0


@mock.patch('orchestrate.base.command.OrchestrateCommand.execute')
def test_execution_with_defaults(execute):
  """Verify translation of CLI options into API call parameters.

  Args:
    execute: Mock to verify calls.
  """
  orchestrate.main.main([
      'instances',
      'create',
      'test_template',
  ])
  assert execute.call_count == 1

  # Unpack and verify parameters to the API call
  arguments, optionals = execute.call_args
  assert arguments and not optionals
  endpoint, request, options = arguments
  assert endpoint and request and options

  # Verify API call parameters

  # endpoint
  assert endpoint == 'CreateInstance'

  # request
  assert request.instance.project == 'gcloud_project'
  assert request.instance.zone == 'gcloud_zone'
  assert request.instance.template == 'test_template'
  assert not request.instance.size
  assert not request.instance.name
  assert not request.instance.metadata
  assert request.instance.use_latest_image
  assert not request.instance.use_external_ip

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
      'instances',
      'create',
      'test_template',
      '--project=user_project',
      '--zone=user_zone',
      '--size=user_size',
      '--name=user_name',
      '--metadata=user_key1=user_value1,user_key2=user_value2',
      '--no-latest-image',
      '--external-ip',
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
  assert endpoint == 'CreateInstance'

  # request
  assert request.instance.project == 'user_project'
  assert request.instance.zone == 'user_zone'
  assert request.instance.template == 'test_template'
  assert request.instance.size == 'user_size'
  assert request.instance.name == 'user_name'
  assert len(request.instance.metadata) == 2
  assert request.instance.metadata[0].key == 'user_key1'
  assert request.instance.metadata[0].value == 'user_value1'
  assert request.instance.metadata[1].key == 'user_key2'
  assert request.instance.metadata[1].value == 'user_value2'
  assert not request.instance.use_latest_image
  assert request.instance.use_external_ip

  # options
  assert options.api_host == 'user_api_host'
  assert options.api_key == 'user_api_key'
