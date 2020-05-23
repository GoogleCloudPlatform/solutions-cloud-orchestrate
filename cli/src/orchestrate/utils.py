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

"""Common utils for orchestrate commands.
"""

import optparse
import os
import subprocess

from orchestrate import config


def get_gcloud_config_value(key, default=None):
  """Returns gcloud config value.

  Args:
    key: Config key to retrieve, e.g. project, compute/zone
    default: Default value to return if key is not found or an error occurs
       trying to retrieve its value.
  """
  command = 'gcloud config get-value ' + key
  command = command.split()
  try:
    value = subprocess.check_output(command)
    return value.strip()
  except subprocess.CalledProcessError:
    return default


def get_common_option_defaults():
  """Returns a dictionary with the default values for command-line options."""
  # Get GCP config values directly from gcloud config
  project = get_gcloud_config_value('project').decode()
  zone = get_gcloud_config_value('compute/zone', 'us-central1-a').decode()

  # Get Orchestrate-specific values from:
  # - environment variables
  # - Orchestrate's user config file, i.e.: ~/.config/orchestrate/config_default
  # - Sensible default wherever possible
  api_host = os.environ.get('ORCHESTRATE_API_HOST')
  if not api_host:
    api_host = config.get_value('api/host', 'localhost:50051')
  api_key = os.environ.get('ORCHESTRATE_API_KEY')
  if not api_key:
    api_key = config.get_value('api/key')
  # Note, there's no API in environ variable name.
  api_project = os.environ.get('ORCHESTRATE_PROJECT')
  if not api_project:
    api_project = config.get_value('api/project')

  return dict(
      project=project,
      zone=zone,
      api_project=api_project,
      api_host=api_host,
      api_key=api_key,
      verbose=False,
  )


def get_common_options():
  """Returns parser options common to all Orchestrate commands."""
  options = [
      optparse.Option('-p', '--project', help=(
          'Create resources in project. Default is %default')),
      optparse.Option('-z', '--zone', help=(
          'Create in zone - make sure GPU_TYPE is available in selected zone.'
          ' Default is %default')),
      optparse.Option('--api-project', help=(
          'GCP project hosting the Orchestrate API server. Uses api/project'
          ' value in the orchestrate config_default file or the'
          ' ORCHESTRATE_API_PROJECT environment variable.')),
      optparse.Option('--api-host', help=(
          'Orchestrate API server. Uses the ORCHESTRATE_API_URL environment variable,'
          ' if set. Defaults to localhost otherwise. Based on the current'
          ' environment the default is: %default')),
      # DO NOT show the api-key %default value in help text below
      optparse.Option('--api-key', help=(
          'Orchestrate API key. Uses the ORCHESTRATE_API_KEY environment variable,'
          ' if set. Defaults to None otherwise.')),
      optparse.Option('-v', '--verbose', action='store_true', help=(
          'verbose output.')),
      ]
  return options


