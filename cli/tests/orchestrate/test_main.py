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

import pytest


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
def test_main(suggest_recovery_options):
  """Verify behaviour when executing commands without actually executing them.

  Args:
    suggest_recovery_options: Mock to verify calls.
  """
  with pytest.raises(SystemExit):
    orchestrate.main.main(['images', 'create', '--help'])
  assert suggest_recovery_options.call_count == 0

  with pytest.raises(SystemExit):
    orchestrate.main.main(['broker', 'machines', 'assign', '--help'])
  assert suggest_recovery_options.call_count == 0

  orchestrate.main.main(
      ['non-existent-command', 'argument1', 'argument2', '--help'])
  assert suggest_recovery_options.call_count == 1
