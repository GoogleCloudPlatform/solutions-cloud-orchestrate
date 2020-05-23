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

"""Simple configuration mechanism inspired by gcloud's."""

import configparser
import os


def load_configuration():
  """Reads configuration from disk.

  Returns:
    An instance of configparser.ConfigParser.
  """
  file_names = [
      os.path.expandvars('$HOME/.config/orchestrate/config_default'),
  ]
  config = configparser.ConfigParser()
  config.read(file_names)
  return config


def get_value(option, default=None):
  """Returns value of given configuration option.

  Configuration is stored in sections following an INI format.

  Args:
    option: Name of option in the format section/key, e.g. api/host.
    default: Default value to use if option is not present.
  """
  global configuration
  section, key = option.split('/')
  if section in configuration:
    return configuration[section].get(key, default)
  return default


configuration = load_configuration()
