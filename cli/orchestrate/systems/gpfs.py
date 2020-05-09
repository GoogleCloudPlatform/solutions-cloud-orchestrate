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

"""Deploy GPFS cache cluster.
"""

import logging
import math
import os
import tempfile
import time
from orchestrate import base


log = logging.getLogger(__name__)


class GPFS(base.OrchestrateSystem):
  """Deploy GPFS instance."""

  def __init__(self):
    super(GPFS, self).__init__()
    # Storage
    self.cluster_name = 'gpfs'
    self.nodes = 1
    self.machine_type = 'n1-highmem-32'
    self.network = 'compute'
    self.cpu_platform = 'Intel Skylake'
    # Creating instances with at least 4xNVME local SSDs for 1.5T gets
    # maximum performance.
    self.disks = 4
    self.storage_type = 'elastifile'
    self.provisioning_script_file_name = None
    self.filesystem_exports_script_file_name = None

    # fine-tunning
    self.gateways = 1
    self.data_replicas = 1
    self.max_data_replicas = 2
    self.metadata_replicas = 1
    self.max_metadata_replicas = 2
    self.page_pool = '100G'
    self.seq_discard_threshold = '1T'
    self.worker_threads = 512
    self.max_stat_cache = 50000
    self.max_files_to_cache = 50000

  @property
  def description(self):
    return """Deploys an GPFS cache cluster."""

  def run(self):
    """Executes system deployment.

    Returns:
      True if successful. False, otherwise.
    """
    log.info('Deploying GPFS')

    self.create_nodes()
    self.wait(180, 'Waiting for nodes to boot up. Thanks for your patience.')
    self.init_ssh_access()
    self.init_cluster()
    self.export_filesystem()

  def configure(self):
    """Configure."""
    self.region = '-'.join(self.zone.split('-')[:-1])

    if self.prefix:
      self.prefix += '-'

    if self.nodes:
      self.nodes = int(self.nodes)

    if self.gateways:
      self.gateways = int(self.gateways)

    if self.deploy_dir:
      command = 'mkdir -p {self.deploy_dir}'.format(self=self)
      self.run_command(command)
    else:
      self.deploy_dir = tempfile.mkdtemp(
          prefix='orchestrate-{self.project}-{self.name}-'.format(self=self),
          dir='/var/tmp',
          )

    if not self.provisioning_script_file_name:
      self.provisioning_script_file_name = \
          '{self.deploy_dir}/gpfs_provisioning.sh'.format(self=self)

    if not self.filesystem_exports_script_file_name:
      self.filesystem_exports_script_file_name = \
          '{self.deploy_dir}/gpfs_filesystem_exports.sh'.format(self=self)

    self.storage_server = '{}.resources'.format(self.storage_type)
    storage = self.others.get(self.storage_type, dict())
    # e.g. 'projects:/projects/root|tools:/tools/root'
    # split into: ['projects', '/projects/root']
    name, volume = storage['volumes'].split('|')[0].split(':')
    self.volume_remote = volume
    self.volume_local = '/{}'.format(name)

  def wait(self, seconds, message):
    """Wait specified amount of time.

    Args:
      seconds (float): Time to wait.
      message: Reason for the wait.
    """
    log.info('Delay %ss: %s', seconds, message)
    if not self.dry_run:
      time.sleep(seconds)

  def get_node_name(self, node):
    """Returns a unique node name based on the cluster name and given node.

    Args:
      node: Node number.
    """
    return '{self.prefix}{self.cluster_name}-node{node}'.format(
        self=self,
        node=node,
        )

  def create_nodes(self):
    """Create nodes for the cluster."""
    log.info('Creating nodes')
    local_ssds = '  --local-ssd=interface=NVME'*self.disks

    for node in range(1, self.nodes+1):
      node_name = self.get_node_name(node)
      command = (
          'gcloud compute instances create {node_name}'
          '  --project={self.project}'
          '  --zone={self.zone}'
          '  --machine-type={self.machine_type}'
          '  --subnet={self.network}'
          '  --no-address'
          '  --maintenance-policy=MIGRATE'
          '  --scopes='
          'https://www.googleapis.com/auth/devstorage.read_only,'
          'https://www.googleapis.com/auth/logging.write,'
          'https://www.googleapis.com/auth/monitoring.write,'
          'https://www.googleapis.com/auth/servicecontrol,'
          'https://www.googleapis.com/auth/service.management.readonly,'
          'https://www.googleapis.com/auth/trace.append'
          '  --min-cpu-platform="{self.cpu_platform}"'
          '  --image=gpfs-final-1'
          '  --image-project=dean-182715'
          '  --boot-disk-size=100GB'
          '  --boot-disk-type=pd-standard'
          '  --boot-disk-device-name={node_name}'
          '  --reservation-affinity=any'
          '  {local_ssds}'
          ).format(
              self=self,
              node_name=node_name,
              local_ssds=local_ssds,
              )
      self.run_command(command)
      command = (
          'gcloud compute instances update {node_name} --deletion-protection'
          ).format(node_name=node_name)
      self.run_command(command)

  def init_ssh_access(self):
    """Initialize passwordless access."""
    log.info('Initializing passwordless access between nodes.')
    for node in range(1, self.nodes+1):
      # Add key to authorized_keys
      command = (
          'gcloud compute ssh --project={self.project} root@{node_name}'
          '  --command="cat /root/.ssh/id_rsa.pub >> /root/.ssh/authorized_keys"'
          ).format(
              self=self,
              node_name=self.get_node_name(node),
              )
      self.run_command(command)
      # Add public keys from all other nodes in the cluster to known_hosts
      # inclusive of current node
      for other_node in range(1, self.nodes+1):
        command = (
            'gcloud compute ssh --project={self.project} root@{node_name} --command=\'ssh-keyscan {other_node_name} | grep ssh-rsa | sed -e "s/{other_node_name}/{other_node_name}.{self.zone}.c.{self.project}.internal/g" - >> /root/.ssh/known_hosts\''
            ).format(
                self=self,
                node_name=self.get_node_name(node),
                other_node_name=self.get_node_name(other_node),
                )
        self.run_command(command)

  def create_provisioning_script(self):
    """Create provisioning script for first node in the cluster."""
    log.info('Creating provisioning script')

    node_entries = []
    node_names = []
    quorum_count = math.ceil(self.nodes/2)
    quorum = 0
    for node in range(1, self.nodes+1):
      node_name = self.get_node_name(node)
      node_names.append(node_name)
      node_entry = self.get_node_name(node)
      if quorum < quorum_count:
        node_entry += ':quorum'
        quorum += 1
      node_entries.append(node_entry)
    node_entries_content = '\n'.join(node_entries)

    disk_entries = []
    for node in range(1, self.nodes+1):
      node_name = self.get_node_name(node)
      for index in range(1, self.disks+1):
        nsd_name = 'd{node_name}nsd{index}'.format(
            node_name=node_name,
            index=index,
            )
        nsd_name = nsd_name.replace('-', '').replace('_', '').replace(' ', '')
        disk_entry = """
%nsd: device=/dev/nvme0n{index}
  nsd={nsd_name}
  servers={node_name}
  usage=dataAndMetadata
""".lstrip().format(
    index=index,
    node_name=node_name,
    nsd_name=nsd_name,
    )
        disk_entries.append(disk_entry)
    disk_entries_content = ''.join(disk_entries)

    wait_on_nodes = []
    for node in range(1, self.nodes+1):
      wait_on_node = (
          'while [ `mmgetstate -N {node_name} -Y | grep {node_name}'
          ' | cut -d: -f9` != "active" ]; do echo "Waiting on {node_name}"'
          ' && sleep 5; done'
          ).format(node_name=self.get_node_name(node))
      wait_on_nodes.append(wait_on_node)
    wait_on_nodes_content = '\n'.join(wait_on_nodes)

    script = """#!/bin/env sh
echo "Creating list of nodes"
cat << EOT > /var/tmp/nodes.txt
{node_entries_content}
EOT

echo "Creating list of disks across all nodes"
cat << EOT > /var/tmp/disks.txt
{disk_entries_content}
EOT

echo "Creating cluster"
mmcrcluster -t lc -n /var/tmp/nodes.txt
# mmlscluster

echo "Accepting license for all nodes"
mmchlicense server --accept -N {node_names}

echo "Fine-tuning performance parameters"
mmchconfig pagepool={self.page_pool} -i -N {node_names}
mmchconfig seqDiscardThreshold={self.seq_discard_threshold} -i
mmchconfig maxStatCache={self.max_stat_cache}
mmchconfig maxFilesToCache={self.max_files_to_cache}
mmchconfig workerThreads={self.worker_threads}

echo "Starting cluster"
mmstartup -a
# mmgetstate -a
# wait until it's done arbitrating
echo "Waiting on all cluster nodes to become active"
{wait_on_nodes_content}

echo "Creating NSDs from disks"
mmcrnsd -F /var/tmp/disks.txt
# mmlsnsd
# ll -lad /dev/n*

echo "Creating file system"
mmcrfs /gpfs/gpfsA /dev/gpfsA -F /var/tmp/disks.txt -B256K -Q yes -r {self.data_replicas} -R {self.max_data_replicas} -m {self.metadata_replicas} -M {self.max_metadata_replicas}
# mmlsnsd

echo "Mounting filesystem"
mmmount gpfsA -a
df -h

# echo "hello from gpfs cluster {self.cluster_name}" > /gpfs/gpfsA/{self.cluster_name}.txt
# cat /gpfs/gpfsA/{self.cluster_name}.txt
# mmlsconfig
# mmlsconfig pagepool

echo "Setting gateway"
mmchnode --gateway -N {gateway_node_names}

echo "Creating fileset {self.volume_local}"
mmcrfileset gpfsA cache -p "afmTarget={self.storage_server}:{self.volume_remote},afmMode=iw" --inode-space=new --inode-limit=10M
mmlinkfileset gpfsA cache -J /gpfs/gpfsA{self.volume_local}
# mmafmctl gpfsA getState
# mmlsfileset gpfsA cache --afm -L
""".lstrip().format(
    self=self,
    node_name=self.get_node_name(1),
    node_names=','.join(node_names),
    gateway_node_names=','.join(node_names[:self.gateways]),
    disk_entries_content=disk_entries_content,
    node_entries_content=node_entries_content,
    wait_on_nodes_content=wait_on_nodes_content,
    )
    if not self.dry_run:
      with open(self.provisioning_script_file_name, 'w') as output_file:
        output_file.write(script)

  def init_cluster(self):
    """Initialize first node in the cluster."""
    log.info('Initializing cluster')
    self.create_provisioning_script()
    self.upload_provisioning_script()
    self.execute_provisioning_script()

  def upload_provisioning_script(self):
    """Upload provisioning script to first node in the cluster for execution."""
    log.info('Uploading provisioning script')
    file_name = os.path.basename(self.provisioning_script_file_name)
    command = (
        'gcloud compute scp --project={self.project}'
        '  {self.provisioning_script_file_name}'
        '  root@{node_name}:/var/tmp/{file_name}'
        ).format(
            self=self,
            node_name=self.get_node_name(1),
            file_name=file_name,
            )
    self.run_command(command)

  def execute_provisioning_script(self):
    """Execute provisioning script on first node."""
    log.info('Executing provisioning script')
    command = (
        'gcloud compute ssh --project={self.project} root@{node_name}'
        '  --command=\'echo "PATH=$PATH:$HOME/bin:/usr/lpp/mmfs/bin ; export PATH" >> /root/.bashrc\''
        ).format(
            self=self,
            node_name=self.get_node_name(1),
            )
    self.run_command(command)
    file_name = os.path.basename(self.provisioning_script_file_name)
    command = (
        'gcloud compute ssh --project={self.project} root@{node_name}'
        '  --command="sh /var/tmp/{file_name}"'
        ).format(
            self=self,
            node_name=self.get_node_name(1),
            file_name=file_name,
            )
    self.run_command(command)

  def export_filesystem(self):
    """Export filesystem from all nodes."""
    log.info('Exporting filesystem')
    self.create_filesystem_exports_script()
    for node in range(1, self.nodes+1):
      self.upload_filesystem_exports_script(node)
      self.execute_filesystem_exports_script(node)

  def create_filesystem_exports_script(self):
    """Create script to export filesystem from cluster."""
    log.info('Creating filesystem export script')

    script = """#!/bin/env sh
echo "Installing nsf-utils"
yum install -y nfs-utils

echo "Exporting fileset {self.volume_local}"
cat << EOT >> /etc/exports
{self.volume_local} *(rw,sync,no_root_squash,no_subtree_check)
EOT

echo "Binding {self.volume_local}"
mkdir {self.volume_local}
mount -o bind /gpfs/gpfsA{self.volume_local} {self.volume_local}
exportfs -r
exportfs
systemctl enable nfs-server
systemctl start nfs-server
systemctl status nfs-server

echo "Force listing of first-level directory on {self.volume_local}"
ls {self.volume_local} > /dev/nul
""".lstrip().format(
    self=self,
    )
    if not self.dry_run:
      with open(self.filesystem_exports_script_file_name, 'w') as output_file:
        output_file.write(script)

  def upload_filesystem_exports_script(self, node):
    """Upload script to export filesystem from cluster.

    Args:
      node: Node index.
    """
    node_name = self.get_node_name(node)
    log.info('Uploading filesystem exports script to %s', node_name)
    file_name = os.path.basename(self.filesystem_exports_script_file_name)
    command = (
        'gcloud compute scp --project={self.project}'
        '  {self.filesystem_exports_script_file_name} root@{node_name}:/var/tmp/{file_name}'
        ).format(
            self=self,
            node_name=node_name,
            file_name=file_name,
            )
    self.run_command(command)

  def execute_filesystem_exports_script(self, node):
    """Execute provisioning script on first node.

    Args:
      node: Node index.
    """
    node_name = self.get_node_name(node)
    log.info('Executing provisioning script on %s', node_name)
    file_name = os.path.basename(self.filesystem_exports_script_file_name)
    command = (
        'gcloud compute ssh --project={self.project} root@{node_name}'
        '  --command="sh /var/tmp/{file_name}"'
        ).format(
            self=self,
            node_name=node_name,
            file_name=file_name,
            )
    self.run_command(command)


