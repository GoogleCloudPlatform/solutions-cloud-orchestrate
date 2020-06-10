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

"""Test the CAM API."""

import contextlib
import json
import os
from unittest import mock

from orchestrate.systems.teradici import camapi

import pytest


def test_connection_without_any_creddentials():
  """Verify client cannot connect without explicitly providing credentials.
  """
  with pytest.raises(RuntimeError):
    camapi.CloudAccessManager()


def test_connection_with_token():
  """Verify client can connect with an API token.
  """
  cam = camapi.CloudAccessManager(token='abc123')
  assert cam.scope == camapi.Scope.ALL
  assert cam.headers == dict(Authorization='abc123')


def test_connection_with_cam_service_account():
  """Verify client can connect with CAM-level service account.
  """
  with mock.patch('orchestrate.systems.teradici.camapi.open') as mock_open:
    # Provide in-memory credentials
    credentials = dict(
        keyId='cam_keyId',
        username='cam_username',
        apiKey='cam_apiKey',
        keyName='cam_keyName',
        )
    mock_open_read = mock.MagicMock()
    mock_open_read.return_value = json.dumps(credentials)
    mock_open.return_value.__enter__.return_value.read = mock_open_read

    with mock.patch('requests.post') as requests_post:
      # Return mock authentication token based on credentials
      payload = dict(
          data=dict(
              token='cam_token',
              )
          )
      requests_post.return_value.json.return_value = payload

      # Connect
      cam = camapi.CloudAccessManager(project='test_connection',
                                      scope=camapi.Scope.CAM)

      # Verify it "loaded" file from the right location
      path = os.path.abspath(os.path.expanduser(
          '~/.config/teradici/test_connection-cam.json'))
      mock_open.assert_called_once_with(path, 'r')

      # Verify it requested a token from the backend
      requests_post.assert_called_once()
      assert requests_post.call_args[0] == (camapi.AuthSignin.url,)

      # Verify we got a token for the requested scope
      assert cam.scope == camapi.Scope.CAM
      assert cam.headers == dict(Authorization='cam_token')


def test_connection_with_deployment_service_account():
  """Verify client can connect with CAM Deployment-level service account.
  """
  with mock.patch('orchestrate.systems.teradici.camapi.open') as mock_open:
    # Provide in-memory credentials
    credentials = dict(
        keyId='deployment_keyId',
        username='deployment_username',
        apiKey='deployment_apiKey',
        keyName='deployment_keyName',
        deploymentId='deployment_deploymentId',
        tenantId='deployment_tenantId',
        )
    mock_open_read = mock.MagicMock()
    mock_open_read.return_value = json.dumps(credentials)
    mock_open.return_value.__enter__.return_value.read = mock_open_read

    with mock.patch('requests.post') as requests_post:
      # Return mock authentication token based on credentials
      payload = dict(
          data=dict(
              token='deployment_token',
              )
          )
      requests_post.return_value.json.return_value = payload

      # Connect
      cam = camapi.CloudAccessManager(project='test_connection',
                                      scope=camapi.Scope.DEPLOYMENT)

      # Verify it "loaded" file from the right location
      path = os.path.abspath(os.path.expanduser(
          '~/.config/teradici/test_connection-deployment.json'))
      mock_open.assert_called_once_with(path, 'r')

      # Verify it requested a token from the backend
      requests_post.assert_called_once()
      assert requests_post.call_args[0] == (camapi.AuthSignin.url,)

      # Verify we got a token for the requested scope
      assert cam.scope == camapi.Scope.DEPLOYMENT
      assert cam.headers == dict(Authorization='deployment_token')


