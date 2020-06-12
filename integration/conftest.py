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

"""Test fixtures."""

import logging
import os
import uuid

import orchestrateapi.main

import pytest


log = logging.getLogger(__name__)


@pytest.fixture()
def tag():
  return 'oit{}'.format(uuid.uuid4().hex[:5])


@pytest.yield_fixture(scope='module', autouse=True)
def local_server():
  """Local Orchestrate API server.

  Initializes a local instance of gRPC servicer serving the Orchestarte API.

  Yields:
    None.
  """
  log.info('Starting local server')
  log.info('ORCHESTRATE_PROJECT : %s', os.environ['ORCHESTRATE_PROJECT'])
  log.info('ORCHESTRATE_API_HOST: %s', os.environ['ORCHESTRATE_API_HOST'])
  server = orchestrateapi.main.start_server()
  yield
  log.info('Stopping local server')
  orchestrateapi.main.stop_server(server)
