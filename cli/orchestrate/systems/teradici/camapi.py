# python3
# Lint as: python3
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

"""Simple interface to Teradici CAM's REST API v1."""

import json
import logging
import os
import requests


log = logging.getLogger(__name__)


class Namespace:
  """Group of endpoints under a relative path."""
  url = 'https://cam.teradici.com/api/v1'
  headers = dict()

  def __init__(self, **endpoints):
    self.endpoints = endpoints

  def __getattr__(self, name):
    return self.endpoints[name]


class CloudAccessManager(Namespace):
  """Simple interface to Teradici CAM's REST API v1.

  Provides a Pythonic interface to the REST API endpoints. Examples:
    - deployments.get -> GET deployments/
    - deployments.post -> POST deployments/
    - auth.tokens.connector.post -> POST auth/tokens/connector
    - auth.verify.post -> POST auth/tokens/connector
    - machines.entitlements.post -> POST machines/entitlements'
  """

  def __init__(self, api_token=None, project=None, deployment=None,
               credentials_file_name=None):
    """Initializes API with given token or credentials.

    Attempt to connect to the backend in the following order:
    1. Use api_token if provided.
    2. Locate the service account credentials using the project and deployment
       names in the following pattern:
       ~/.config/teradici/{project}-{deployment}.json
    3. Locate the service account credentials from credentials_file_name.

    Note that api_token, project & deployment, and credentials_file_name are
    mutually exclusive. If all are provided, they are attempted in the order
    above and stop when the first connection method succeeds.

    Args:
      api_token: CAM organization level API token.
      project: GCP project name.
      deployment: CAM deployment name.
      credentials_file_name: JSON file containing the credentials of a CAM
        service account.

    Raises:
      RuntimeError: if unable to get a valid API token with any of the given
        parameters.
    """
    super().__init__()

    self.endpoints = dict(
        deployments=Deployments(),
        auth=Namespace(
            signin=AuthSignin(),
            tokens=Namespace(
                connector=AuthTokensConnector()
                )
            ),
        machines=Machines(
            entitlements=MachinesEntitlements(
                adusers=MachinesEntitlementsADUsers(),
                adcomputers=MachinesEntitlementsADComputers(),
                )
            ),
        )

    if not api_token and project and deployment:
      log.debug('Locating CAM service account credentials using project %s'
                ' and deployment %s names', project, deployment)
      file_name = '~/.config/teradici/{project}-{deployment}.json'.format(
          project=project,
          deployment=deployment,
          )
      try:
        api_token = self.auth.signin.post(file_name)
      except FileNotFoundError:
        log.error('Could not locate CAM service account credentials file at %s',
                  file_name)

    if not api_token and credentials_file_name:
      try:
        api_token = self.auth.signin.post(credentials_file_name)
      except FileNotFoundError:
        log.error('Could not locate CAM service account credentials file at %s',
                  credentials_file_name)

    if not api_token:
      message = (
          'Unable to get a valid CAM API token. You may provide an API token,'
          ' project & deployment names, or the file name of a CAM service'
          ' account credentials.'
          )
      raise RuntimeError(message)

    Namespace.headers = dict(
        Authorization=api_token,
        )


class Deployments(Namespace):
  """deployments endpoints."""
  url = '{}/deployments'.format(Namespace.url)

  def get(self, name):
    """Returns a deployment by name."""
    params = dict(
        deploymentName=name,
        showactive='true',
        )
    response = requests.get(self.url, headers=self.headers, params=params)
    response.raise_for_status()
    payload = response.json()
    if payload['total'] > 0:
      deployment = payload['data'][0]
      return deployment
    return None

  def post(self, name, registration_code):
    """Creates a new deployment.

    Args:
      name: Deployment name.
      registration_code: Teradici PCoIP registration code.

    Returns:
      A dictionary with the deployment details.
    """
    payload = dict(
        deploymentName=name,
        registrationCode=registration_code,
        )
    response = requests.post(self.url, data=payload, headers=self.headers)
    response.raise_for_status()
    payload = response.json()
    deployment = payload['data']
    return deployment