def test_connection_with_scope_autodetect():
  """Verify client can gracefully connect and adapt to scope discrepancies.

  Dynamically changes the scope if the provided credentials have a different
  scope, e.g. requested CAM-level but the credentials in fact belong to a
  Deployment-level account.
  """
  with mock.patch('orchestrate.systems.teradici.camapi.open') as mock_open:
    # Provide in-memory credentials for a Deployment-level account
    credentials = dict(
        keyId='deployment_keyId',
        username='deployment_username',
        apiKey='deployment_apiKey',
        keyName='deployment_keyName',
        deploymentId='deployment_deploymentId',
        tenantId='deployment_tenantId',
        )
    mock_open_read = mock.MagicMock()
    mock_open_read.return_value = json.dumps(credentials)
    mock_open.return_value.__enter__.return_value.read = mock_open_read

    with mock.patch('requests.post') as requests_post:
      # Return mock authentication token based on credentials
      payload = dict(
          data=dict(
              token='deployment_token',
              )
          )
      requests_post.return_value.json.return_value = payload

      # Connect
      # IMPORTANT difference here: We are requesting a CAM-level connection,
      # but the actual credentials stored in the file are for a Deployment-level
      # account. It will connect but update the scope to DEPLOYMENT instead of
      # CAM.
      cam = camapi.CloudAccessManager(project='test_connection',
                                      scope=camapi.Scope.CAM)

      # Verify it "loaded" file from the right location
      path = os.path.abspath(os.path.expanduser(
          '~/.config/teradici/test_connection-cam.json'))
      mock_open.assert_called_once_with(path, 'r')

      # Verify it requested a token from the backend
      requests_post.assert_called_once()
      assert requests_post.call_args[0] == (camapi.AuthSignin.url,)

      # Verify we got a token that matches the actual credentials from disk
      # which in this test are different on purpose.
      assert cam.scope == camapi.Scope.DEPLOYMENT
      assert cam.headers == dict(Authorization='deployment_token')


