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

"""Implements the Orchestrate API Service."""

import uuid

import orchestrate_pb2

from googleapiclient import discovery
from googleapiclient import errors
from oauth2client.client import GoogleCredentials
from google.cloud import error_reporting

error_client = error_reporting.Client()

# Connect to Google Cloud Compute Engine API using the environment's service
# account.
credentials = GoogleCredentials.get_application_default()
compute = discovery.build('compute', 'v1', credentials=credentials)


class OrchestrateTemplateCreationError(Exception):
  """Provides detailed message on error occurred during template creation.
  """
  pass


def run(request, context):
  """Creates a template.

  Args:
    request (orchestrate_pb2.CreateTemplateRequest): Request payload.
    context: Context.

  Returns:
    A orchestrate_pb2.CreateTemplate with the status of the request.
  """
  template = request.template
  print('Orchestrate.CreateTemplate name={name} project={project}'.format(
      name=template.name,
      project=template.project,
      ))

  request_id = uuid.uuid4().hex

  try:
    # Make sure data is valid before creating individual sizes - don't want to
    # clean-up half-way or leave incomplete template families.
    for size in template.sizes:
      validate_metadata(template, size)

    # Data checks out. let's create all template sizes.
    for size in template.sizes:
      create_template_size(template, size)

    return orchestrate_pb2.CreateTemplateResponse(
        status='CREATED',
        request_id=str(request_id),
        )

  except errors.HttpError as exception:
    if exception.resp.status == 409:
      message = 'A template with name {name} already exists.'.format(
          name=template.name)
      raise OrchestrateTemplateCreationError(message)
    else:
      raise


def create_template_size(template, size):
  """Creates instance template for the given size.

  Args:
    template: Creation parameters.
    size: Size parameters to use.

  Returns:
    Operation performing template creation.
  """
  print('Creating template {name} size {size_name}'.format(
      name=template.name, size_name=size.name))
  payload = build_template_payload(template, size)
  operation = compute.instanceTemplates().insert(
      project=template.project,
      body=payload,
      ).execute()
  print('Started operation {name}'.format(name=operation['name']))
  return operation


def build_template_payload(template, size):
  """Returns a dict with all creation parameters.

  Payload format required by the POST instances.insert endpoint.
  https://cloud.google.com/compute/docs/reference/rest/v1/instanceTemplates/insert

  Args:
    template: Creation parameters.
    size: Size parameters.
  """
  name = '{name}-{size_name}'.format(name=template.name, size_name=size.name)

  # Find latest image
  response = compute.images().getFromFamily(
      project=template.image_project,
      family=template.image_family,
      ).execute()
  source_image = response['selfLink']

  # Normalize size parameters
  memory = size.memory*1024     # gb to mb
  disk_size = size.disk_size    # gb

  # InstanceTemplates.insert expects machineType to be a name,
  # it does NOT support URL-based custom machines, e.g.
  # projects/orchestrate-test-1/zones/us-central1-a/machineTypes/custom-6-32768
  # Therefore, store this metadata as orchestrate_machine_type
  # TODO(b/137211294) orchestrate instances create would have to pay attention to
  # this value and override the machineType from this template.
  machine_type = 'custom-{cpus}-{memory}'.format(
      cpus=size.cpus,
      memory=memory,
      )

  is_default_size = size.name == template.default_size_name

  # Prepare metadata
  metadata = []
  # Metadata intended for the instance itself
  for item in template.metadata:
    metadata.append(dict(key=item.key, value=item.value))
  # Orchestrate-specific metadata that extends the properties stored in the
  # instanceTemplate itself. Insert after the instance metadata to ensure
  # that clients do not accidentally override orchestrate-specific entries.
  metadata += [
      dict(key='orchestrate_template', value=True),
      dict(key='orchestrate_default_size', value=is_default_size),
      dict(key='orchestrate_machine_type', value=machine_type),
      dict(key='orchestrate_gpu_type', value=size.gpu_type),
      dict(key='orchestrate_gpu_count', value=size.gpu_count),
      dict(key='orchestrate_network', value=template.network),
  ]
  if template.instance_name_pattern:
    metadata.append(dict(key='orchestrate_instance_name_pattern',
                         value=template.instance_name_pattern))

  region = '-'.join(template.zone.split('-')[:2])
  region_url = 'projects/{project}/regions/{region}'.format(
      project=template.project,
      region=region,
      )
  network = 'projects/{project}/global/networks/{network}'.format(
      project=template.project,
      network=template.network,
      )
  subnetwork = '{region_url}/subnetworks/{subnetwork}'.format(
      region_url=region_url,
      subnetwork=template.network,
      )

  guest_accelerators = []
  if size.gpu_type:
    guest_accelerators.append(dict(
        acceleratorType='{gpu_type}'.format(gpu_type=size.gpu_type),
        acceleratorCount=size.gpu_count,
    ))

  # POST https://www.googleapis.com/compute/v1/
  #       projects/{project}/zones/us-central1-a/instanceTemplates
  payload = dict(
      name=name,
      description='Orchestrate template {name} size {size_name}'.format(
          name=name, size_name=size.name),
      properties=dict(
          metadata=dict(items=metadata),
          tags=dict(
              items=[
                  'https-server',
              ],
          ),
          canIpForward=True,
          networkInterfaces=[
              dict(
                  network=network,
                  subnetwork=subnetwork,
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
          labels=dict(),
          scheduling=dict(
              preemptible=False,
              onHostMaintenance='TERMINATE',
              automaticRestart=True,
              nodeAffinities=[],
          ),
          deletionProtection=False,
          serviceAccounts=[
              # TODO(b/138243681) Ideally this should be configured to run
              # with the "orchestrate" service account from the main Orchestrate
              # project. Use the one from orchestrated project for now.
              dict(
                  email='orchestrate@{project}.iam.gserviceaccount.com'.format(
                      project=template.project),
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
          # Size-related parameters
          machineType='n1-standard-8',
          guestAccelerators=guest_accelerators,
          disks=[
              dict(
                  type='PERSISTENT',
                  boot=True,
                  mode='READ_WRITE',
                  autoDelete=True,
                  initializeParams=dict(
                      sourceImage=source_image,
                      diskType='pd-standard',
                      diskSizeGb=disk_size,
                  ),
              ),
          ],
      ),
  )

  return payload


def validate_metadata(template, size):
  """Validates metadata.

  Catch any errors or invalid input that would cause a template with incorrect
  information being created and propagated down to instances.

  Args:
    template: Creation parameters.
    size: Size parameters to use.

  Returns:
    Nothing. The function returns normally if everything is correct. Raises an
    exception otherwise.

  Raises:
    OrchestrateTemplateCreationError: If any of the metadata is invalid.
  """
  print('Validating metadata for template {name} size {size_name}'.format(
      name=template.name, size_name=size.name))

  # (b/148229648) Does gpu_type exist?

  if size.gpu_type:
    response = compute.acceleratorTypes().list(
        project=template.project,
        zone=template.zone,
        ).execute()

    gpu_types = [gpu['name'] for gpu in response['items']]

    if size.gpu_type not in gpu_types:
      message = (
          '{gpu_type} is not a valid GPU type or is not available in project'
          ' {project} zone {zone}. Available options are: {gpu_types}'
          ).format(
              project=template.image_project,
              zone=template.zone,
              gpu_type=size.gpu_type,
              gpu_types=', '.join(gpu_types),
              )
      raise OrchestrateTemplateCreationError(message)
