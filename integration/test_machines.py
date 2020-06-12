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

"""Test basic template and machine orchestration."""

import logging
import subprocess
import time
import uuid

import orchestrateapi.main
import orchestrate.main

import pytest


log = logging.getLogger(__name__)


def wait(seconds, message):
  log.info('Waiting %ss for %s', seconds, message)
  time.sleep(seconds)


def run(command, pii=False):
  """Runs given system command.

  Args:
    command: Command to run.
    pii: Logs command redacted to prevent any PII from leaking in plain text.
         By default it logs the command verbatim. Please make sure to set this
         to True if the command being executed contains passwords or any other
         sensitive information.
  """
  message = command if not pii else '[redacted due to pii]'
  log.debug('Executing: %(message)s', dict(message=message))
  subprocess.check_call(command, shell=True)


def test_machines(tag):
  """Verify creation of templates and machines.

  Args:
    tag: Unique tag for this test.
  """
  zone = 'us-west2-b'
  template_name = tag
  log.info('Creating template %s', template_name)
  orchestrate.main.main([
      'templates',
      'create',
      template_name,
      '--image-project=centos-cloud',
      '--image-family=centos-7',
      '--cpus=4',
      '--memory=20',
      '--disk-size=20',
      '--metadata=key1=value1,key2=value2',
      '--zone={}'.format(zone),
  ])
  wait(2, 'template creation')

  instance_name = '{tag}-1'.format(tag=tag)
  log.info('Creating instance %s', instance_name)
  orchestrate.main.main([
      'instances',
      'create',
      template_name,
      '--name={}'.format(instance_name),
      '--zone={}'.format(zone),
  ])
  wait(30, 'image creation')

  log.info('Deleting template %s', template_name)
  orchestrate.main.main([
      'templates',
      'delete',
      template_name,
  ])
  wait(2, 'template deletion')

  log.info('Deleting instance %s', instance_name)
  command = (
      'gcloud compute instances delete {instance_name} --zone={zone} --quiet'
      ).format(
          instance_name=instance_name,
          zone=zone,
          )
  run(command)
