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

"""Test orchestrate templates delete."""

from unittest import mock

import orchestrate.main
from orchestrate.service.orchestrate_pb2 import DeleteTemplateRequest

import pytest


@mock.patch('orchestrate.base.command.OrchestrateCommand.execute')
def test_no_execution(execute):
  """Verify expected behaviour with incomplete options.

  Args:
    execute: Mock to verify calls.
  """
  # Bare command does not execute API call
  orchestrate.main.main(['templates', 'delete'])
  assert execute.call_count == 0

  # Help text exits program without executing API call
  with pytest.raises(SystemExit):
    orchestrate.main.main(['templates', 'delete', '--help'])
  assert execute.call_count == 0

  # Incorrect option exits program without executing API call
  with pytest.raises(SystemExit):
    orchestrate.main.main(['templates', 'delete', '--non-existent-option'])
  assert execute.call_count == 0


@mock.patch('orchestrate.base.command.OrchestrateCommand.execute')
def test_execution_with_defaults(execute):
  """Verify translation of CLI options into API call parameters.

  Args:
    execute: Mock to verify calls.
  """
  orchestrate.main.main([
      'templates',
      'delete',
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
  assert endpoint == 'DeleteTemplate'

  # request
  assert request.project == 'gcloud_project'
  assert request.name == 'test_template'

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
      'templates',
      'delete',
      'test_template',
      '--project=user_project',
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
  assert endpoint == 'DeleteTemplate'

  # request
  assert request.project == 'user_project'
  assert request.name == 'test_template'

  # options
  assert options.api_host == 'user_api_host'
  assert options.api_key == 'user_api_key'

