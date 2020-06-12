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

"""Test fixtures."""

import configparser

import orchestrate.config
import orchestrate.utils

import pytest


@pytest.fixture(autouse=True)
def configuration(monkeypatch):
  """In-memory configuration.

  Args:
    monkeypatch: Fixture helper.
  """
  config = configparser.ConfigParser()
  config.read_dict(dict(
      api=dict(
          project='config_project',
          host='config_host',
          key='config_key',
          )
      ))
  monkeypatch.setattr(orchestrate.config, 'configuration', config)


@pytest.fixture(autouse=False)
def environ(monkeypatch):
  """In-memory environment variables.

  Args:
    monkeypatch: Fixture helper.
  """
  monkeypatch.setenv('ORCHESTRATE_PROJECT', 'environ_project')
  monkeypatch.setenv('ORCHESTRATE_API_HOST', 'environ_host')
  monkeypatch.setenv('ORCHESTRATE_API_KEY', 'environ_key')


@pytest.fixture(autouse=True)
def get_gcloud_config_value(monkeypatch):
  """Returns predictable gcloud config values for testing.

  Args:
    monkeypatch: Fixture helper.
  """
  def get_gcloud_config_value_for_tests(key, default=None):
    """Returns predictable gcloud config values for testing.

    Args:
      key: Config key to retrieve, e.g. project, compute/zone
      default: Default value to return if key is not found or an error occurs
         trying to retrieve its value.
    """
    if key == 'project':
      return b'gcloud_project'
    elif key == 'compute/zone':
      return b'gcloud_zone'
    else:
      return default

  monkeypatch.setattr(orchestrate.utils, 'get_gcloud_config_value',
                      get_gcloud_config_value_for_tests)
