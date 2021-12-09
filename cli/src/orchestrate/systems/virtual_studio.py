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

"""Deploy a project structure suitable for VFX and animation workloads.

This included creating VPC networks, firewall rules, network peering, instance
templates, instances, etc.
"""

import logging
import os
import tempfile
from orchestrate import base


log = logging.getLogger(__name__)


class VirtualStudio(base.OrchestrateSystem):
  """Deploy Virtual Studio project structure."""

  def __init__(self):
    super(VirtualStudio, self).__init__()
    # Network
    self.workstations_network = 'workstations'
    self.workstations_network_cidr = '10.0.0.0/20'
    self.dns_zone = 'resources'

    # Licenses
    self.licenses_network = None
    self.licenses_project = None
    self.licenses_ip = None

    # Images
    self.image_project = None
    self.image_families = None
    self.gpu_type = None

    # Storage
    self.storage_type = 'elastifile'

  @property
  def description(self):
    return """Deploy Virtual Studio project structure."""

  def run(self):
    """Executes system deployment.

    Returns:
      True if successful. False, otherwise.
    """
    log.info('Deploying Virtual Studio')

    self.create_vpc()
    self.create_vpc_peering()
    self.create_firewall_rules()
    self.create_dns_zones()
    self.create_templates()

  def configure(self):
    """Configure."""
    self.region = '-'.join(self.zone.split('-')[:-1])

    if self.prefix:
      self.prefix += '-'

    self.workstations_network = self.prefix + self.workstations_network
    self.dns_zone_name = self.prefix + self.dns_zone

    storage = self.others.get(self.storage_type, dict())
    self.storage_project = storage.get('project') or self.project
    self.storage_network = storage.get('network') or \
        self.prefix + self.storage_type
    self.storage_ip = storage.get('ip')
    self.volume_names = [volume.split(':')[0] for volume in storage['volumes'].split('|')]

    self.teradici_registration_code = self.others.get('teradici', dict()).get(
        'registration_code')

    self.licenses_project = self.licenses_project or self.project

    if self.deploy_dir:
      command = 'mkdir -p {self.deploy_dir}'.format(self=self)
      self.run_command(command)
    else:
      self.deploy_dir = tempfile.mkdtemp(
          prefix='orchestrate-{self.project}-{self.name}-'.format(self=self),
          dir='/var/tmp',
          )

  def create_vpc(self):
    """Create VPC networks."""
    log.info('Creating VPC %s %s', self.workstations_network,
             self.workstations_network_cidr)
    command = (
        'gcloud compute networks create {self.workstations_network}'
        '  --project={self.project}'
        '  --subnet-mode=custom'
        ).format(self=self)
    self.run_command(command)

    command = (
        'gcloud compute networks subnets create {self.workstations_network}'
        '  --project={self.project}'
        '  --network={self.workstations_network}'
        '  --range={self.workstations_network_cidr}'
        '  --region={self.region}'
        '  --enable-flow-logs'
        '  --enable-private-ip-google-access'
        ).format(self=self)
    self.run_command(command)

  def create_vpc_peering(self):
    """Create VPC network connections."""
    log.info('Peering VPC networks')

    # Storage
    if self.storage_project and self.storage_network \
        and self.storage_network != self.workstations_network:
      log.info('Peering %s:%s to %s:%s', self.storage_project,
               self.storage_network, self.project, self.workstations_network)
      command = (
          'gcloud beta compute networks peerings create'
          '  {self.storage_network}-{self.project}-{self.workstations_network}'
          '  --project={self.storage_project}'
          '  --network={self.storage_network}'
          '  --peer-project={self.project}'
          '  --peer-network={self.workstations_network}'
          '  --export-custom-routes'
          ).format(self=self)
      self.run_command(command)
      log.info('Peering %s:%s to %s:%s', self.project,
               self.workstations_network, self.storage_project,
               self.storage_network)
      command = (
          'gcloud beta compute networks peerings create'
          '  {self.workstations_network}-{self.storage_project}-{self.storage_network}'
          '  --project={self.project}'
          '  --network={self.workstations_network}'
          '  --peer-project={self.storage_project}'
          '  --peer-network={self.storage_network}'
          '  --import-custom-routes'
          ).format(self=self)
      self.run_command(command)
    else:
      log.info('No storage network specified, skipping peering.')

    if self.licenses_network \
        and self.licenses_network != self.workstations_network:
      log.info('Peering %s:%s to %s:%s', self.licenses_project,
               self.licenses_network, self.project, self.workstations_network)
      command = (
          'gcloud beta compute networks peerings create'
          '  {self.licenses_network}-{self.project}-{self.workstations_network}'
          '  --project={self.licenses_project}'
          '  --network={self.licenses_network}'
          '  --peer-project={self.project}'
          '  --peer-network={self.workstations_network}'
          '  --export-custom-routes'
          ).format(self=self)
      self.run_command(command)
      log.info('Peering %s:%s to %s:%s', self.project,
               self.workstations_network, self.licenses_project,
               self.licenses_network)
      command = (
          'gcloud beta compute networks peerings create'
          '  {self.workstations_network}-{self.licenses_project}-{self.licenses_network}'
          '  --project={self.project}'
          '  --network={self.workstations_network}'
          '  --peer-project={self.licenses_project}'
          '  --peer-network={self.licenses_network}'
          '  --import-custom-routes'
          ).format(self=self)
      self.run_command(command)
    else:
      log.info('No licenses network specified, skipping peering.')

  def create_firewall_rules(self):
    """Create firewall rules."""
    log.info('Creating firewall rules')

    # Remote Access protocols
    log.info('%s remote-access: ssh, rdp, icmp', self.workstations_network)
    command = (
        'gcloud compute firewall-rules create'
        '  {self.workstations_network}-remote-access'
        '  --project={self.project}'
        '  --network={self.workstations_network}'
        '  --allow=tcp:22,tcp:3389,icmp'
        '  --enable-logging'
        '  --priority=1000'
        ).format(self=self)
    self.run_command(command)

    # Teradici
    log.info('%s teradici', self.workstations_network)
    command = (
        'gcloud compute firewall-rules create'
        '  {self.workstations_network}-teradici'
        '  --project={self.project}'
        '  --network={self.workstations_network}'
        '  --allow=tcp:443,tcp:4172,tcp:60443,udp:4172'
        '  --enable-logging'
        '  --priority=1000'
        ).format(self=self)
    self.run_command(command)

    # Storage
    if self.storage_project and self.storage_network and self.storage_ip \
        and self.storage_network != self.workstations_network:
      log.info('%s:%s internal from %s:%s', self.storage_network,
               self.storage_network, self.project, self.workstations_network)
      command = (
          'gcloud compute firewall-rules create'
          '  {self.storage_network}-internal-{self.project}-{self.workstations_network}'
          '  --project={self.storage_project}'
          '  --network={self.storage_network}'
          '  --source-ranges={self.workstations_network_cidr},{self.storage_ip}/32'
          '  --allow=tcp,udp,icmp'
          '  --enable-logging'
          '  --priority=1000'
          ).format(self=self)
      self.run_command(command)

    # Licenses
    if self.licenses_network \
        and self.licenses_network != self.workstations_network:
      log.info('%s:%s internal from %s:%s', self.licenses_network,
               self.licenses_network, self.project, self.workstations_network)
      command = (
          'gcloud compute firewall-rules create'
          '  {self.licenses_network}-internal-{self.project}-'
          '{self.workstations_network}'
          '  --project={self.licenses_project}'
          '  --network={self.licenses_network}'
          '  --source-ranges={self.workstations_network_cidr}'
          '  --allow=tcp,udp,icmp'
          '  --enable-logging'
          '  --priority=1000'
          ).format(self=self)
      self.run_command(command)
    else:
      log.info('No licenses network specified, skipping firewall rules')

  def create_dns_zones(self):
    log.info('Creating DNS zones')

    transaction_file = tempfile.mkstemp(
        dir=self.deploy_dir, prefix='dns-transaction-', suffix='.yaml')[1]
    os.remove(transaction_file)

    command = (
        'gcloud dns managed-zones create {self.dns_zone_name}'
        '  --project={self.project}'
        '  --dns-name={self.dns_zone}.'
        '  --visibility=private'
        '  --networks={self.workstations_network}'
        '  --description="License servers, storage clusters, render farms, etc."'
        ).format(self=self)
    self.run_command(command)

    command = (
        'gcloud dns record-sets transaction start'
        '  --project={self.project}'
        '  --zone={self.dns_zone_name}'
        '  --transaction-file={transaction_file}'
        ).format(
            self=self,
            transaction_file=transaction_file,
            )
    self.run_command(command)

    if self.storage_ip:
      # storage.resources
      command = (
          'gcloud dns record-sets transaction add {self.storage_ip}'
          '  --project={self.project}'
          '  --zone={self.dns_zone_name}'
          '  --type=A'
          '  --name=storage.{self.dns_zone}.'
          '  --ttl=300'
          '  --transaction-file={transaction_file}'
          ).format(
              self=self,
              transaction_file=transaction_file,
              )
      self.run_command(command)
      # one record per volume
      # e.g. projects.storage.resources, tools.storage.resources
      for volume_name in self.volume_names:
        command = (
            'gcloud dns record-sets transaction add {self.storage_ip}'
            '  --project={self.project}'
            '  --zone={self.dns_zone_name}'
            '  --type=A'
            '  --name={volume_name}.storage.{self.dns_zone}.'
            '  --ttl=300'
            '  --transaction-file={transaction_file}'
            ).format(
                self=self,
                transaction_file=transaction_file,
                volume_name=volume_name,
                )
        self.run_command(command)

    if self.licenses_ip:
      command = (
          'gcloud dns record-sets transaction add {self.licenses_ip}'
          '  --project={self.project}'
          '  --zone={self.dns_zone_name}'
          '  --type=A'
          '  --name=licenses.{self.dns_zone}.'
          '  --ttl=300'
          '  --transaction-file={transaction_file}'
          ).format(
              self=self,
              transaction_file=transaction_file,
              )
      self.run_command(command)

    command = (
        'gcloud dns record-sets transaction execute'
        '  --project={self.project}'
        '  --zone={self.dns_zone_name}'
        '  --transaction-file={transaction_file}'
        ).format(
            self=self,
            transaction_file=transaction_file,
            )
    self.run_command(command)

  def create_template(self, name, image_family, gpu_type):
    """Create a Orchestrate template.

    Args:
      name: Template name.
      image_family: Name of the base OS image family.
      gpu_type: Type of GPU to accommodate region.
    """
    name = self.prefix + name
    log.info('Creating Orchestrate template name=%s gpu_type=%s zone=%s', name,
             gpu_type, self.zone)

    command = (
        'orchestrate templates create {template_name}'
        '  --project={self.project}'
        '  --zone={self.zone}'
        '  --image-project={self.image_project}'
        '  --image-family={image_family}'
        '  --sizes='
        'name=small,cpus=8,memory=30,disk_size=200,gpu_type={gpu_type},gpu_count=1:'
        'name=medium,cpus=24,memory=60,disk_size=200,gpu_type={gpu_type},gpu_count=1:'
        'name=large,cpus=48,memory=120,disk_size=200,gpu_type={gpu_type},gpu_count=2:'
        'name=xlarge,cpus=96,memory=360,disk_size=200,gpu_type={gpu_type},gpu_count=4'
        '  --default-size-name=medium'
        '  --network={self.workstations_network}'
        '  --instance-name-pattern="{{type}}-{{zone}}-{{gpu_count}}x{{gpu_name}}-{{user}}"'
        '  --metadata='
        'teradici_registration_code="{self.teradici_registration_code}"'
        ).format(
            self=self,
            template_name=name,
            image_family=image_family,
            gpu_type=gpu_type,
            )
    self.run_command(command)

  def create_templates(self):
    if not self.image_project or not self.image_families:
      log.info('No image families specified. Skipping templates creation.')
      return

    if not self.gpu_type:
      if self.region in ['us-east4', 'northamerica-northeast1']:
        self.gpu_type = 'p4-vws'
      else:
        self.gpu_type = 't4-vws'

    for image_family in self.image_families.split(':'):
      self.create_template(image_family, image_family, self.gpu_type)
