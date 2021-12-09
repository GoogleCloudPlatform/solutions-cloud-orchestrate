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

"""Test orchestrate templates create."""

from unittest import mock

import orchestrate.commands.templates.create
import orchestrate.main
from orchestrate.service.orchestrate_pb2 import CreateTemplateRequest
from orchestrate.service.orchestrate_pb2 import Metadata

import pytest


@mock.patch('orchestrate.base.command.OrchestrateCommand.execute')
def test_no_execution(execute):
  """Verify expected behaviour with incomplete options.

  Args:
    execute: Mock to verify calls.
  """
  # Bare command does not execute API call
  orchestrate.main.main(['templates', 'create'])
  assert execute.call_count == 0

  # Help text exits program without executing API call
  with pytest.raises(SystemExit):
    orchestrate.main.main(['templates', 'create', '--help'])
  assert execute.call_count == 0

  # Incorrect option exits program without executing API call
  with pytest.raises(SystemExit):
    orchestrate.main.main(['templates', 'create', '--non-existent-option'])
  assert execute.call_count == 0


@mock.patch('orchestrate.base.command.OrchestrateCommand.execute')
def test_execution_with_defaults(execute):
  """Verify translation of CLI options into API call parameters.

  Args:
    execute: Mock to verify calls.
  """
  orchestrate.main.main([
      'templates',
      'create',
      'test_template',
  ])
  assert execute.call_count == 1

  # Unpack and verify parameters to the API call
  arguments, optionals = execute.call_args
  assert arguments and not optionals
  endpoint, request, options = arguments
  assert endpoint and request and options

  # Get command and default values
  command = orchestrate.commands.templates.create.Command()
  defaults = command.defaults

  # Verify API call parameters

  # endpoint
  assert endpoint == 'CreateTemplate'

  # request
  assert request.template.project == 'gcloud_project'
  assert request.template.zone == 'gcloud_zone'
  assert request.template.name == 'test_template'
  assert not request.template.image_family
  assert request.template.image_project == defaults['image_project']
  assert request.template.static_ip == defaults['static_ip']
  assert request.template.network == defaults['network']
  assert not request.template.subnetwork
  assert not request.template.scopes
  assert not request.template.metadata
  assert len(request.template.sizes) == 1
  assert request.template.sizes[0].name == defaults['size_name']
  assert request.template.sizes[0].cpus == defaults['cpus']
  assert request.template.sizes[0].memory == defaults['memory']
  assert request.template.sizes[0].disk_size == defaults['disk_size']
  assert request.template.sizes[0].disk_type == defaults['disk_type']
  assert not request.template.sizes[0].gpu_type
  assert request.template.sizes[0].gpu_count == 1
  assert request.template.default_size_name == defaults['size_name']
  assert not request.template.instance_name_pattern

  # options
  assert options.api_host == 'config_host'
  assert options.api_key == 'config_key'


@mock.patch('orchestrate.base.command.OrchestrateCommand.execute')
def test_execution_with_one_custom_size(execute):
  """Verify translation of CLI options into API call parameters.

  Args:
    execute: Mock to verify calls.
  """
  orchestrate.main.main([
      'templates',
      'create',
      'test_template',
      '--cpus=11',
      '--memory=12',
      '--disk-size=13',
      '--disk-type=pd-ssd',
      '--gpu-type=nvidia-tesla-t4-vws',
      '--gpu-count=14',
      '--size-name=user_size',
      '--default-size-name=user_size',
  ])
  assert execute.call_count == 1

  # Unpack and verify parameters to the API call
  arguments, optionals = execute.call_args
  assert arguments and not optionals
  endpoint, request, options = arguments
  assert endpoint and request and options

  # Get command and default values
  command = orchestrate.commands.templates.create.Command()
  defaults = command.defaults

  # Verify API call parameters

  # endpoint
  assert endpoint == 'CreateTemplate'

  # request
  assert request.template.project == 'gcloud_project'
  assert request.template.zone == 'gcloud_zone'
  assert request.template.name == 'test_template'
  assert not request.template.image_family
  assert request.template.image_project == defaults['image_project']
  assert request.template.static_ip == defaults['static_ip']
  assert request.template.network == defaults['network']
  assert not request.template.subnetwork
  assert not request.template.scopes
  assert not request.template.metadata
  assert len(request.template.sizes) == 1
  assert request.template.sizes[0].name == 'user_size'
  assert request.template.sizes[0].cpus == 11
  assert request.template.sizes[0].memory == 12
  assert request.template.sizes[0].disk_size == 13
  assert request.template.sizes[0].disk_type == 'pd-ssd'
  assert request.template.sizes[0].gpu_type == 'nvidia-tesla-t4-vws'
  assert request.template.sizes[0].gpu_count == 14
  assert request.template.default_size_name == 'user_size'
  assert not request.template.instance_name_pattern

  # options
  assert options.api_host == 'config_host'
  assert options.api_key == 'config_key'