class LocalBackend:
  """In-memory test data to feed the Python API implementation via requests.
  """
  GET = 'GET'
  POST = 'POST'

  class Expectation:
    """Parameters of an expected API call to the backend.
    """

    def __init__(self, method, url, params=None, data=None, result=None):
      """Parameters of an expected API call to the backend.

      Args:
        method: GET, POST, etc.
        url: Endpoint URL.
        params: (optional) Dictionary with query parameters.
        data: (optional) Dictionary with data payload.
        result: (optional) Body returned in the response. If not a callable,
          it uses the value directly to return it in the response.json() method.
          Otherwise, it will execute the callable with the request parameters
          so that it can construct a custom response body.
      """
      self.method = method
      self.url = url
      self.params = params
      self.data = data
      self.result = result

    def __repr__(self):
      text = (
          'Expecation(method={method}, url={url}, params={params}, data={data},'
          'result={result}'
          ).format(**vars(self))
      return text

  class UnexpectedRequestError(Exception):
    """A request was attempted but the unit tests were not expecting it.
    """

    def __init__(self, message, method, url, options):
      """Store details about what was expected and what was received.

      Args:
        message: Detail message about the error.
        method: GET, POST, etc.
        url: Attempted endpoint.
        options: Parmeters for the endpoint request.
      """
      super().__init__(message)
      self.method = method
      self.url = url
      self.options = options

  def __init__(self, token):
    """Sample data to return to expected backend calls.

    Request methods are mocked so that it can return predicatble data.

    Args:
      token: Test API token.
    """
    self.token = token
    self.expectations = []
    self.deployments = [
        {
            'deploymentId': 'd1',
            'resourceGroup': 'rg1',
            'subscriptionId': 's1',
            'createdBy': 'u1',
            'createdOn': '2020-06-06T00:11:22.333Z',
            'updatedOn': '2020-06-06T00:11:22.333Z',
            'active': True,
            'scannedOn': None,
            'registrationCode': '111AAA',
            'deploymentURI': '',
            'deploymentName': 'deployment1',
            'status': 'active',
        },
    ]
    self.computers = [
        {
            'deploymentId': 'd1',
            'createdBy': 'u1',
            'operatingSystem': 'Windows Server 2019 Datacenter',
            'computerName': 'COMPUTER1',
            'computerHostname': 'win1.cloud.demo',
            'operatingSystemVersion': '10.0 (17763)',
            'createdOn': '2020-06-06T00:11:22.333Z',
        },
        {
            'deploymentId': 'd1',
            'createdBy': 'u1',
            'operatingSystem': 'Windows Server 2019 Datacenter',
            'computerName': 'COMPUTER2',
            'computerHostname': 'win1.cloud.demo',
            'operatingSystemVersion': '10.0 (17763)',
            'createdOn': '2020-06-06T00:11:22.333Z',
        },
    ]
    self.users = [
        {
            'usnChanged': '',
            'groups': [],
            'name': 'User One',
            'enabled': True,
            '_id': 'u1',
            'userGuid': 'guid1',
            'deploymentId': 'd1',
            'userName': 'user1',
            'createdBy': 'u0',
            'createdOn': '2020-06-06T00:22:33.444Z',
        },
        {
            'usnChanged': '',
            'groups': [],
            'name': 'User Two',
            'enabled': True,
            '_id': 'u2',
            'userGuid': 'guid2',
            'deploymentId': 'd1',
            'userName': 'user2',
            'createdBy': 'u0',
            'createdOn': '2020-06-06T00:22:33.444Z',
        },
    ]
    self.entitlements = [
        {
            'entitlementId': 'e1',
            'deploymentId': 'd1',
            'createdBy': 'u0',
            'createdOn': '2020-06-06T05:31:49.268Z',
            'updatedOn': '2020-06-06T05:31:49.268Z',
            'userGuid': 'guid1',
            'status': 'active',
            'machineId': 'm1',
            'machine': {
                'machineId': 'm1',
                'provider': 'gcp',
                'subscriptionId': 'd1',
                'machineName': 'computer1',
                'hostName': 'computer1',
                'deploymentId': 'd1',
                'connectorId': '',
                'resourceGroup': 'us-west2-b',
                'powerState': 'unknown',
                'createdBy': 'u0',
                'createdOn': '2020-06-06T05:31:34.672Z',
                'updatedOn': '2020-06-06T05:31:34.673Z',
                'active': True,
                'location': 'unknown',
                'vmSize': 'unknown',
                'osInfo': {
                    'publisher': 'unknown',
                    'offer': 'unknown',
                    'sku': 'unknown',
                    'version': 'unknown',
                },
                'provisioningStatus': {
                    'state': 'succeeded',
                    'message': '',
                    'deployment': {},
                    'attributes': {},
                },
                'status': 'active',
                'projectId': 'test',
                'zone': 'us-west2-b',
                'powerStateLastChangedOn': '2020-06-06T05:31:34.673Z',
                'managed': True,
            },
        },
        {
            'entitlementId': 'e2',
            'deploymentId': 'd1',
            'createdBy': 'u0',
            'createdOn': '2020-06-06T05:31:49.268Z',
            'updatedOn': '2020-06-06T05:31:49.268Z',
            'userGuid': 'guid2',
            'status': 'active',
            'machineId': 'm2',
            'machine': {
                'machineId': 'm2',
                'provider': 'gcp',
                'subscriptionId': 'd1',
                'machineName': 'computer2',
                'hostName': 'computer2',
                'deploymentId': 'd1',
                'connectorId': '',
                'resourceGroup': 'us-west2-b',
                'powerState': 'unknown',
                'createdBy': 'u0',
                'createdOn': '2020-06-06T05:31:34.672Z',
                'updatedOn': '2020-06-06T05:31:34.673Z',
                'active': True,
                'location': 'unknown',
                'vmSize': 'unknown',
                'osInfo': {
                    'publisher': 'unknown',
                    'offer': 'unknown',
                    'sku': 'unknown',
                    'version': 'unknown',
                },
                'provisioningStatus': {
                    'state': 'succeeded',
                    'message': '',
                    'deployment': {},
                    'attributes': {},
                },
                'status': 'active',
                'projectId': 'test',
                'zone': 'us-west2-b',
                'powerStateLastChangedOn': '2020-06-06T05:31:34.673Z',
                'managed': True,
            },
        },
    ]
    self.machines = [
        {
            'machineId': 'm1',
            'provider': 'gcp',
            'subscriptionId': 'd1',
            'machineName': 'computer1',
            'hostName': 'computer1',
            'deploymentId': 'd1',
            'connectorId': '',
            'resourceGroup': 'us-west2-b',
            'powerState': 'unknown',
            'createdBy': 'u0',
            'createdOn': '2020-06-06T05:31:34.672Z',
            'updatedOn': '2020-06-06T05:31:34.673Z',
            'active': True,
            'location': 'unknown',
            'vmSize': 'unknown',
            'osInfo': {
                'publisher': 'unknown',
                'offer': 'unknown',
                'sku': 'unknown',
                'version': 'unknown',
            },
            'provisioningStatus': {
                'state': 'succeeded',
                'message': '',
                'deployment': {},
                'attributes': {},
            },
            'status': 'active',
            'projectId': 'test',
            'zone': 'us-west2-b',
            'powerStateLastChangedOn': '2020-06-06T05:31:34.673Z',
            'managed': True,
        },
    ]

  def expect(self, method, url, params=None, data=None, result=None):
    expectation = LocalBackend.Expectation(method, url, params, data, result)
    self.expectations.append(expectation)

  def get(self, url, **options):
    """Mock requests.get.

    Args:
      url: Endpoint URL.
      **options: Request parameters.

    Returns:
      A mock response to emulate the ones returned by requests.get.

    Raises:
      UnexpectedRequestError if the request was not previously expected by
        calling expect().
    """
    for expectation in self.expectations:
      if expectation.method == LocalBackend.GET and \
          expectation.url == url and \
          expectation.params == options.get('params') and \
          expectation.data == options.get('data'):
        return self.make_response(200, expectation.result)
    self.unexpected_request(self.GET, url, options)

  def post(self, url, **options):
    """Mock requests.post.

    Args:
      url: Endpoint URL.
      **options: Request parameters.

    Returns:
      A mock response to emulate the ones returned by requests.post.

    Raises:
      UnexpectedRequestError if the request was not previously expected by
        calling expect().
    """
    for expectation in self.expectations:
      data = list(options.get('data', dict()).keys())
      if expectation.method == LocalBackend.POST and \
          expectation.url == url and \
          expectation.params == options.get('params') and \
          sorted(expectation.data) == sorted(data) and \
          callable(expectation.result):
        payload = expectation.result(expectation, options)
        return self.make_response(200, payload)
    self.unexpected_request(self.POST, url, options)

  def unexpected_request(self, method, url, options):
    """Raises an exception with useful message and data.

    Args:
      method: GET, POST, etc.
      url: Endpoint URL.
      options: Request parameters.

    Raises:
      UnexpectedRequestError: The request was not previously expected by
        calling expect().
    """
    message = (
        'Unexpected {} {} request during tests. Perhaps adding an Expectation'
        ' via LocalBackend.expect() would help? Or, review the tests for typos'
        ' or missing parameters.'
        ).format(method, url)
    raise self.UnexpectedRequestError(message, method, url, options)

  def make_response(self, status_code, payload):
    response = mock.MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    return response

  def deployments_post(self, expectation, options):
    deployment = dict(
        deploymentId='d{}'.format(len(self.deployments)+1),
        status='active',
        )
    for key in expectation.data:
      deployment[key] = options['data'][key]
    self.deployments.append(deployment)
    return dict(data=deployment)

  def machines_post(self, expectation, options):
    machine = dict(
        machineId='m{}'.format(len(self.machines)+1),
        )
    for key in expectation.data:
      machine[key] = options['data'][key]
    self.machines.append(machine)
    return dict(data=machine)

  def entitlements_post(self, expectation, options):
    entitlement = dict(
        entitlementId='e{}'.format(len(self.entitlements)+1),
        )
    for key in expectation.data:
      entitlement[key] = options['data'][key]
    self.entitlements.append(entitlement)
    return dict(data=entitlement)

  @contextlib.contextmanager
  def activate(self):
    with mock.patch('requests.get', side_effect=self.get):
      with mock.patch('requests.post', side_effect=self.post):
        yield self


