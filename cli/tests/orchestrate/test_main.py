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

"""Test main CLI functionality."""

import os
from unittest import mock

import orchestrate.main


def test_find_valid_commands():
  """Should find valid commands and subcommands at different levels.
  """
  root = os.path.sep.join([
      os.path.dirname(orchestrate.main.__file__),
      'commands',
  ])

  # top level commands
  path = root
  expected = [
      'broker',
      'images',
      'instances',
      'projects',
      'systems',
      'templates',
  ]
  commands = orchestrate.main.find_valid_commands(path)
  assert sorted(commands) == sorted(expected)

  # sample bottom level commands
  path = os.path.sep.join([root, 'images'])
  expected = ['create']
  commands = orchestrate.main.find_valid_commands(path)
  assert sorted(commands) == sorted(expected)

  # sample third level commands
  path = os.path.sep.join([root, 'broker', 'machines'])
  expected = ['assign', 'unassign', 'list']
  commands = orchestrate.main.find_valid_commands(path)
  assert sorted(commands) == sorted(expected)


@mock.patch('orchestrate.main.suggest_recovery_options')
@mock.patch('orchestrate.main.execute_command')
def test_main(execute_command, suggest_recovery_options):
  """Verify behaviour when executing commands without actually executing them.

  Args:
    execute_command: Mock to verify calls.
    suggest_recovery_options: Mock to verify calls.
  """
  orchestrate.main.main(['images', 'create'])
  assert execute_command.call_count == 1
  assert suggest_recovery_options.call_count == 0

  orchestrate.main.main(['broker', 'machines', 'assign'])
  assert execute_command.call_count == 2
  assert suggest_recovery_options.call_count == 0

  orchestrate.main.main(['non-existent-command', 'argument1', 'argument2'])
  assert execute_command.call_count == 2
  assert suggest_recovery_options.call_count == 1