@mock.patch('orchestrate.base.command.OrchestrateCommand.execute')
def test_execution_with_many_custom_sizes(execute):
  """Verify translation of CLI options into API call parameters.

  Args:
    execute: Mock to verify calls.
  """
  orchestrate.main.main([
      'templates',
      'create',
      'test_template',
      (
          '--sizes='
          'name=user_size1,cpus=11,memory=12,disk-size=13,'
          'gpu-type=nvidia-tesla-t4-vws,gpu-count=14:'
          'name=user_size2,cpus=21,memory=22,disk-size=23,'
          'gpu-type=nvidia-tesla-t4-vws,gpu-count=24'
      ),
      '--default-size-name=user_size1',
  ])
  assert execute.call_count == 1

  # Unpack and verify parameters to the API call
  arguments, optionals = execute.call_args
  assert arguments and not optionals
  endpoint, request, options = arguments
  assert endpoint and request and options

  # Get command and default values
  command = orchestrate.commands.templates.create.Command()
  defaults = command.defaults

  # Verify API call parameters

  # endpoint
  assert endpoint == 'CreateTemplate'

  # request
  assert request.template.project == 'gcloud_project'
  assert request.template.zone == 'gcloud_zone'
  assert request.template.name == 'test_template'
  assert not request.template.image_family
  assert request.template.image_project == defaults['image_project']
  assert request.template.static_ip == defaults['static_ip']
  assert request.template.network == defaults['network']
  assert not request.template.subnetwork
  assert not request.template.scopes
  assert not request.template.metadata
  assert len(request.template.sizes) == 2
  assert request.template.sizes[0].name == 'user_size1'
  assert request.template.sizes[0].cpus == 11
  assert request.template.sizes[0].memory == 12
  assert request.template.sizes[0].disk_size == 13
  assert request.template.sizes[0].gpu_type == 'nvidia-tesla-t4-vws'
  assert request.template.sizes[0].gpu_count == 14
  assert request.template.sizes[1].name == 'user_size2'
  assert request.template.sizes[1].cpus == 21
  assert request.template.sizes[1].memory == 22
  assert request.template.sizes[1].disk_size == 23
  assert request.template.sizes[1].gpu_type == 'nvidia-tesla-t4-vws'
  assert request.template.sizes[1].gpu_count == 24
  assert request.template.default_size_name == 'user_size1'
  assert not request.template.instance_name_pattern

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
      'create',
      'test_template',
      '--project=user_project',
      '--zone=user_zone',
      '--image-family=user_image_family',
      '--image-project=user_image_project',
      '--static-ip',
      '--network=user_network',
      '--subnetwork=user_subnetwork',
      '--instance-name-pattern=test-{user}',
      '--scopes=user_scope1,user_scope2',
      '--metadata=user_key1=user_value1,user_key2=user_value2',
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

  # Get command and default values
  command = orchestrate.commands.templates.create.Command()
  defaults = command.defaults

  # Verify API call parameters

  # endpoint
  assert endpoint == 'CreateTemplate'

  # request
  assert request.template.project == 'user_project'
  assert request.template.zone == 'user_zone'
  assert request.template.name == 'test_template'
  assert request.template.image_family == 'user_image_family'
  assert request.template.image_project == 'user_image_project'
  assert request.template.static_ip
  assert request.template.network == 'user_network'
  assert request.template.subnetwork == 'user_subnetwork'
  assert len(request.template.scopes) == 2
  assert request.template.scopes == ['user_scope1', 'user_scope2']
  assert len(request.template.metadata) == 2
  assert request.template.metadata[0].key == 'user_key1'
  assert request.template.metadata[0].value == 'user_value1'
  assert request.template.metadata[1].key == 'user_key2'
  assert request.template.metadata[1].value == 'user_value2'
  assert len(request.template.sizes) == 1
  assert request.template.sizes[0].name == defaults['size_name']
  assert request.template.sizes[0].cpus == defaults['cpus']
  assert request.template.sizes[0].memory == defaults['memory']
  assert request.template.sizes[0].disk_size == defaults['disk_size']
  assert not request.template.sizes[0].gpu_type
  assert request.template.sizes[0].gpu_count == 1
  assert request.template.default_size_name == defaults['size_name']
  assert request.template.instance_name_pattern == 'test-{user}'

  # options
  assert options.api_host == 'user_api_host'
  assert options.api_key == 'user_api_key'