@pytest.fixture
def local_backend():
  return LocalBackend(token='123abc')


def test_deployments(local_backend):
  """Test deployments endpoints.

  Args:
    local_backend: Backend that intercepts requests and returns predictable
      test data.
  """
  with local_backend.activate() as backend:
    backend.expect(
        LocalBackend.GET, camapi.Deployments.url,
        params=dict(deploymentName='deployment1', showactive='true'),
        result=dict(total=1, data=[backend.deployments[0]]))
    backend.expect(
        LocalBackend.GET, camapi.Deployments.url,
        params=dict(deploymentName='non-existent-deployment',
                    showactive='true'),
        result=dict(total=0, data=[]))
    backend.expect(
        LocalBackend.POST, camapi.Deployments.url,
        data=['deploymentName', 'registrationCode'],
        result=backend.deployments_post)

    cam = camapi.CloudAccessManager(token=backend.token)
    deployment = cam.deployments.get('deployment1')
    assert deployment['deploymentId'] == 'd1'
    assert deployment['deploymentName'] == 'deployment1'
    assert deployment['registrationCode'] == '111AAA'
    assert deployment['status'] == 'active'

    deployment = cam.deployments.get('non-existent-deployment')
    assert not deployment

    deployment = cam.deployments.post('deployment2', '222BBB')
    assert deployment['deploymentId'] == 'd2'
    assert deployment['deploymentName'] == 'deployment2'
    assert deployment['registrationCode'] == '222BBB'
    assert deployment['status'] == 'active'

    backend.expect(
        LocalBackend.GET, camapi.Deployments.url,
        params=dict(deploymentName='deployment2', showactive='true'),
        result=dict(total=1, data=[backend.deployments[1]]))

    deployment = cam.deployments.get('deployment2')
    assert deployment['deploymentId'] == 'd2'
    assert deployment['deploymentName'] == 'deployment2'
    assert deployment['registrationCode'] == '222BBB'
    assert deployment['status'] == 'active'