class AuthSignin(Namespace):
  """auth/signin endpoints."""
  url = '{}/auth/signin'.format(Namespace.url)

  def post(self, credentials_file_name):
    """Returns a API token for the given service account.

    Args:
      credentials_file_name: JSON file with the credentials of a CAM service
        account.

    Returns:
      An API token.
    """
    file_name = os.path.abspath(os.path.expanduser(credentials_file_name))
    with open(file_name, 'r') as input_file:
      credentials = json.load(input_file)

    payload = dict(
        username=credentials.get('username'),
        password=credentials.get('apiKey'),
        tenantId=credentials.get('tenantId'),
        )
    response = requests.post(self.url, data=payload)
    response.raise_for_status()
    payload = response.json()
    token = payload['data']['token']
    return token


class AuthTokensConnector(Namespace):
  """auth/tokens/connector endpoints."""
  url = '{}/auth/tokens/connector'.format(Namespace.url)

  def post(self, deployment, name):
    """Returns a connector token that can used to deploy CAS.

    Args:
      deployment: Deployment object
      name: Connector name

    Returns:
      A dictionary with the connector token details.
    """
    payload = dict(
        deploymentId=deployment['deploymentId'],
        createdBy=deployment['createdBy'],
        connectorName=name,
        )
    response = requests.post(self.url, data=payload, headers=self.headers)
    response.raise_for_status()
    payload = response.json()
    token = payload['data']['token']
    return token


class Machines(Namespace):
  """machines/ endpoints."""
  url = '{}/machines'.format(Namespace.url)

  def get(self, deployment, **options):
    """Get list of machine for given deployment.

    Args:
      deployment: Deployment object.
      **options: Additional query parameters to filter results.

    Returns:
      A list of dictionaries representing machines.
    """
    params = dict(
        deploymentId=deployment['deploymentId'],
        **options,
        )
    response = requests.get(self.url, params=params, headers=self.headers)
    response.raise_for_status()
    payload = response.json()
    machines = payload.get('data', [])
    return machines


class MachinesEntitlements(Namespace):
  """machines/entitlements/ endpoints."""
  url = '{}/machines/entitlements'.format(Namespace.url)

  def get(self, deployment, **options):
    """Get list of entitlements.

    Args:
      deployment: Deployment object.
      **options: Query arguments.

    Returns:
      A list of dictionary with the entitlements.
    """
    params = dict(
        deploymentId=deployment['deploymentId'],
        **options,
        )
    response = requests.get(self.url, params=params, headers=self.headers)
    response.raise_for_status()
    payload = response.json()
    entitlements = payload.get('data', [])
    return entitlements

  def post(self, machine, user):
    """Create a new entitlement associating a user with a machine.

    Args:
      machine: Machine object
      user: User object

    Returns:
      A dictionary with the entitlement details.
    """
    payload = dict(
        deploymentId=machine['deploymentId'],
        machineId=machine['machineId'],
        userGuid=user['userGuid'],
        )
    response = requests.post(self.url, data=payload, headers=self.headers)
    response.raise_for_status()
    payload = response.json()
    entitlement = payload['data']
    return entitlement

  def delete(self, entitlement):
    """Delete entitlement.

    Args:
      entitlement: Entitlement associating a machine with an AD user.
    """
    url = '{url}/{id}'.format(url=self.url, id=entitlement['entitlementId'])
    response = requests.delete(url, headers=self.headers)
    response.raise_for_status()


class MachinesEntitlementsADUsers(Namespace):
  """machines/entitlements/adusers endpoints."""
  url = '{}/machines/entitlements/adusers'.format(Namespace.url)

  def get(self, deployment, **options):
    """Return list of AD users.

    Args:
      deployment: Deployment object
      **options: Additional query parameters to filter results.

    Returns:
      A list of dictionaries representing AD users.
    """
    params = dict(
        deploymentId=deployment['deploymentId'],
        **options,
        )
    response = requests.get(self.url, params=params, headers=self.headers)
    response.raise_for_status()
    payload = response.json()
    users = payload.get('data', [])
    return users


class MachinesEntitlementsADComputers(Namespace):
  """machines/entitlements/adcomputers endpoints."""
  url = '{}/machines/entitlements/adcomputers'.format(Namespace.url)

  def get(self, deployment, **options):
    """Return list of AD computers.

    Args:
      deployment: Deployment object
      **options: Additional query parameters to filter results.

    Returns:
      A list of dictionaries representing AD computers.
    """
    params = dict(
        deploymentId=deployment['deploymentId'],
        **options,
        )
    response = requests.get(self.url, params=params, headers=self.headers)
    response.raise_for_status()
    payload = response.json()
    computers = payload.get('data', [])
    return computers
