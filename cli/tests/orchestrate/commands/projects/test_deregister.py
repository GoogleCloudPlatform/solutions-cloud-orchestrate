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

"""Test orchestrate projects deregister."""

from unittest import mock

import orchestrate.commands.projects.deregister
import orchestrate.main
from orchestrate.service.orchestrate_pb2 import DeregisterProjectRequest

import pytest


def run(execute_command_with_options, arguments):
  """Execute command with correct patches applied to dynamically-loaded module.

  Args:
    execute_command_with_options: Mock to extrac options and arguments.
    arguments: Command-line.
  """
  orchestrate.main.main(arguments)
  command, options, arguments = execute_command_with_options.call_args[0]
  command = orchestrate.commands.projects.deregister.Command()
  command.run(options, arguments)


@mock.patch('orchestrate.commands.projects.deregister.Command.remove_configuration')
@mock.patch('orchestrate.base.command.OrchestrateCommand.execute')
@mock.patch('orchestrate.main.execute_command_with_options')
def test_no_execution(execute_command_with_options, execute, remove_configuration):
  """Verify expected behaviour with incomplete options.

  Args:
    execute_command_with_options: Mock to verify calls.
    execute: Mock to verify calls.
    remove_configuration: Mock to verify calls.
  """
  # Does not execute API call with unexpected arguments
  run(execute_command_with_options,
      ['projects', 'deregister', 'unexpected-arguments'])
  assert execute_command_with_options.call_count == 1
  assert remove_configuration.call_count == 0
  assert execute.call_count == 0

  # Help text exits program without executing API call
  with pytest.raises(SystemExit):
    run(execute_command_with_options, ['projects', 'deregister', '--help'])
  assert execute_command_with_options.call_count == 1
  assert remove_configuration.call_count == 0
  assert execute.call_count == 0

  # Incorrect option exits program without executing API call
  with pytest.raises(SystemExit):
    run(execute_command_with_options,
        ['projects', 'deregister', '--non-existent-option'])
  assert execute_command_with_options.call_count == 1
  assert remove_configuration.call_count == 0
  assert execute.call_count == 0


@mock.patch('orchestrate.commands.projects.deregister.Command.remove_configuration')
@mock.patch('orchestrate.base.command.OrchestrateCommand.execute')
@mock.patch('orchestrate.main.execute_command_with_options')
def test_execution_with_defaults(
    execute_command_with_options, execute, remove_configuration):
  """Verify translation of CLI options into API call parameters.

  Args:
    execute_command_with_options: Mock to verify calls.
    execute: Mock to verify calls.
    remove_configuration: Mock to verify calls.
  """
  run(execute_command_with_options, [
      'projects',
      'deregister',
  ])
  assert execute_command_with_options.call_count == 1
  assert remove_configuration.call_count == 1
  assert execute.call_count == 1

  # Unpack and verify parameters to the API call
  arguments, optionals = execute.call_args
  assert arguments and not optionals
  endpoint, request, options = arguments
  assert endpoint and request and options

  # Verify API call parameters

  # endpoint
  assert endpoint == 'DeregisterProject'

  # request
  assert request.project == 'gcloud_project'

  # options
  assert options.api_host == 'config_host'
  assert options.api_key == 'config_key'


@mock.patch('orchestrate.commands.projects.deregister.Command.remove_configuration')
@mock.patch('orchestrate.base.command.OrchestrateCommand.execute')
@mock.patch('orchestrate.main.execute_command_with_options')
def test_execution_with_user_options(
    execute_command_with_options, execute, remove_configuration):
  """Verify translation of CLI options into API call parameters.

  Args:
    execute_command_with_options: Mock to verify calls.
    execute: Mock to verify calls.
    remove_configuration: Mock to verify calls.
  """
  run(execute_command_with_options, [
      'projects',
      'deregister',
      '--project=user_project',
      '--api-project=user_api_project',
      '--api-host=user_api_host',
      '--api-key=user_api_key',
  ])
  assert execute_command_with_options.call_count == 1
  assert remove_configuration.call_count == 1
  assert execute.call_count == 1

  # Unpack and verify parameters to the API call
  arguments, optionals = execute.call_args
  assert arguments and not optionals
  endpoint, request, options = arguments
  assert endpoint and request and options

  # Verify API call parameters

  # endpoint
  assert endpoint == 'DeregisterProject'

  # request
  assert request.project == 'user_project'

  # options
  assert options.api_host == 'user_api_host'
  assert options.api_key == 'user_api_key'