def test_computers(local_backend):
  """Test computers endpoints.

  Args:
    local_backend: Backend that intercepts requests and returns predictable
      test data.
  """
  with local_backend.activate() as backend:
    backend.expect(
        LocalBackend.GET, camapi.Deployments.url,
        params=dict(deploymentName='deployment1', showactive='true'),
        result=dict(total=1, data=[backend.deployments[0]]))
    backend.expect(
        LocalBackend.GET, camapi.MachinesEntitlementsADComputers.url,
        params=dict(deploymentId='d1', computerName='computer1'),
        result=dict(total=1, data=[backend.computers[0]]))
    backend.expect(
        LocalBackend.GET, camapi.MachinesEntitlementsADComputers.url,
        params=dict(deploymentId='d1', computerName='non-existent-computer'),
        result=dict(total=0, data=[]))
    backend.expect(
        LocalBackend.GET, camapi.MachinesEntitlementsADComputers.url,
        params=dict(deploymentId='d1'),
        result=dict(total=2, data=backend.computers))

    cam = camapi.CloudAccessManager(token=backend.token)
    deployment = cam.deployments.get('deployment1')

    computers = cam.machines.entitlements.adcomputers.get(
        deployment, computerName='computer1')
    assert len(computers) == 1
    assert computers[0]['deploymentId'] == 'd1'
    assert computers[0]['computerName'] == 'COMPUTER1'

    computers = cam.machines.entitlements.adcomputers.get(
        deployment, computerName='non-existent-computer')
    assert not computers

    computers = cam.machines.entitlements.adcomputers.get(deployment)
    assert len(computers) == 2
    assert computers[0]['deploymentId'] == 'd1'
    assert computers[0]['computerName'] == 'COMPUTER1'
    assert computers[1]['deploymentId'] == 'd1'
    assert computers[1]['computerName'] == 'COMPUTER2'


