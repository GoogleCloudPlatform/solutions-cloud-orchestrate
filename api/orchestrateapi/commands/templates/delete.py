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


class OrchestrateTemplateDeletionError(Exception):
  """Provides detailed message on error occurred during template deletion.
  """
  pass


def run(request, context):
  """Deletes a template.

  Args:
    request (orchestrate_pb2.CreateTemplateRequest): Request payload.
    context: Context.

  Returns:
    A orchestrate_pb2.DeleteTemplate with the status of the request.
  """
  print('Orchestrate.DeleteTemplate name={name} project={project}'.format(
      name=request.name,
      project=request.project,
      ))

  request_id = uuid.uuid4().hex

  try:
    names = get_instance_template_names(request)
    for name in names:
      print('Deleting template {name}'.format(name=name))
      operation = compute.instanceTemplates().delete(
          project=request.project,
          instanceTemplate=name,
          ).execute()
      print('Started operation {name}'.format(name=operation['name']))

    return orchestrate_pb2.DeleteTemplateResponse(
        status='DELETED',
        request_id=str(request_id),
        )

  except errors.HttpError as exception:
    if exception.resp.status == 404:
      message = 'Could not find template with name {name}.'.format(
          name=request.name)
      raise OrchestrateTemplateDeletionError(message)
    else:
      raise


def get_instance_template_names(request):
  """Returns names of all instance templates associated with Orchestrate template.

  Args:
    request: Deletion request parameters
  """
  print('Finding Orchestrate templates by name {name}'.format(name=request.name))
  result = compute.instanceTemplates().list(
      project=request.project,
      filter='name = {name}-*'.format(name=request.name),
      ).execute()
  names = [item['name'] for item in result.get('items', [])]
  return names
