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

"""Creates an actual image from a disk provisioned by image_provisioning_start.

"""

import base64
import datetime
import json
import logging
import os
import time
from googleapiclient import discovery
from oauth2client.client import GoogleCredentials
from google.cloud import error_reporting

# Silence warnings from Google API internals.
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)


class OrchestrateImageProvisioningError(Exception):
  """Provides detailed message on error occurred during image provisioning.
  """
  pass


class CreateImageService:
  """Create an image from the temporary provisioning instance disk."""

  def __init__(self):
    # Connect to Google Cloud Compute Engine API using the environment's service
    # account.
    credentials = GoogleCredentials.get_application_default()
    self.compute = discovery.build('compute', 'v1', credentials=credentials)

  def wait_for_operation(self, operation, project, scope='global',
                         scope_value=None, max_seconds=500):
    """Waits for give operation to finish.

    Polls operation status every seconds until DONE or max_seconds is up.

    Args:
      operation: Dictionary representing an operation in GCE as returned by REST
        API calls.
      project: Project.
      scope: One of: global, region, or zone. Default is global.
      scope_value: None if scope is global, region or zone otherwise depending
        on the value of the scope parameter. Default is None.
      max_seconds: Maximum wait time.

    Returns:
      Resulting operation.

    Raises:
      RuntimeError: Operation timed out or was unable to stop.
    """
    print('Waiting on operation={name}'.format(name=operation['name']))

    if scope == 'region':
      operations = self.compute.regionOperations()
      scope_values = dict(region=scope_value)
    elif scope == 'zone':
      operations = self.compute.zoneOperations()
      scope_values = dict(zone=scope_value)
    else:
      operations = self.compute.globalOperations()
      scope_values = dict()

    request = operations.get(project=project, **scope_values,
                             operation=operation['name'])
    wait_time = 1      # Time to wait between polls
    elapsed_time = 0   # Total time waited
    while elapsed_time < max_seconds:
      response = request.execute()
      if response['status'] == 'DONE':
        if 'error' in response:
          message = response['error']
          logging.error(message)
          raise RuntimeError(message)
        # Ok, operation is done with no errors.
        print('Operation {name} completed successfully'.format(
            name=operation['name']))
        return response
      # Wait before we poll status again
      time.sleep(wait_time)
      elapsed_time += wait_time
    message = 'Time out waiting for operation {operation}'.format(
        operation=operation['name'],
        )
    raise RuntimeError(message)

  def stop_instance(self, image, wait=True):
    """Stops image containing the provisioned disk.

    Args:
      image: Image creation parameters.
      wait: Wait for operation to finish when True.
    """
    print('Stopping provisioning instance={instance_name}'.format(
        instance_name=image['instance_name']))
    operation = self.compute.instances().stop(
        project=image['project'],
        zone=image['zone'],
        instance=image['instance_name']).execute()
    print('Started operation={name}'.format(name=operation['name']))

    if wait:
      self.wait_for_operation(operation, project=image['project'], scope='zone',
                              scope_value=image['zone'])

  def create_image_from_instance(self, image, wait=True):
    """Creates an image from the provisioning image disk.

    Args:
      image (dict): Image creation parameters.
      wait (bool): Indicates whether to wait for operation to finish or not.

    Returns:
      An Operation instance.
    """
    print('Creating image={name} from instance={instance_name}'.format(
        name=image['name'],
        instance_name=image['instance_name'],
        ))

    now = datetime.datetime.now()
    timestamp = now.strftime('%Y%m%dt%H%M%S')
    image_version = '{name}-{timestamp}'.format(
        name=image['name'],
        timestamp=timestamp,
        )
    source_disk = 'projects/{project}/zones/{zone}/disks/{name}'.format(
        project=image['project'],
        zone=image['zone'],
        name=image['instance_name'],
        )
    labels = [
        dict(orchestrate_os=image['os_type'].lower()),
    ]

    payload = dict(
        family=image['name'],
        name=image_version,
        sourceDisk=source_disk,
        description='Orchestrate image.',
        labels=labels,
        )

    operation = self.compute.images().insert(
        project=image['project'],
        body=payload).execute()
    print('Started operation {name}'.format(name=operation['name']))

    if wait:
      self.wait_for_operation(operation, project=image['project'],
                              scope='global')

  def set_deletion_protection(self, image, protection=True, wait=True):
    """Delete instance containing the provisioned disk.

    Args:
      image: Image creation parameters.
      protection: Boolean indicating whether deletion protections is enabled or
        not.
      wait: Wait for operation to finish when True.
    """
    print('Removing deletion protection from instance={instance_name}'.format(
        instance_name=image['instance_name']))
    operation = self.compute.instances().setDeletionProtection(
        project=image['project'],
        zone=image['zone'],
        resource=image['instance_name'],
        deletionProtection=protection).execute()
    print('Started operation={name}'.format(name=operation['name']))

    if wait:
      self.wait_for_operation(operation, project=image['project'], scope='zone',
                              scope_value=image['zone'])

  def delete_instance(self, image, wait=True):
    """Delete instance containing the provisioned disk.

    Args:
      image: Image creation parameters.
      wait: Wait for operation to finish when True.
    """
    print('Deleting provisioning instance={instance_name}'.format(
        instance_name=image['instance_name']))
    operation = self.compute.instances().delete(
        project=image['project'],
        zone=image['zone'],
        instance=image['instance_name']).execute()
    print('Started operation={name}'.format(name=operation['name']))

    if wait:
      self.wait_for_operation(operation, project=image['project'], scope='zone',
                              scope_value=image['zone'])

  def run(self, image):
    """Creates an image from a provisioned disk.

    Args:
      image (dict): Image creation parameters.
    """
    message = 'Creating image name={name} project={project}'.format(**image)
    print(message)

    self.stop_instance(image)
    self.create_image_from_instance(image)
    self.set_deletion_protection(image, protection=False, wait=True)
    self.delete_instance(image, wait=False)


