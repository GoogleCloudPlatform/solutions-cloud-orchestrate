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

"""Test orchestrate projects register."""

from unittest import mock

import orchestrate.main

import pytest


original_create_command = orchestrate.main.create_command
register_Command_configure = mock.Mock()


def create_patched_command(name, loader):
  """Returns a command instance from the given module loader ready for testing.

  The command subject to unit testing attempts to execute some gcloud commands
  in addition to the Orchestrate API call. Need to patch it to prevent it from
  actually executing the commands since we're only interested in knowing that
  the method was called. Testing the actual execution of these commands is
  delegated to integration tests and they need proper environment setup and a
  GCP project in the backend to verify operations.

  Need to decorate the original `orchestrate.main.create_command` function here
  so that we can intercept the instantiated command and patch the `configure`
  method with a `unittest.mock.Mock`. It needs to be done this way because the
  module is loaded dynamically and the `patch` decorator is not effective given
  the way `Mock` works. Need to patch where the module is actually loaded.

  Args:
    name: Module name.
    loader: Module loader.
  """
  command = original_create_command(name, loader)
  command.configure = register_Command_configure
  return command


@mock.patch('orchestrate.base.command.OrchestrateCommand.execute')
@mock.patch('orchestrate.main.create_command', create_patched_command)
def test_no_execution(execute):
  """Verify expected behaviour with incomplete options.

  Args:
    execute: Mock to verify calls.
  """
  register_Command_configure.reset_mock()

  # Does not execute API call with unexpected arguments
  orchestrate.main.main(['projects', 'register', 'unexpected-arguments'])
  assert register_Command_configure.call_count == 0
  assert execute.call_count == 0

  # Help text exits program without executing API call
  with pytest.raises(SystemExit):
    orchestrate.main.main(['projects', 'register', '--help'])
  assert register_Command_configure.call_count == 0
  assert execute.call_count == 0

  # Incorrect option exits program without executing API call
  with pytest.raises(SystemExit):
    orchestrate.main.main(['projects', 'register', '--non-existent-option'])
  assert register_Command_configure.call_count == 0
  assert execute.call_count == 0


@mock.patch('orchestrate.base.command.OrchestrateCommand.execute')
@mock.patch('orchestrate.main.create_command', create_patched_command)
def test_execution_with_defaults(execute):
  """Verify translation of CLI options into API call parameters.

  Args:
    execute: Mock to verify calls.
  """
  register_Command_configure.reset_mock()

  orchestrate.main.main([
      'projects',
      'register',
  ])
  assert register_Command_configure.call_count == 1
  assert execute.call_count == 1

  # Unpack and verify parameters to the API call
  arguments, optionals = execute.call_args
  assert arguments and not optionals
  endpoint, request, options = arguments
  assert endpoint and request and options

  # Verify API call parameters

  # endpoint
  assert endpoint == 'RegisterProject'

  # request
  assert request.project == 'gcloud_project'

  # options
  assert options.api_host == 'config_host'
  assert options.api_key == 'config_key'


@mock.patch('orchestrate.base.command.OrchestrateCommand.execute')
@mock.patch('orchestrate.main.create_command', create_patched_command)
def test_execution_with_user_options(execute):
  """Verify translation of CLI options into API call parameters.

  Args:
    execute: Mock to verify calls.
  """
  register_Command_configure.reset_mock()

  orchestrate.main.main([
      'projects',
      'register',
      '--project=user_project',
      '--api-project=user_api_project',
      '--api-host=user_api_host',
      '--api-key=user_api_key',
  ])
  assert register_Command_configure.call_count == 1
  assert execute.call_count == 1

  # Unpack and verify parameters to the API call
  arguments, optionals = execute.call_args
  assert arguments and not optionals
  endpoint, request, options = arguments
  assert endpoint and request and options

  # Verify API call parameters

  # endpoint
  assert endpoint == 'RegisterProject'

  # request
  assert request.project == 'user_project'

  # options
  assert options.api_host == 'user_api_host'
  assert options.api_key == 'user_api_key'
