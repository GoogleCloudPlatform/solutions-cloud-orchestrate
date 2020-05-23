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

"""Test utils."""

import orchestrate.utils


def test_get_common_option_defaults_from_configuration():
  """Defaults should come from configuration file.
  """
  defaults = orchestrate.utils.get_common_option_defaults()
  expected = dict(
      project='gcloud_project',
      zone='gcloud_zone',
      api_project='config_project',
      api_host='config_host',
      api_key='config_key',
      verbose=False,
  )
  assert defaults == expected


def test_get_common_option_defaults_from_environment(environ):
  """Defaults should come from environment even if configuration provides them.

  Args:
    environ: Fixture to override config values from the environment.
  """
  defaults = orchestrate.utils.get_common_option_defaults()
  expected = dict(
      project='gcloud_project',
      zone='gcloud_zone',
      api_project='environ_project',
      api_host='environ_host',
      api_key='environ_key',
      verbose=False,
  )
  assert defaults == expected
