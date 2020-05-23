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

"""Test configuration."""

import configparser
from unittest import mock

import orchestrate.config


def test_get_value():
  """Values required for connecting to the API.
  """
  # Default values
  assert orchestrate.config.get_value('api/project') == 'config_project'
  assert orchestrate.config.get_value('api/host') == 'config_host'
  assert orchestrate.config.get_value('api/key') == 'config_key'

  # Explicit default values
  assert orchestrate.config.get_value('api/project', 'one') == 'config_project'
  assert orchestrate.config.get_value('api/host', 'two') == 'config_host'
  assert orchestrate.config.get_value('api/key', 'three') == 'config_key'


def test_get_value_with_non_existent_entries():
  """Values required for connecting to the API.
  """
  with mock.patch('orchestrate.config.configuration',
                  configparser.ConfigParser()):
    # Default values
    assert orchestrate.config.get_value('api/project') is None
    assert orchestrate.config.get_value('api/host') is None
    assert orchestrate.config.get_value('api/key') is None

    # Explicit default values
    assert orchestrate.config.get_value('api/project', 'one') == 'one'
    assert orchestrate.config.get_value('api/host', 'two') == 'two'
    assert orchestrate.config.get_value('api/key', 'three') == 'three'
