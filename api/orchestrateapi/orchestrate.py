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


import orchestrate_pb2_grpc
from orchestrateapi.commands import images
from orchestrateapi.commands import instances
from orchestrateapi.commands import projects
from orchestrateapi.commands import templates

from google.cloud import error_reporting

error_client = error_reporting.Client()


def log_errors(function):
  """Explicitly log unhandled exceptions to Stackdriver's Error reporting.

  This happens automatically for Cloud Functions but not for code running
  in Kubernetes.

  Args:
    function: Decorated function.

  Returns:
    Decoratored function.
  """
  def wrapper(*arguments, **kwargs):
    try:
      return function(*arguments, **kwargs)
    except:
      error_client.report_exception()
      raise
  return wrapper


class Orchestrate(orchestrate_pb2_grpc.OrchestrateServicer):
  """Implements the Orchestrate API Service endpoints.
  """

  @log_errors
  def CreateImage(self, request, context):
    """Creates an image asynchronously.

    Args:
      request (orchestrate_pb2.CreateImageRequest): Request payload.
      context: Context.

    Returns:
      A orchestrate_pb2.CreateImageResponse with the status of the request.
    """
    return images.create.run(request, context)

  @log_errors
  def CreateTemplate(self, request, context):
    """Creates a template.

    Args:
      request (orchestrate_pb2.CreateTemplateRequest): Request payload.
      context: Context.

    Returns:
      A orchestrate_pb2.CreateTemplateResponse with the status of the request.
    """
    return templates.create.run(request, context)

  @log_errors
  def DeleteTemplate(self, request, context):
    """Deletes a template.

    Args:
      request (orchestrate_pb2.DeleteTemplateRequest): Request payload.
      context: Context.

    Returns:
      A orchestrate_pb2.DeleteTemplateResponse with the status of the request.
    """
    return templates.delete.run(request, context)

  @log_errors
  def CreateInstance(self, request, context):
    """Creates an instance.

    Args:
      request (orchestrate_pb2.CreateInstanceRequest): Request payload.
      context: Context.

    Returns:
      A orchestrate_pb2.CreateInstanceResponse with the status of the request.
    """
    return instances.create.run(request, context)

  @log_errors
  def RegisterProject(self, request, context):
    """Registers a project.

    Args:
      request (orchestrate_pb2.RegisterProjectRequest): Request payload.
      context: Context.

    Returns:
      A orchestrate_pb2.RegisterProjectResponse with the status of the request.
    """
    return projects.register.run(request, context)

  @log_errors
  def DeregisterProject(self, request, context):
    """Deregisters a project.

    Args:
      request (orchestrate_pb2.DeregisterProjectRequest): Request payload.
      context: Context.

    Returns:
      A orchestrate_pb2.DeregisterProjectResponse with the status of the request.
    """
    return projects.deregister.run(request, context)
