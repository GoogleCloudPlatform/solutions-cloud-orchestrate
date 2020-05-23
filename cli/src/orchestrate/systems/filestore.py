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

"""Deploy Filestore instance.
"""

import logging
from orchestrate import base


log = logging.getLogger(__name__)


class Filestore(base.OrchestrateSystem):
  """Deploy Filestore instance."""

  def __init__(self):
    super(Filestore, self).__init__()
    # Storage
    self.tier = 'standard'   # 'standard', 'premium'
    self.instance_name = None
    self.volumes = 'projects:/projects'
    self.terabytes = 1

    # Network
    self.network = 'filestore'
    # The IP to mount will be the second IP available in the CIDR
    # For instance, for 172.16.0.0/29 the IP will be 172.16.0.2
    self.cidr = '172.16.0.0/29'
    self.ip = '172.16.0.2'

  @property
  def description(self):
    return """Deploys an Filestore instance."""

  def run(self):
    """Executes system deployment.

    Returns:
      True if successful. False, otherwise.
    """
    log.info('Deploying Filestore')

    self.enable_apis()
    self.create_vpc()
    self.create_filestore_instance()

  def configure(self):
    """Configure."""
    self.region = '-'.join(self.zone.split('-')[:-1])

    if self.prefix:
      self.prefix += '-'

    self.volume_name = self.volumes.split(':')[0]

    if not self.instance_name:
      self.instance_name = '{}{}-{}'.format(self.prefix, self.network,
                                            self.volume_name)
    self.network = self.prefix + self.network

  def enable_apis(self):
    """Enable APIs."""
    log.info('Enabling APIs')
    command = (
        'gcloud services enable'
        ' file.googleapis.com'
        )
    self.run_command(command)

  def create_vpc(self):
    """Create VPC networks."""
    log.info('Creating VPC networks')
    command = (
        'gcloud compute networks create {self.network}'
        '  --project={self.project}'
        '  --subnet-mode=custom'
        ).format(self=self)
    self.run_command(command)

  def create_filestore_instance(self):
    log.info('Creating Filestore instance')
    command = (
        'gcloud filestore instances create {self.instance_name}'
        '  --project={self.project}'
        '  --zone={self.zone}'
        '  --tier={self.tier}'
        '  --file-share=name={self.volume_name},capacity={self.terabytes}TB'
        '  --network=name={self.network},reserved-ip-range={self.cidr}'
        ).format(self=self)
    self.run_command(command)
