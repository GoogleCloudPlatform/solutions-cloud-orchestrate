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

from google.cloud import error_reporting
from google.cloud import pubsub_v1
from google.protobuf.json_format import MessageToJson

from orchestrateapi import environ
from orchestrateapi import orchestrate_pb2


TOPIC_CREATE_IMAGE = 'image_provisioning_start'

error_client = error_reporting.Client()


def run(request, context):
  """Creates an image asynchronously.

  Args:
    request (orchestrate_pb2.CreateImageRequest): Request payload.
    context: Context.

  Returns:
    A orchestrate_pb2.CreateImageResponse with the status of the request.
  """
  print('Orchestrate.CreateImage name={name} project={project}'.format(
      name=request.image.name,
      project=request.image.project,
      ))
  steps = ', '.join(request.image.steps) or 'all'
  print('Installation steps: {}'.format(steps))

  publisher = pubsub_v1.PublisherClient()
  topic = publisher.topic_path(environ.ORCHESTRATE_PROJECT, TOPIC_CREATE_IMAGE)
  print('Sending message to {}'.format(TOPIC_CREATE_IMAGE))

  data = MessageToJson(request, preserving_proto_field_name=True).encode()
  future = publisher.publish(topic, data=data)
  result = future.result()
  print('Message publish result: {}'.format(result))

  return orchestrate_pb2.CreateImageResponse(
      status='SUBMITTED',
      request_id=result,
      )
