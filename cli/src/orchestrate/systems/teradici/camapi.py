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

import enum
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


class Scope(enum.Enum):
  """Scope of endpoints that can be accessed by a given token.
  """
  NONE = 1
  ALL = 2           # Get API token
  CAM = 3           # CAM Service Account
  DEPLOYMENT = 4    # Deployment Service Acount


class CloudAccessManager(Namespace):
  """Simple interface to Teradici CAM's REST API v1.

  Provides a Pythonic interface to the REST API endpoints. Examples:
    - deployments.get -> GET deployments/
    - deployments.post -> POST deployments/
    - auth.tokens.connector.post -> POST auth/tokens/connector
    - auth.verify.post -> POST auth/tokens/connector
    - machines.entitlements.post -> POST machines/entitlements'
  """

  def __init__(self, token=None, project=None, scope=Scope.NONE,
               credentials_file_name=None):
    """Initializes API with given token or credentials.

    Attempt to connect to the backend in the following order:
    1. Use token if provided.
    2. Locate the service account credentials using the project name and scope
       in the following pattern:
       ~/.config/teradici/{project}-{scope}.json
    3. Locate the service account credentials from credentials_file_name.

    Note that token, project & scope, and credentials_file_name are
    mutually exclusive. If all are provided, they are attempted in the order
    above and stop when the first connection method succeeds.

    Args:
      token: CAM organization level API token.
      project: GCP project name.
      scope: Intended use, i.e. "cam", "deployment". This allows for credentials
        of different types of CAM service accounts. Currently, a "CAM-level"
        service account can be used to `deploy` the teradici system, whereas the
        "CAM deployment-level" account can be used to execute `broker` commands.
      credentials_file_name: JSON file containing the credentials of a CAM
        service account.

    Raises:
      RuntimeError: if unable to get a valid API token with any of the given
        parameters.
    """
    super().__init__()

    self.endpoints = dict(
        deployments=Deployments(
              cloudServiceAccounts=CloudServiceAccounts(),
            ),
        auth=Namespace(
            signin=AuthSignin(),
            keys=AuthKeys(),
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

    if token:
      self.scope = Scope.ALL

    if not token and project and scope:
      scope_name = scope.name.lower()
      log.debug('Locating CAM service account credentials using project %s'
                ' and scope %s', project, scope_name)
      file_name = '~/.config/teradici/{project}-{scope}.json'.format(
          project=project,
          scope=scope_name,
          )
      try:
        token, self.scope = self.auth.signin.post(file_name)
      except FileNotFoundError:
        log.error('Could not locate CAM service account credentials file at %s',
                  file_name)

    if not token and credentials_file_name:
      try:
        token, self.scope = self.auth.signin.post(credentials_file_name)
      except FileNotFoundError:
        log.error('Could not locate CAM service account credentials file at %s',
                  credentials_file_name)

    if not token:
      message = (
          'Unable to get a valid CAM API token. You may provide an API token,'
          ' project & deployment names, or the file name of a CAM service'
          ' account credentials.'
          )
      raise RuntimeError(message)

    Namespace.headers = dict(
        Authorization=token,
        )


class RequestIterator:
  """Returns a page of results from request supporting offset and limit.
  """

  def __init__(self, endpoint, *arguments, **options):
    """Initializes iterator to fetch results in batches.

    Caller to provide `offset` and `limit` in `**options`. If not provided,
    defaults are used.

    Args:
      endpoint: Bound method to a camapi.CloudAccessManager method.
      *arguments: Positional arguments for endpoint.
      **options: Keyword arguments for endpoint.
    """
    self.endpoint = endpoint
    self.arguments = arguments
    self.options = dict(options)

  def __iter__(self):
    offset = self.options.get('offset', 0)
    limit = self.options.get('limit', 10)
    while True:
      self.options['offset'] = offset
      self.options['limit'] = limit
      results = self.endpoint(*self.arguments, **self.options)
      if results:
        for result in results:
          yield result
        offset += limit
        if len(results) < limit:
          # This was the last page, no point in sending another request just
          # to get an empty list.
          break
      else:
        # Last page was full but there are no more results left to fetch.
        break


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


class CloudServiceAccounts(Namespace):
  """deployments/{deploymentId}/cloudServiceAccounts endpoints."""
  url = '{}/deployments/{{deployment_id}}/cloudServiceAccounts'.format(
      Namespace.url)

  def post(self, deployment, credentials_file_name):
    """Registers a GCP service account in CAM.

    Args:
      deployment: CAM Deployment object.
      credentials_file_name: JSON file containing the private key of a GCP
        service account.

    Returns:
      A dictionary with minimal information about the service account registered
      in CAM.
    """
    with open(credentials_file_name, 'r') as input_file:
      credentials = json.load(input_file)

    url = self.url.format(deployment_id=deployment['deploymentId'])
    payload = dict(
        provider='gcp',
        credential=dict(
            clientEmail=credentials['client_email'],
            privateKey=credentials['private_key'],
            projectId=credentials['project_id'],
        ))

    response = requests.post(url, json=payload, headers=self.headers)
    response.raise_for_status()
    payload = response.json()
    service_account = payload['data']
    return service_account


class AuthSignin(Namespace):
  """auth/signin endpoints."""
  url = '{}/auth/signin'.format(Namespace.url)

  def post(self, credentials_file_name):
    """Connect with the given credentials to obtain an API token.

    If the 'deploymentId' key is in the credentials read from disk it sets the
    scope to Scope.DEPLOYMENT. Otherwise, assume that it is a Scope.CAM account.

    Args:
      credentials_file_name: JSON file with the credentials of a CAM service
        account.

    Returns:
      An API token and the detected scope.
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
    scope = Scope.DEPLOYMENT if 'deploymentId' in credentials else Scope.CAM
    return token, scope


class AuthKeys(Namespace):
  """auth/keys endpoints."""
  url = '{}/auth/keys'.format(Namespace.url)

  def post(self, deployment):
    """Create a deployment-level service account key.

    Args:
      deployment: CAM deployment object.

    Returns:
      A dictionary with the credentials. IMPORTANT, these keys should be saved
      if meant to be persistent. This is the only time they are generated.
    """
    payload = dict(
        deploymentId=deployment['deploymentId'],
        )
    response = requests.post(self.url, data=payload, headers=self.headers)
    response.raise_for_status()
    payload = response.json()
    credentials = payload['data']
    return credentials


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

  def post(self, deployment, name, project, zone):
    """Creates a machine that can be assigned to users.

    Args:
      deployment: CAM deployment object.
      name: Machine name.
      project: GCP project name.
      zone: GCP zone.

    Returns:
      A dictionary with the CAM machine details.
    """
    payload = dict(
        provider='gcp',
        machineName=name,
        deploymentId=deployment['deploymentId'],
        projectId=project,
        zone=zone,
        active=True,
        managed=True,
    )

    response = requests.post(
        self.url,
        headers=self.headers,
        data=payload,
    )
    response.raise_for_status()

    payload = response.json()
    machine = payload['data']
    return machine


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
