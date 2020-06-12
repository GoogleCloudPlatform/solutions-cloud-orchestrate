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

"""Serves the Orchestrate API Service."""

from concurrent import futures
import time

import grpc

from orchestrateapi import orchestrate_pb2_grpc
from orchestrateapi import servicer


def start_server():
  """Returns a GRPC server instance initialized and ready to server requests.
  """
  print('Starting local Orchestrate API')
  port = 50051
  server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
  orchestrate_pb2_grpc.add_OrchestrateServicer_to_server(
      servicer.Orchestrate(), server)
  server.add_insecure_port('[::]:{}'.format(port))
  server.start()
  print('Listening on port {}'.format(port))
  return server


def stop_server(server):
  server.stop(grace=0)


def keep_alive():
  """Keep process alive until Ctrl+C or process is otherwise terminated.
  """
  print('Press Ctrl+C to stop.')
  # gRPC starts a new thread to service requests. Just make the main thread
  # sleep.
  delay = 60*60*24   # One day in seconds
  try:
    while True:
      time.sleep(delay)
  except KeyboardInterrupt:
    pass


def main():
  """Serves gRPC endpoints.
  """
  server = start_server()
  keep_alive()
  stop_server(server)


if __name__ == '__main__':
  main()
