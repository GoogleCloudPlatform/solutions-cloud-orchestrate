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

"""Starts provisioning an image."""

import base64
import json
import logging
import os
import uuid
from googleapiclient import discovery
from googleapiclient import errors
from oauth2client.client import GoogleCredentials
from google.cloud import error_reporting

# Silence warnings from Google API internals.
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)


class OrchestrateImageProvisioningError(Exception):
  """Provides detailed message on error occurred during image provisioning.
  """
  pass


class ProvisionImageService:
  """Installs domain-specific software on an image."""

  def __init__(self):
    # Connect to Google Cloud Compute Engine API using the environment's service
    # account.
    credentials = GoogleCredentials.get_application_default()
    self.compute = discovery.build('compute', 'v1', credentials=credentials)

  def build_instance_insert_payload(self, image, request_id):
    """Returns a dict with all the parameters to create an instance.

    Payload format required by the POST instances.insert endpoint.
    https://cloud.google.com/compute/docs/reference/rest/v1/instances/insert

    Args:
      image (dict): Creation parameters.
      request_id (str): Unique request ID for this operation.

    Raises:
      OrchestrateImageProvisioningError: If the provisioning instance could not be
        successfully started.
    """
    region = '-'.join(image['zone'].split('-')[:2])
    region_url = 'projects/{project}/regions/{region}'.format(
        project=image['project'],
        region=region,
        )

    zone_url = 'projects/{project}/zones/{zone}'.format(
        project=image['project'],
        zone=image['zone'],
        )

    image_payload = json.dumps(image).encode()
    image_payload = base64.b64encode(image_payload).decode()

    # Prepare metadata
    # provisioning script
    bucket = 'gs://{project}'.format(project=image['api_project'])
    script = '{bucket}/remotedesktopinstall.py'.format(bucket=bucket)
    metadata = [
        dict(
            key='orchestrate_request_id',
            value=str(request_id),
        ),
        dict(
            key='orchestrate_project',
            value=image['api_project'],
        ),
        dict(
            key='orchestrate_image',
            value=str(image_payload),
        ),
        dict(
            key='startup-script-url',
            value=script,
        ),
    ]
    # license strings, etc.
    metadata.extend(image.get('metadata', []))
    # specific installation steps, if any. No explicit steps means all, i.e.
    # installing everything.
    if image.get('steps', []):
      metadata.append(
          dict(
              key='steps',
              value=':'.join(image['steps']),
              )
          )

    # Find latest image
    response = self.compute.images().getFromFamily(
        project=image['image_project'],
        family=image['image_family'],
        ).execute()
    source_image = response['selfLink']

    gpu_type = self.select_gpu_type(image['project'], image['zone'])
    if not gpu_type:
      message = (
          'There are no suitable GPU types with Virtual Workstation support'
          ' available in project {project} zone {zone} in order to create'
          ' the temporary provisioning image for your image {image}. Please'
          ' consider creating image in a different zone. For more information'
          ' visit https://cloud.google.com/compute/docs/gpus/'
          ).format(**image)
      raise OrchestrateImageProvisioningError(message)
    accelerator_type = \
        '{zone_url}/acceleratorTypes/{gpu_type}'.format(
            zone_url=zone_url,
            gpu_type=gpu_type,
            )

    # POST https://www.googleapis.com/compute/v1/
    #       projects/{project}/zones/us-central1-a/instances
    payload = dict(
        name=image['instance_name'],
        machineType='{zone_url}/machineTypes/custom-6-32768'.format(
            zone_url=zone_url),
        metadata=dict(items=metadata),
        tags=dict(
            items=[
                'https-server',
            ],
        ),
        guestAccelerators=[
            dict(
                acceleratorType=accelerator_type,
                acceleratorCount=1,
            ),
        ],
        disks=[
            dict(
                type='PERSISTENT',
                boot=True,
                mode='READ_WRITE',
                autoDelete=True,
                deviceName=image['name'],
                initializeParams=dict(
                    sourceImage=source_image,
                    diskType='{zone_url}/diskTypes/pd-standard'.format(
                        zone_url=zone_url),
                    diskSizeGb=image['disk_size'],
                ),
            ),
        ],
        canIpForward=True,
        networkInterfaces=[
            dict(
                subnetwork='{region_url}/subnetworks/{network}'.format(
                    region_url=region_url,
                    network=image['network'],
                    ),
                accessConfigs=[
                    dict(
                        name='External NAT',
                        type='ONE_TO_ONE_NAT',
                        networkTier='PREMIUM',
                    )
                ],
                aliasIpRanges=[],
            ),
        ],
        description='Orchestrate temporary provisioning image.',
        labels=dict(),
        scheduling=dict(
            preemptible=False,
            onHostMaintenance='TERMINATE',
            automaticRestart=True,
            nodeAffinities=[],
        ),
        deletionProtection=True,
        serviceAccounts=[
            dict(
                # TODO(b/138243681) Ideally this should be configured to run
                # with the "orchestrate" service account from the main Orchestrate
                # project. Use the one from orchestrated project for now.
                email='orchestrate@{project}.iam.gserviceaccount.com'.format(
                    **image),
                scopes=[
                    'https://www.googleapis.com/auth/devstorage.read_only',
                    'https://www.googleapis.com/auth/logging.write',
                    'https://www.googleapis.com/auth/monitoring.write',
                    'https://www.googleapis.com/auth/servicecontrol',
                    'https://www.googleapis.com/auth/service.management.readonly',
                    'https://www.googleapis.com/auth/trace.append',
                    'https://www.googleapis.com/auth/compute',
                    'https://www.googleapis.com/auth/cloud-platform',
                ],
            ),
        ],
    )

    return payload

  def select_gpu_type(self, project, zone):
    """Select GPU type with virtual workstation support available in given zone.

    Args:
      project: Project
      zone: Zone

    Returns:
      A string with the name of the GPU type to use.
    """
    # (b/148285282) Find suitable GPU type based on zone. Try P4 if available.
    # Otherwise, assume T4. See: https://cloud.google.com/compute/docs/gpus/
    response = self.compute.acceleratorTypes().list(
        project=project,
        zone=zone,
        ).execute()
    for gpu in response['items']:
      # e.g. nvidia-tesla-t4-vws to ['nvidia', 'tesla', 't4', 'vws']
      gpu_name_parts = gpu['name'].split('-')
      if gpu['name'].endswith('-vws') and gpu_name_parts[2] in ('t4', 'p4'):
        return gpu['name']
    return None

  def run(self, parameters):
    """Starts image provisioning process.

    Args:
      parameters (dict): Creation parameters.

    Returns:
      An Operation instance.
    """
    image = parameters['image']
    message = 'Provisioning image name={name} project={project}'.format(**image)
    print(message)
    print('Image parameters: {}'.format(image))
    steps = ', '.join(image.get('steps', [])) or 'all'
    print('Installation steps: {}'.format(steps))

    request_id = uuid.uuid4()
    print('Provisioning request_id={}'.format(request_id))

    instance_name = image.get('instance_name')
    if not instance_name:
      instance_name = 'orchestrate-image-{name}'.format(name=image['name'])
      image['instance_name'] = instance_name

    payload = self.build_instance_insert_payload(image, request_id)

    try:
      operation = self.compute.instances().insert(
          project=image['project'],
          zone=image['zone'],
          body=payload,
          ).execute()
      print('Started operation {name}'.format(name=operation['name']))
      return operation
    except errors.HttpError as exception:
      if exception.resp.status == 409:
        message = (
            'An image with name {name} appears to be currently being created.'
            ' Or, a previous attempt failed and the temporary provisioning'
            ' image is still around. Please check your Compute Engine instances'
            ' and look for a VM with name {instance_name}.'
            ).format(
                name=image['name'],
                instance_name=image['instance_name'],
                )
        # Explicitly discarding exception chain because Stackdriver Error
        # Reporting is always showing and grouping on the first exception which
        # is too generic and low level. It obscures the higher-level more
        # meaningful exception being raised as the last in the stack. (The
        # current Stackdriver behaviour seems at odds with PEP-314
        # https://www.python.org/dev/peps/pep-3134/)
        # Let's work around it especially since the chain is just two levels in
        # this case.
        raise OrchestrateImageProvisioningError(message) from None
      else:
        raise


def main(message, context):
  """Starts provisioning an image.

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

    # Start image provisioning
    ProvisionImageService().run(parameters)

  except (TypeError, KeyError, json.decoder.JSONDecodeError) as exception:
    logging.error(exception)
    error_reporting.Client().report_exception()
    # Do not retry when payload is malformed

  return True
