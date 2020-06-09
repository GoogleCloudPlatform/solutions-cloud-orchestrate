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


class Backend:
  """In-memory test data to feed the Python API implementation via requests.
  """

  def __init__(self, token):
    self.token = token
    self.deployments = dict(
        deployment1={
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
            'status': 'active'},
        )

  def deployments_get(self, url, **options):
    """GET deployments/.

    Args:
      url: Endpoint URL
      **options: Arguments to requests.get

    Returns a mock response object to requests.get calls.
    """
    assert url == camapi.Deployments.url
    assert options['headers'] == dict(Authorization=self.token)
    name = options['params']['deploymentName']
    try:
      deployment = self.deployments[name]
      response = mock.MagicMock()
      response.status_code = 200
      response.json.return_value = dict(
          total=1,
          data=[deployment],
          )
      return response
    except KeyError:
      response = mock.MagicMock()
      response.status_code = 200
      response.json.return_value = dict(
          total=0,
          data=[],
          )
      return response

  def deployments_post(self, url, **options):
    """POST deployments/.

    Args:
      url: Endpoint URL
      **options: Arguments to requests.post

    Returns a mock response object to requests.post calls.
    """
    assert url == camapi.Deployments.url
    assert options['headers'] == dict(Authorization=self.token)
    name = options['data']['deploymentName']
    code = options['data']['registrationCode']
    deployment = dict(
        deploymentId='d{}'.format(len(self.deployments)+1),
        deploymentName=name,
        registrationCode=code,
        status='active',
        )
    self.deployments[name] = deployment
    response = mock.MagicMock()
    response.status_code = 201
    response.json.return_value = dict(
        data=deployment,
        )
    return response


def test_deployments():
  """Test deployments endpoints.
  """
  backend = Backend(token='123abc')
  cam = camapi.CloudAccessManager(token=backend.token)

  with mock.patch('requests.get', side_effect=backend.deployments_get):
    deployment = cam.deployments.get('deployment1')
    assert deployment['deploymentId'] == 'd1'
    assert deployment['deploymentName'] == 'deployment1'
    assert deployment['registrationCode'] == '111AAA'
    assert deployment['status'] == 'active'

  with mock.patch('requests.get', side_effect=backend.deployments_get):
    deployment = cam.deployments.get('non-existent-deployment')
    assert not deployment

  with mock.patch('requests.post', side_effect=backend.deployments_post):
    deployment = cam.deployments.post('deployment2', '222BBB')
    assert deployment['deploymentId'] == 'd2'
    assert deployment['deploymentName'] == 'deployment2'
    assert deployment['registrationCode'] == '222BBB'
    assert deployment['status'] == 'active'

  with mock.patch('requests.get', side_effect=backend.deployments_get):
    deployment = cam.deployments.get('deployment2')
    assert deployment['deploymentId'] == 'd2'
    assert deployment['deploymentName'] == 'deployment2'
    assert deployment['registrationCode'] == '222BBB'
    assert deployment['status'] == 'active'