def main(message, context):
  """Creates an image from a provisioned disk.

  Args:
    message (dict): PubsubMessage event payload.
    context: Pub/Sub event context.

  Returns:
    True if successful, False otherwise.

  Raises:
    RuntimeError: If not data or unaccounted error cases.
  """
  if not message or 'data' not in message:
    raise RuntimeError('Missing data in message.')

  try:
    print('Running {project}.{function}'.format(
        project=os.environ.get('GCP_PROJECT'),
        function=os.environ.get('FUNCTION_NAME'),
        ))

    # Get image creation parameters
    data = message['data'].encode()
    payload = base64.b64decode(data).decode()
    parameters = json.loads(payload)
    image = parameters['image'].encode()
    image = base64.b64decode(image).decode()
    image = json.loads(image)
    print('Image {}'.format(image))
    print('Provisioning image finished: request_id={request_id}'
          ' success={success} project={project} zone={zone}'
          ' name={name} instance_name={instance_name}'.format(
              request_id=parameters['request_id'],
              success=parameters['success'],
              project=image['project'],
              zone=image['zone'],
              name=image['name'],
              instance_name=image['instance_name'],
              ))

    # Create image
    if parameters['success']:
      CreateImageService().run(image)
    else:
      message = (
          'Failed to create image with name {name}. Errors occurred while'
          ' installing software. For more information please search logs for'
          ' errors on instance {instance_name}.'
          ).format(
              name=image['name'],
              instance_name=image['instance_name'],
              )
      raise OrchestrateImageProvisioningError(message)

  except (TypeError, KeyError, json.decoder.JSONDecodeError,
          OrchestrateImageProvisioningError) as exception:
    logging.error(exception)
    error_reporting.Client().report_exception()
    # Let it continue so that function is not retry when payload is malformed
    # and other known error conditions that can not recover from.

  return True
