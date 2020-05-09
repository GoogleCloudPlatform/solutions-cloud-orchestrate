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

"""Base Orchestrate command interface.
"""

import logging
from orchestrate.service import orchestrate_pb2_grpc
import grpc

log = logging.getLogger(__name__)


class OrchestrateCommand:
  """Orchestrate command interface."""

  @property
  def description(self):
    raise NotImplementedError()

  @property
  def defaults(self):
    """Returns default option values."""
    return dict()

  @property
  def options(self):
    """Returns command parser options."""
    return []

  def run(self, options, arguments):
    """Executes command.

    Args:
      options: Command-line options.
      arguments: Command-line positional arguments

    Returns:
      True if successful. False, otherwise.
    """
    raise NotImplementedError()

  def execute(self, endpoint, request, options):
    """Sends a gRPC request to the API.

    Args:
      endpoint: Name of API endpoint to execute.
      request: Request payload compatible with endpoint.
      options: Command-line and configuration options.

    Returns:
      A response object whose type depends on the endpoint.
    """
    channel = grpc.insecure_channel(options.api_host)
    service = orchestrate_pb2_grpc.OrchestrateStub(channel)

    service_metadata = []
    if options.api_key:
      service_metadata.append(('x-api-key', options.api_key))

    log.info('Executing: %s', endpoint)
    method = getattr(service, endpoint)
    response = method(request, metadata=service_metadata)

    return response