def test_users(local_backend):
  """Test user endpoints.

  Args:
    local_backend: Backend that intercepts requests and returns predictable
      test data.
  """
  with local_backend.activate() as backend:
    backend.expect(
        LocalBackend.GET, camapi.Deployments.url,
        params=dict(deploymentName='deployment1', showactive='true'),
        result=dict(total=1, data=[backend.deployments[0]]))
    backend.expect(
        LocalBackend.GET, camapi.MachinesEntitlementsADUsers.url,
        params=dict(deploymentId='d1', userName='User One'),
        result=dict(total=1, data=[backend.users[0]]))
    backend.expect(
        LocalBackend.GET, camapi.MachinesEntitlementsADUsers.url,
        params=dict(deploymentId='d1', userName='non-existent-user'),
        result=dict(total=0, data=[]))
    backend.expect(
        LocalBackend.GET, camapi.MachinesEntitlementsADUsers.url,
        params=dict(deploymentId='d1'),
        result=dict(total=2, data=backend.users))

    cam = camapi.CloudAccessManager(token=backend.token)
    deployment = cam.deployments.get('deployment1')

    users = cam.machines.entitlements.adusers.get(
        deployment, userName='User One')
    assert len(users) == 1
    assert users[0]['deploymentId'] == 'd1'
    assert users[0]['userGuid'] == 'guid1'
    assert users[0]['name'] == 'User One'
    assert users[0]['userName'] == 'user1'

    users = cam.machines.entitlements.adusers.get(
        deployment, userName='non-existent-user')
    assert not users

    users = cam.machines.entitlements.adusers.get(deployment)
    assert len(users) == 2
    assert users[0]['deploymentId'] == 'd1'
    assert users[0]['userGuid'] == 'guid1'
    assert users[0]['name'] == 'User One'
    assert users[0]['userName'] == 'user1'
    assert users[1]['deploymentId'] == 'd1'
    assert users[1]['userGuid'] == 'guid2'
    assert users[1]['name'] == 'User Two'
    assert users[1]['userName'] == 'user2'


def test_machines(local_backend):
  """Test machines endpoints.

  Args:
    local_backend: Backend that intercepts requests and returns predictable
      test data.
  """
  with local_backend.activate() as backend:
    backend.expect(
        LocalBackend.GET, camapi.Deployments.url,
        params=dict(deploymentName='deployment1', showactive='true'),
        result=dict(total=1, data=[backend.deployments[0]]))
    backend.expect(
        LocalBackend.GET, camapi.Machines.url,
        params=dict(deploymentId='d1', machineName='computer1'),
        result=dict(total=1, data=[backend.machines[0]]))
    backend.expect(
        LocalBackend.GET, camapi.Machines.url,
        params=dict(deploymentId='d1', machineName='non-existent-computer'),
        result=dict(total=0, data=[]))
    backend.expect(
        LocalBackend.POST, camapi.Machines.url,
        data=[
            'provider',
            'machineName',
            'deploymentId',
            'projectId',
            'zone',
            'active',
            'managed',
        ],
        result=backend.machines_post)
    backend.expect(
        LocalBackend.GET, camapi.Machines.url,
        params=dict(deploymentId='d1'),
        result=dict(total=2, data=backend.machines))

    cam = camapi.CloudAccessManager(token=backend.token)
    deployment = cam.deployments.get('deployment1')

    machines = cam.machines.get(deployment, machineName='computer1')
    assert len(machines) == 1
    assert machines[0]['deploymentId'] == 'd1'
    assert machines[0]['machineId'] == 'm1'
    assert machines[0]['machineName'] == 'computer1'
    assert machines[0]['projectId'] == 'test'
    assert machines[0]['zone'] == 'us-west2-b'
    assert machines[0]['active']
    assert machines[0]['managed']

    machines = cam.machines.get(
        deployment, machineName='non-existent-computer')
    assert not machines

    machine = cam.machines.post(
        deployment, 'computer2', 'test_project', 'test_zone')
    assert machine['deploymentId'] == 'd1'
    assert machine['machineId'] == 'm2'
    assert machine['machineName'] == 'computer2'
    assert machine['projectId'] == 'test_project'
    assert machine['zone'] == 'test_zone'

    machines = cam.machines.get(deployment)
    assert len(machines) == 2
    assert machines[0]['deploymentId'] == 'd1'
    assert machines[0]['machineId'] == 'm1'
    assert machines[0]['machineName'] == 'computer1'
    assert machines[0]['projectId'] == 'test'
    assert machines[0]['zone'] == 'us-west2-b'
    assert machines[1]['deploymentId'] == 'd1'
    assert machines[1]['machineId'] == 'm2'
    assert machines[1]['machineName'] == 'computer2'
    assert machines[1]['projectId'] == 'test_project'
    assert machines[1]['zone'] == 'test_zone'


