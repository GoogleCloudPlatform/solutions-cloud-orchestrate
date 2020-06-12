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
from googleapiclient import discovery
from oauth2client.client import GoogleCredentials
from google.cloud import error_reporting

from orchestrateapi import environ
from orchestrateapi import orchestrate_pb2


error_client = error_reporting.Client()

# Connect to Google Cloud Compute Engine API using the environment's service
# account.
credentials = GoogleCredentials.get_application_default()
resource_manager = discovery.build('cloudresourcemanager', 'v1',
                                   credentials=credentials,
                                   cache_discovery=False)
storage = discovery.build('storage', 'v1', credentials=credentials,
                          cache_discovery=False)


def run(request, context):
  """Deregister a project.

  On project Orchestrate project (environ.ORCHESTRATE_PROJECT):
  - Revoke orchestrate@PROJECT_ID service account roles:
    - Pub/Sub Publisher
  - Revoke access to Orchestrate bucket (environ.ORCHESTRATE_BUCKET) to
    orchestrate@PROJECT_ID service account with role:
    - Storage Object Viewer

  Args:
    request (orchestrate_pb2.DeregisterProjectRequest): Request payload.
    context: Context.

  Returns:
    A orchestrate_pb2.DeregisterProjectResponse with the status of the request.
  """
  print('Orchestrate.DeregisterProject project={project}'.format(
      project=request.project,
      ))

  request_id = uuid.uuid4().hex

  account = (
      'serviceAccount:orchestrate@{project}.iam.gserviceaccount.com').format(
          project=request.project)

  role = 'projects/{project}/roles/orchestrate.project'.format(
      project=environ.ORCHESTRATE_PROJECT)
  remove_project_iam_binding(account, role)
  remove_storage_iam_binding(account, 'roles/storage.objectViewer')

  return orchestrate_pb2.RegisterProjectResponse(
      status='DEREGISTERED',
      request_id=str(request_id),
      )


def remove_project_iam_binding(member, role):
  """Remove policy binding.

  Args:
    member: Account, e.g. user:joe@doe.com, serviceAccount:..., etc.
    role: Role.
  """
  # IMPORTANT: Get existing policy and remove from it.
  # DO NOT just send a small policy with the member we want to add. Doing so
  # will override all other bindings potentially damaging access to the
  # resource.
  policy = resource_manager.projects().getIamPolicy(
      resource=environ.ORCHESTRATE_PROJECT, body=dict()).execute()

  if remove_iam_binding(policy, member, role):
    resource_manager.projects().setIamPolicy(
        resource=environ.ORCHESTRATE_PROJECT, body=dict(policy=policy)).execute()


def remove_storage_iam_binding(member, role):
  """Remove policy binding.

  Args:
    member: Account, e.g. user:joe@doe.com, serviceAccount:..., etc.
    role: Role.
  """
  # IMPORTANT: Get existing policy and append to it.
  # DO NOT just send a small policy with the member we want to add. Doing so
  # will override all other bindings potentially damaging access to the
  # resource.
  policy = storage.buckets().getIamPolicy(
      bucket=environ.ORCHESTRATE_BUCKET).execute()

  if remove_iam_binding(policy, member, role):
    storage.buckets().setIamPolicy(
        bucket=environ.ORCHESTRATE_BUCKET, body=policy).execute()


def remove_iam_binding(policy, member, role):
  """Removes binding from given policy.

  Args:
    policy: Policy.
    member: Account, e.g. user:joe@doe.com, serviceAccount:..., etc.
    role: Role

  Returns:
    True if binding was removed. False, if binding was not present in policy.
  """
  # Check if member is already bound to the role and remove it
  for binding in policy['bindings']:
    if binding['role'] == role:
      if member in binding['members']:
        # Member is bound to role. Remove it.
        binding['members'].remove(member)
        # Remove binding altogether if no more members left.
        if not binding['members']:
          policy['bindings'].remove(binding)
        return True

  return False