def test_entitlements(local_backend):
  """Test entitlement endpoints.

  Args:
    local_backend: Backend that intercepts requests and returns predictable
      test data.
  """
  with local_backend.activate() as backend:
    backend.expect(
        LocalBackend.GET, camapi.Deployments.url,
        params=dict(deploymentName='deployment1', showactive='true'),
        result=dict(total=1, data=[backend.deployments[0]]))
    backend.expect(
        LocalBackend.GET, camapi.MachinesEntitlements.url,
        params=dict(deploymentId='d1', machineName='computer1'),
        result=dict(total=1, data=[backend.entitlements[0]]))
    backend.expect(
        LocalBackend.GET, camapi.MachinesEntitlements.url,
        params=dict(deploymentId='d1', machineName='non-existent-computer'),
        result=dict(total=0, data=[]))
    backend.expect(
        LocalBackend.GET, camapi.MachinesEntitlements.url,
        params=dict(deploymentId='d1'),
        result=dict(total=2, data=backend.entitlements))

    cam = camapi.CloudAccessManager(token=backend.token)
    deployment = cam.deployments.get('deployment1')

    entitlements = cam.machines.entitlements.get(
        deployment, machineName='computer1')
    assert len(entitlements) == 1
    assert entitlements[0]['entitlementId'] == 'e1'
    assert entitlements[0]['deploymentId'] == 'd1'
    assert entitlements[0]['machineId'] == 'm1'
    assert entitlements[0]['userGuid'] == 'guid1'
    assert entitlements[0]['machine']['machineId'] == 'm1'
    assert entitlements[0]['machine']['machineName'] == 'computer1'

    entitlements = cam.machines.entitlements.get(
        deployment, machineName='non-existent-computer')
    assert not entitlements

    entitlements = cam.machines.entitlements.get(deployment)
    assert len(entitlements) == 2
    assert entitlements[0]['entitlementId'] == 'e1'
    assert entitlements[0]['deploymentId'] == 'd1'
    assert entitlements[0]['machineId'] == 'm1'
    assert entitlements[0]['userGuid'] == 'guid1'
    assert entitlements[0]['machine']['machineId'] == 'm1'
    assert entitlements[0]['machine']['machineName'] == 'computer1'
    assert entitlements[1]['entitlementId'] == 'e2'
    assert entitlements[1]['deploymentId'] == 'd1'
    assert entitlements[1]['machineId'] == 'm2'
    assert entitlements[1]['userGuid'] == 'guid2'
    assert entitlements[1]['machine']['machineId'] == 'm2'
    assert entitlements[1]['machine']['machineName'] == 'computer2'

    backend.expect(
        LocalBackend.POST, camapi.MachinesEntitlements.url,
        data=['deploymentId', 'machineId', 'userGuid'],
        result=backend.entitlements_post)
    backend.expect(
        LocalBackend.POST, camapi.Machines.url,
        data=[
            'provider',
            'machineName',
            'deploymentId',
            'projectId',
            'zone',
            'active',
            'managed',
        ],
        result=backend.machines_post)
    backend.expect(
        LocalBackend.GET, camapi.MachinesEntitlementsADUsers.url,
        params=dict(deploymentId='d1', userName='User One'),
        result=dict(total=1, data=[backend.users[0]]))

    machine = cam.machines.post(
        deployment, 'computer2', 'test_project', 'test_zone')
    users = cam.machines.entitlements.adusers.get(
        deployment, userName='User One')
    entitlement = cam.machines.entitlements.post(machine, users[0])
    assert entitlement['entitlementId'] == 'e3'
    assert entitlement['deploymentId'] == 'd1'
    assert entitlement['machineId'] == 'm2'
    assert entitlement['userGuid'] == 'guid1'

    entitlements = cam.machines.entitlements.get(deployment)
    assert len(entitlements) == 3
    assert entitlements[2]['entitlementId'] == 'e3'
    assert entitlements[2]['deploymentId'] == 'd1'
    assert entitlements[2]['machineId'] == 'm2'
    assert entitlements[2]['userGuid'] == 'guid1'
