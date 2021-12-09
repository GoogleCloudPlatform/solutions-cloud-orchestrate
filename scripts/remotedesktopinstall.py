#!/usr/bin/env python
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

r"""Provisions graphics remote workstation automatically."""

import base64
import collections
import contextlib
import getpass
import json
import logging
import optparse
import os
import subprocess
import sys
import time

import requests

BIN_DIR = '/usr/local/bin'
TEMP_DIR = '/var/tmp'
TEMPLATES_DIR = '/opt/remotedesktop/templates'
STEP_FILE_NAME = TEMP_DIR + '/remotedesktop-install.step'

steps = collections.OrderedDict()
METADATA = dict()
# These will be set from metadata early in main function
ORCHESTRATE_PROJECT = None
ORCHESTRATE_BUCKET = None

USAGE = """Usage: %prog [options] [steps]

Sets up VM with necessary configuration, drivers and server-side
software to run a Linux Remote Desktop using NVIDIA and Teradici.
Makes use of GCE startup scripts capability. Exploratory script.
Will use more robust tools for provisioning in the future.

Typical usage:

1. Autoprovision machine upon creation:

  gcloud compute instances create YOUR_VM_NAME \
    --machine-type=custom-24-32768 \
    --accelerator=type=nvidia-tesla-t4-vws,count=1 \
    --can-ip-forward \
    --maintenance-policy TERMINATE \
    --tags 'https-server' \
    --image-project=centos-cloud \
    --image-family=centos-7 \
    --boot-disk-size=200 \
    --metadata \
startup-script-url=gs://{project}/remotedesktopinstall.py,\
teradici_registration_code=$TERADICI_REGISTRATION_CODE,\
maya_license_server=$MAYA_LICENSE_SERVER,\
vray_license=$VRAY_LICENSE,\
nuke_license=$NUKE_LICENSE,\
rv_license=$RV_LICENSE,\
storage_volumes=\
server=$ELASTIFILE_SERVER,remote=/projects/root,local=/projects,\
server=$ELASTIFILE_SERVER,remote=/tools/root,local=/tools

2. Run explicitly on an existing VM:

  gsutil cp gs://{project}/remotedesktopinstall.py .
  python remotedesktopinstall.py

  Please note that you will need to run multiple times as there are steps in
  this script that reboot the instance. When ran as a startup script (1) GCE
  will automatically run this on every instance reboot. You would have to do
  it manually.

3. Run a specific installation step:

  gsutil cp gs://{project}/remotedesktopinstall.py .
  python remotedesktopinstall.py nvidia

  Run with --help to see all available installation steps.

4. Provide metadata. This will override the instance metadata.

  gsutil cp gs://{project}/remotedesktopinstall.py .
  python remotedesktopinstall.py nvidia --metadata nvidia_driver_version=418.40
"""


#
# Logging
#

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

log_formatter = logging.Formatter(
    fmt='%(levelname)-9s %(asctime)s %(message)s',
    datefmt='%Y.%m.%d %H:%M:%S',
    )

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
log.addHandler(console_handler)

LOG_FILE_NAME = '/var/log/remotedesktop-install.log'
LOG_FILE = open(LOG_FILE_NAME, 'ab')
file_handler = logging.StreamHandler(LOG_FILE)
file_handler.setFormatter(log_formatter)
log.addHandler(file_handler)


#
# Utils
#


class RebootInProgressError(Exception):
  pass


def get_metadata(key, default=None):
  """Returns value from GCE VM instance.

  Args:
    key: Metadata key to retrieve.
    default: Default value to return if key is not present

  Returns:
    A string with the metadata value.

  Raises:
    KeyError: Key not found in the instance metadata.
    requests.exceptions.ConnectionError: Unable to connect to metadata server.
  """
  # try to get from metadata supplied from command-line first
  global METADATA
  try:
    value = METADATA[key]
    return value
  except KeyError:
    # Continue on to look at the instance metadata
    pass

  # try go get from instance metadata, and return default when applicable
  api_url = 'http://metadata.google.internal/computeMetadata/v1/'
  url = '{api_url}/instance/{key}?alt=text'.format(
      api_url=api_url,
      key=key,
  )
  headers = {
      'Metadata-Flavor': 'Google',
  }
  response = requests.get(url=url, headers=headers)
  if response.ok:
    return response.text
  elif response.status_code == 404 and default is not None:
    return default
  message = '{key} not found in metadata'.format(key=key)
  raise KeyError(message)


def run(command, pii=False):
  """Runs given system command.

  Args:
    command: Command to run.
    pii: Logs command redacted to prevent any PII from leaking in plain text.
         By default it logs the command verbatim. Please make sure to set this
         to True if the command being executed contains passwords or any other
         sensitive information.
  """
  message = command if not pii else '[redacted due to pii]'
  log.info('Executing: %(message)s', dict(message=message))
  subprocess.call(command, stdout=LOG_FILE, stderr=subprocess.STDOUT,
                  shell=True)


def run_commands(commands, pii=False):
  """Runs given list of system commands.

  Args:
    commands: List of commands to run.
    pii: Logs command redacted to prevent any PII from leaking in plain text.
         By default it logs the command verbatim. Please make sure to set this
         to True if the command being executed contains passwords or any other
         sensitive information.
  """
  for command in commands:
    run(command, pii=pii)


def can_run():
  """Determines whether the script can run.

  Consider whether the current host is running on a GCE VM and whether the
  script is running with sudo access.

  Returns:
    True if it is ok to run. False otherwise.
  """
  # Is it GCE VM?
  try:
    get_metadata('id')
  except:  # pylint: disable=bare-except
    log.error('Please run from a GCE VM.')
    return False

  # Running as sudo?
  if os.geteuid() != 0:
    log.error('Requires sudo access.')
    return False

  return True


def can_run_step(step):
  """Determines whether given installation step can be executed.

  The script is designed to install all `steps` in sequence if no arguments are
  provided from the command line. This ensures that steps are executed only once
  and in the order specified in `steps`.

  Args:
    step: Name of the installation step.

  Returns:
    A boolean to indicate whether it can run or not.
  """
  log.info('Checking %(step)s', dict(step=step))

  # Find index of last executed step
  last_step_index = -1
  if os.path.isfile(STEP_FILE_NAME):
    with open(STEP_FILE_NAME, 'r') as input_file:
      last_step = input_file.readline().strip()
      try:
        last_step_index = steps.keys().index(last_step)
      except ValueError:
        pass

  # Find index of step to execute
  try:
    step_index = steps.keys().index(step)
  except ValueError:
    return False

  # Make sure it runs only once and in the expected order
  if step_index <= last_step_index:
    return False

  # Yes, it can run
  return True


@contextlib.contextmanager
def enter_step(step):
  """Marks install step complete.

  Args:
    step: Name of installation step.

  Yields:
    A string with the step name.
  """
  log.info('Installing %(step)s', dict(step=step))
  with open(STEP_FILE_NAME, 'w') as output_file:
    output_file.write(step)
  # Yield actual install execution to caller
  yield step


def reboot():
  """Reboots system and stops further installation steps."""
  run('reboot')
  raise RebootInProgressError


def parse_metadata(text):
  if text is None or not text.strip():
    return
  global METADATA
  text = text.strip()
  pairs = text.split(',')
  items = [pair.split('=') for pair in pairs]
  for key, value in items:
    name = 'attributes/' + key
    METADATA[name] = value


#
# Installation steps
#


def install_core():
  """Installs core system-level tools."""
  commands = """
yum -y update
yum -y groupinstall "Development Tools"
yum install -y gvim xterm
yum install -y python-pip python-virtualenv
pip install --upgrade pip
pip install virtualenvwrapper
pip install --upgrade google-api-python-client oauth2client pyasn1 --ignore-installed requests
pip install --no-cache-dir -U crcmod
  """.strip().split('\n')
  run_commands(commands)


def install_tools():
  """Installs system-level tools required to install nvidia drivers, etc."""
  commands = """
yum -y update
yum -y install kernel-devel
yum -y groupinstall "KDE desktop" "X Window System" "Fonts"
yum -y groupinstall "Server with GUI"
  """.strip().split('\n')
  run_commands(commands)
  reboot()


def install_nvidia():
  """Installs NVIDIA Grid driver."""

  # This driver works for all accelerator types, i.e. t4, p4, v100.
  # Contains both CUDA libraries + visual workstation support.
  # Drivers:
  # 410.92
  # 418.40 - used at GTC for Arnold Beta gpu18 - should be backward compatible
  # 430.63 - 2/5/2020 latest copied from gs://nvidia-drivers-us-public/GRID/
  version = get_metadata('attributes/nvidia_driver_version', '430.63')
  script = 'NVIDIA-Linux-x86_64-{version}-grid.run'.format(
      version=version
      )

  # Execute driver installation script
  commands = """
gsutil cp {bucket}/{script} {temp_dir}
chmod u+x {temp_dir}/{script}
{temp_dir}/{script} --no-questions --ui=none --install-libglvnd
nvidia-smi
  """.format(
      bucket=ORCHESTRATE_BUCKET,
      script=script,
      temp_dir=TEMP_DIR,
  ).strip().split('\n')
  run_commands(commands)


def install_teradici():
  """Installs Teradici PCoIP agent."""
  commands = """
rpm --import https://downloads.teradici.com/rhel/teradici.pub.gpg
yum -y install wget
wget -O /etc/yum.repos.d/pcoip.repo https://downloads.teradici.com/rhel/pcoip.repo
yum -y update
yum -y install pcoip-agent-graphics
systemctl set-default graphical.target
""".strip().split('\n')
  run_commands(commands)
  reboot()


def install_teradici_registration():
  """Installs Teradici registration code."""
  registration_code = get_metadata('attributes/teradici_registration_code')
  commands = """
pcoip-register-host --registration-code={registration_code}
""".format(
    registration_code=registration_code,
).strip().split('\n')
  run_commands(commands)


def install_maya():
  """Installs Maya."""
  # Download location
  temp_dir = TEMP_DIR + '/maya'
  tarball = 'https://up.autodesk.com/2018/MAYA/2EF85F31-A797-48F4-AD2B-551205B969C9/Autodesk_Maya_2018_5_Update_Linux_64bit.tgz'
  file_name = os.path.basename(tarball)

  # Download, install system package, and install Maya using the RPM
  # installation method because the ./setup --noui method still requires an
  # X session which doesn't work when installing completely in non-interactive
  # mode. Method is described here:
  # https://knowledge.autodesk.com/support/maya/troubleshooting/caas/CloudHelp/cloudhelp/2018/ENU/Installation-Maya/files/GUID-E7E054E1-0E32-4B3C-88F9-BF820EB45BE5-htm.html
  log.info('Installing system tools, fonts and Maya')
  commands = """
mkdir -p {temp_dir}
wget -O {temp_dir}/{file_name} {tarball}
tar xvfz {temp_dir}/{file_name} -C {temp_dir}
yum install -y libpng12 compat-libtiff3 gamin
yum install -y libGLEW libXp mesa-libGLw
yum install -y audiofile audiofile-devel e2fsprogs-libs
yum install -y xorg-x11-fonts-ISO8859-1-100dpi xorg-x11-fonts-ISO8859-1-75dpi
yum install -y liberation-mono-fonts liberation-fonts-common
yum install -y liberation-sans-fonts liberation-serif-fonts
rpm -ivh {temp_dir}/Maya2018_64-2018.0-7880.x86_64.rpm
rpm -ivh {temp_dir}/adlmapps14-14.0.23-0.x86_64.rpm
rpm -ivh {temp_dir}/adlmflexnetclient-14.0.23-0.x86_64.rpm
""".format(
    temp_dir=temp_dir,
    file_name=file_name,
    tarball=tarball,
).strip().split('\n')
  run_commands(commands)


def install_maya_license():
  """Registers Maya license."""
  # Determine license parameters
  license_type = get_metadata('attributes/maya_license_type', 'network')
  serial_number = get_metadata('attributes/maya_serial_number', '399-99999966')
  product_key = get_metadata('attributes/maya_product_key', '657J1')
  license_server = get_metadata('attributes/maya_license_server',
                                'licenses.resources')

  file_name = '/usr/autodesk/maya2018/bin/License.env'
  log.info('Writing license file to %s', file_name)
  with open(file_name, 'w') as output_file:
    content = (
        'MAYA_LICENSE={product_key}\n'
        'MAYA_LICENSE_METHOD={license_type}\n'
        ).format(
            product_key=product_key,
            license_type=license_type,
            )
    output_file.write(content)

  file_name = '/var/flexlm/maya.lic'
  log.info('Writing license server details to %s', file_name)
  with open(file_name, 'w') as output_file:
    content = (
        'SERVER {license_server} 0\n'
        'USE_SERVER\n'
        ).format(
            license_server=license_server,
            )
    output_file.write(content)

  log.info('Registering license')
  command = (
      'LD_LIBRARY_PATH=/opt/Autodesk/Adlm/R14/lib64/'
      ' /usr/autodesk/maya2018/bin/adlmreg -i N {product_key} {product_key}'
      ' 2018.0.0.F {serial_number}'
      ' /var/opt/Autodesk/Adlm/Maya2018/MayaConfig.pit').format(
          product_key=product_key,
          serial_number=serial_number,
          )
  run(command)


def get_opencue_metadata():
  """Returns OpenCue metadata dictionary."""
  version = get_metadata('attributes/opencue_version', '0.3.6')
  return dict(
      temp_dir=TEMP_DIR + '/opencue',
      install_dir='/opt/opencue',
      version=version,
      )


def install_opencue():
  """Install OpenCue client."""
  metadata = get_opencue_metadata()

  # Install Python and system tools
  commands = """
mkdir -p {install_dir}
virtualenv {install_dir}
mkdir -p {temp_dir}
cd {temp_dir}
""".format(
    temp_dir=metadata['temp_dir'],
    install_dir=metadata['install_dir'],
).strip().split('\n')
  run_commands(commands)

  # Install OpenCue
  repository_url = 'https://github.com/AcademySoftwareFoundation/OpenCue'
  download_root = '{url}/releases/download/{version}/'.format(
      url=repository_url,
      version=metadata['version'],
      )
  packages = """
pycue-{version}-all.tar.gz
pyoutline-{version}-all.tar.gz
cuegui-{version}-all.tar.gz
cuesubmit-{version}-all.tar.gz
""".strip().format(
    version=metadata['version'],
    ).split('\n')
  for package in packages:
    tarball = download_root + package
    install_python_tarball(tarball, metadata['temp_dir'],
                           metadata['install_dir'])

  # Make binaries available in the default path
  commands = """
ln -s {install_dir}/bin/cuegui {bin_dir}/cuegui
ln -s {install_dir}/bin/cuesubmit {bin_dir}/cuesubmit
""".format(
    install_dir=metadata['install_dir'],
    bin_dir=BIN_DIR,
).strip().split('\n')
  run_commands(commands)

  # Install plugins
  cuesubmit_path = (
      '{install_dir}/lib/python2.7/site-packages/'
      'cuesubmit-{version}-py2.7.egg/cuesubmit'
      ).format(
          install_dir=metadata['install_dir'],
          version=metadata['version'],
          )

  commands = """
  cp -pr {temp_dir}/cuesubmit-{version}-all/plugins {cuesubmit_path}/
  touch {install_dir}/lib/python2.7/site-packages/google/__init__.py
  """.format(
      temp_dir=metadata['temp_dir'],
      version=metadata['version'],
      cuesubmit_path=cuesubmit_path,
      install_dir=metadata['install_dir'],
      ).strip().split('\n')
  run_commands(commands)


def install_python_tarball(tarball, temp_dir, install_dir):
  """Perform a standard procedure to install a Python package from a tarball.

  Args:
    tarball: Fully-qualified Python tarball to download and install.
    temp_dir: Temporary directory for unpacking and building.
    install_dir: Installation directory.
  """
  file_name = os.path.basename(tarball)
  base_name = file_name.split('.tar.gz')[0]

  # Download
  if tarball.startswith('gs://'):
    download_command = 'gsutil cp {tarball} {temp_dir}/{file_name}'
  else:
    download_command = 'wget -O {temp_dir}/{file_name} {tarball}'
  command = download_command.format(
      temp_dir=temp_dir,
      file_name=file_name,
      tarball=tarball,
      )
  run(command)

  # Install
  commands = """
tar xvfz {temp_dir}/{file_name} -C {temp_dir}
(cd {temp_dir}/{base_name} && {install_dir}/bin/pip install -r requirements.txt)
(cd {temp_dir}/{base_name} && {install_dir}/bin/python setup.py install)
""".format(
    temp_dir=temp_dir,
    install_dir=install_dir,
    file_name=file_name,
    base_name=base_name,
).strip().split('\n')
  run_commands(commands)


def install_opencue_environment():
  """Installs OpenCue environment template file.

  This file will be appended to users' Maya.env files.
  """
  metadata = get_opencue_metadata()
  storage_metadata = get_storage_metadata()
  projects_volume =  storage_metadata['volumes']['projects']

  # Environment
  cuesubmit_path = (
      '{install_dir}/lib/python2.7/site-packages/'
      'cuesubmit-{version}-py2.7.egg/cuesubmit'
      ).format(
          install_dir=metadata['install_dir'],
          version=metadata['version'],
          )
  pythonpath = '{cuesubmit_path}/plugins/maya'.format(
      cuesubmit_path=cuesubmit_path,
      )
  xbmlangpath = '{cuesubmit_path}/plugins/maya/%B'.format(
      cuesubmit_path=cuesubmit_path,
      )
  cue_pythonpath = '{install_dir}/lib/python2.7/site-packages'.format(
      install_dir=metadata['install_dir'],
      )
  cuesubmit_config_file = '{local}/data/config/cuesubmit.config'.format(
      local=projects_volume['local'],
      )

  # Ensure templates directory exists
  command = 'mkdir -p {templates_dir}'.format(templates_dir=TEMPLATES_DIR)
  run(command)

  # Write file that could be added on a per-user basis to ~/maya/2018/Maya.env
  file_name = '{templates_dir}/opencue.env'.format(templates_dir=TEMPLATES_DIR)
  with open(file_name, 'w') as output_file:
    content = (
        'PYTHONPATH=$PYTHONPATH:{pythonpath}\n'
        'XBMLANGPATH=$XBMLANGPATH:{xbmlangpath}\n'
        'CUE_PYTHONPATH={cue_pythonpath}\n'
        'CUEBOT_HOSTS=cuebot\n'
        'CUESUBMIT_CONFIG_FILE={cuesubmit_config_file}/\n'
        ).format(
            pythonpath=pythonpath,
            xbmlangpath=xbmlangpath,
            cue_pythonpath=cue_pythonpath,
            cuesubmit_config_file=cuesubmit_config_file,
            )
    output_file.write(content)

  # Write bash file
  file_name = '/etc/profile.d/remotedesktop_opencue.sh'
  with open(file_name, 'w') as output_file:
    content = (
        '# Put all handy things from RV in the path\n'
        '[[ ":$PYTHONPATH:" != *":{pythonpath}:"* ]] && '
        'export PYTHONPATH=$PYTHONPATH:{pythonpath}\n'
        '[[ ":$XBMLANGPATH:" != *":{xbmlangpath}:"* ]] && '
        'export XBMLANGPATH=$XBMLANGPATH:{xbmlangpath}\n'
        '[[ ":$CUE_PYTHONPATH:" != *":{cue_pythonpath}:"* ]] && '
        'export CUE_PYTHONPATH={cue_pythonpath}\n'
        'export CUEBOT_HOSTS=cuebot\n'
        'export CUESUBMIT_CONFIG_FILE={cuesubmit_config_file}\n'
        'export EDITOR=gvim\n'
        ).format(
            pythonpath=pythonpath,
            xbmlangpath=xbmlangpath,
            cue_pythonpath=cue_pythonpath,
            cuesubmit_config_file=cuesubmit_config_file,
            )
    output_file.write(content)


def install_blender():
  """Install Blender."""
  temp_dir = TEMP_DIR + '/blender'
  install_dir = '/opt'
  tarball = 'https://mirror.clarkson.edu/blender/release/Blender2.79/blender-2.79b-linux-glibc219-x86_64.tar.bz2'
  file_name = os.path.basename(tarball)
  base_name = file_name.split('.tar.bz2')[0]
  commands = """
mkdir -p {temp_dir}
wget -O {temp_dir}/{file_name} {tarball}
tar xvfj {temp_dir}/{file_name} -C {install_dir}
chown -R root:root {install_dir}/{base_name}
ln -s {install_dir}/{base_name} {install_dir}/blender
ln -s {install_dir}/blender/blender {bin_dir}/blender
""".format(
    temp_dir=temp_dir,
    install_dir=install_dir,
    bin_dir=BIN_DIR,
    tarball=tarball,
    file_name=file_name,
    base_name=base_name,
).strip().split('\n')
  run_commands(commands)


def get_storage_metadata():
  """Returns storage metadata dictionary."""
  volumes = dict()

  # b/146580026 Format is this:
  #  storage_volumes=NAME:SERVER:REMOTE:LOCAL[|NAME:SERVER:REMOTE:LOCAL][|...]
  # example:
  #  storage_volumes=projects:1.1.1.1:/projects/root:/projects|tools:2.2.2.2:/tools/root:/tools
  default_volumes = (
      'projects:storage.resources:/projects/root:/projects|'
      'tools:storage.resources:/tools/root:/tools'
      )
  text = get_metadata('attributes/storage_volumes', default_volumes)
  if text:
    entries = text.split('|')
    for entry in entries:
      name, server, remote, local = entry.split(':')
      volume = dict(
          name=name,
          server=server,
          remote=remote,
          local=local,
          )
      volumes[name] = volume

  return dict(volumes=volumes)


def install_storage():
  """Install storage configuration and mount points to ECFS."""
  metadata = get_storage_metadata()

  # Install packages
  command = 'yum install -y nfs-utils'
  run(command)

  # Configure mount points

  file_name = '/etc/fstab'
  flags = 'nfs rw,async,hard,intr,noexec 0 0'
  mount_points = [volume['local'] for volume in metadata['volumes'].values()]

  # Make sure mount points are added only once to fstab
  with open(file_name, 'r+') as stream:
    # read current mount points
    existing_lines = stream.read().split('\n')

    # prune lines to be replaced by new volumes
    new_lines = []
    for existing_line in existing_lines:
      # skip line if it matches a mount point
      found = False
      for mount_point in mount_points:
        if mount_point in existing_line and not existing_line.startswith('#'):
          found = True
          break
      # no match, then preserve line
      if not found:
        new_lines.append(existing_line)

    # Add mount points for volumes
    for volume in metadata['volumes'].values():
      line = '{server}:{remote} {local} {flags}'.format(flags=flags, **volume)
      new_lines.append(line)

    # Update contents
    stream.seek(0)
    stream.write('\n'.join(new_lines))
    stream.truncate()

  # Create local mount point directories
  for mount_point in mount_points:
    command = 'mkdir -m 0777 {}'.format(mount_point)
    run(command)


def install_storage_environment():
  """Install storage environment."""
  metadata = get_storage_metadata()

  # Write bash file
  file_name = '/etc/profile.d/remotedesktop_storage.sh'
  tools_volume = metadata['volumes'].get('tools')
  tools_local_bin_dir = '{local}/bin'.format(**tools_volume)
  if tools_volume:
    with open(file_name, 'w') as output_file:
      content = (
          '# Put interesting directories from storage in the path\n'
          '[[ ":$PATH:" != *":{tools_local_bin_dir}:"* ]] && '
          'export PATH=$PATH:{tools_local_bin_dir}\n'
          ).format(tools_local_bin_dir=tools_local_bin_dir)
      output_file.write(content)


def get_vray_metadata():
  """Returns VRay metadata dictionary."""
  license_string = get_metadata('attributes/vray_license',
                                'licenses.resources:30304')
  server, port = license_string.split(':')
  return dict(
      temp_dir=TEMP_DIR + '/vray',
      install_dir='/usr/autodesk/maya2018/vray',
      server=server,
      port=port,
      )


def install_vray():
  """Install Vray."""
  metadata = get_vray_metadata()

  # Download and extract installer
  zip_file = '{bucket}/vray_adv_36004_maya2018_linux_x64.zip'.format(
      bucket=ORCHESTRATE_BUCKET)
  file_name = os.path.basename(zip_file)
  base_name = file_name.split('.zip')[0]
  commands = """
mkdir -p {temp_dir}
gsutil cp {zip_file} {temp_dir}
unzip {temp_dir}/{file_name} -d {temp_dir}/installer
""".format(
    temp_dir=metadata['temp_dir'],
    file_name=file_name,
    zip_file=zip_file,
).strip().split('\n')
  run_commands(commands)

  # Prepare installer configuration
  config = """
<DefValues>
 <Value Name="OPEN_CHANGELOG" DataType="value">0</Value>
 <Value Name="REVERT_INSTALL" DataType="value">1</Value>
 <Value Name="MAYAROOT" DataType="value">/usr/autodesk/maya2018</Value>
 <Value Name="MODULEDEST" DataType="value">/usr/autodesk/modules/maya/2018</Value>
 <Value Name="STDROOT" DataType="value">/usr/ChaosGroup/V-Ray/Maya2018-x64</Value>
 <Value Name="PLUGINS" DataType="value">/usr/autodesk/maya2018/vray</Value>
 <Value Name="INSTALL_TYPE" DataType="value">0</Value>
 <Value Name="REGISTER_RENDERSLAVE_SERVICE" DataType="value">0</Value>
 <Value Name="MAYA_VERSION" DataType="value">2018</Value>
 <Value Name="MAYA_MODULES_DIR" DataType="value">2018</Value>
 <Value Name="REMOTE_LICENSE" DataType="value">1</Value>
 <Value Name="SHOULDUNINSTALL" DataType="value">1</Value>
 <LicServer>
  <Host>{server}</Host>
  <Port>{port}</Port>
  <Host1></Host1>
  <Port1>{port}</Port1>
  <Host2></Host2>
  <Port2>{port}</Port2>
  <User></User>
 </LicServer>
</DefValues>
""".strip().format(
    server=metadata['server'],
    port=metadata['port'],
    )
  config_file_name = '{temp_dir}/installer/config.xml'.format(
      temp_dir=metadata['temp_dir'],
      )
  with open(config_file_name, 'w') as config_file:
    config_file.write(config)

  # Silent installation
  command = (
      '{temp_dir}/installer/{base_name}'
      ' -configFile="{temp_dir}/installer/config.xml"'
      ' -gui=0 -quiet=1 -ignoreErrors=1'
      ).format(
          temp_dir=metadata['temp_dir'],
          base_name=base_name,
          )
  run(command)


def install_vray_environment():
  """Install VRay environment template file.

  This file will be appended to users' Maya.env files.
  """
  metadata = get_vray_metadata()
  command = 'mkdir -p {templates_dir}'.format(templates_dir=TEMPLATES_DIR)
  run(command)
  file_name = '{templates_dir}/vray.env'.format(templates_dir=TEMPLATES_DIR)
  with open(file_name, 'w') as output_file:
    content = (
        'VRAY_FOR_MAYA2018_MAIN_x64={install_dir}\n'
        'VRAY_FOR_MAYA2018_PLUGINS_x64={install_dir}/vrayplugins\n'
        'VRAY_PATH=:{install_dir}/bin\n'
        ).format(
            install_dir=metadata['install_dir'],
            )
    output_file.write(content)


def install_vray_license():
  """Installs VRay license file shared for all users in the same instance."""
  metadata = get_vray_metadata()
  # License file
  command = 'mkdir -p {templates_dir}'.format(templates_dir=TEMPLATES_DIR)
  run(command)
  file_name = '{templates_dir}/vrlclient.xml'.format(
      templates_dir=TEMPLATES_DIR,
      )
  with open(file_name, 'w') as output_file:
    content = """
<VRLClient>
	<LicServer>
		<Host>{server}</Host>
		<Port>{port}</Port>
		<Host1></Host1>
		<Port1>{port}</Port1>
		<Host2></Host2>
		<Port2>{port}</Port2>
		<User></User>
		<Pass></Pass>
	</LicServer>
</VRLClient>
""".strip().format(
    server=metadata['server'],
    port=metadata['port'],
    )
    output_file.write(content)

  # Write bash file
  file_name = '/etc/profile.d/remotedesktop_vray_license.sh'
  with open(file_name, 'w') as output_file:
    content = (
        '# Directory to shared vrlclient.xml file\n'
        'export VRAY_AUTH_CLIENT_FILE_PATH={templates_dir}\n'
        ).format(
            templates_dir=TEMPLATES_DIR,
            )
    output_file.write(content)

  # Write csh file
  file_name = '/etc/profile.d/remotedesktop_vray_license.csh'
  with open(file_name, 'w') as output_file:
    content = (
        '# Directory to shared vrlclient.xml file\n'
        'setenv VRAY_AUTH_CLIENT_FILE_PATH {templates_dir}\n'
        ).format(
            templates_dir=TEMPLATES_DIR,
            )
    output_file.write(content)


def get_nuke_metadata():
  """Returns Nuke metadata directory."""
  version = '11.0v4'
  short_version = version.split('v')[0]
  license_string = get_metadata('attributes/nuke_license',
                                '4101@licenses.resources')
  port, server = license_string.split('@')
  return dict(
      version=version,
      short_version=short_version,
      temp_dir=TEMP_DIR+'/nuke',
      install_dir='/usr/local/Nuke{version}'.format(version=version),
      user=getpass.getuser(),
      server=server,
      port=port,
      )


def install_nuke():
  """Install Nuke."""
  metadata = get_nuke_metadata()
  file_name = 'Nuke{version}-linux-x86-release-64.tgz'.format(
      version=metadata['version']
      )
  tarball = 'https://www.foundry.com/products/download_product?file=' + file_name
  base_name = file_name.split('.tgz')[0]
  installer_name = base_name + '-installer'
  commands = """
mkdir -p {temp_dir}
wget -O {temp_dir}/{file_name} {tarball}
tar xvfz {temp_dir}/{file_name} -C {temp_dir}
unzip {temp_dir}/{installer_name} -d {install_dir}
ln -s {install_dir}/Nuke{short_version} {bin_dir}/nuke
""".format(
    bin_dir=BIN_DIR,
    temp_dir=metadata['temp_dir'],
    install_dir=metadata['install_dir'],
    tarball=tarball,
    file_name=file_name,
    installer_name=installer_name,
    short_version=metadata['short_version'],
).strip().split('\n')
  run_commands(commands)


def install_nuke_license():
  """Install Nuke license."""
  metadata = get_nuke_metadata()
  file_name = '/usr/local/foundry/RLM/foundry_float.lic'
  directory = os.path.dirname(file_name)
  command = 'mkdir -p {directory}'.format(directory=directory)
  run(command)
  timestamp = time.strftime('%a %b %d %H:%M:%S %Y', time.gmtime())
  with open(file_name, 'w') as output_file:
    content = (
        '#License installed by {user} : {timestamp}\n'
        '\n'
        'HOST {server} any {port}\n'
        '\n'
        ).format(
            user=metadata['user'],
            server=metadata['server'],
            port=metadata['port'],
            timestamp=timestamp,
            )
    output_file.write(content)


def get_houdini_metadata():
  """Returns Houdini metadata dictionary."""
  version = '16.5.473'
  tarball = '{bucket}/houdini-{version}-linux_x86_64_gcc4.8.tar'.format(
      bucket=ORCHESTRATE_BUCKET,
      version=version,
      )
  file_name = os.path.basename(tarball)
  directory = file_name.split('.tar')[0]
  install_root = '/opt'
  install_dir = '{install_root}/{directory}'.format(
      install_root=install_root,
      directory=directory,
      )
  return dict(
      temp_dir=TEMP_DIR + '/houdini',
      install_root=install_root,
      install_dir=install_dir,
      version=version,
      tarball=tarball,
      file_name=file_name,
      directory=directory,
      )


def install_houdini():
  """Install Houdini."""
  metadata = get_houdini_metadata()

  # Download and extract installer
  commands = """
yum install -y libGL libXmu libXi
mkdir -p {temp_dir}
gsutil cp {tarball} {temp_dir}
tar xvf {temp_dir}/{file_name} -C {temp_dir}
mkdir -p {install_dir}
{temp_dir}/{directory}/houdini.install --local-licensing --auto-install --accept-EULA {install_dir}
ln -s {install_dir} {install_root}/houdini
ln -s {install_dir}/bin/houdini {bin_dir}/houdini
""".format(
    temp_dir=metadata['temp_dir'],
    install_root=metadata['install_root'],
    install_dir=metadata['install_dir'],
    tarball=metadata['tarball'],
    file_name=metadata['file_name'],
    directory=metadata['directory'],
    bin_dir=BIN_DIR,
).strip().split('\n')
  run_commands(commands)


def install_houdini_license():
  """Install Houdini license."""
  # lartola 2019.03.08 - noop: Using Apprentice license.
  pass


def get_chrome_environment():
  """Returns Chrome metadata dictionary."""
  rpm = 'https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm'
  file_name = os.path.basename(rpm)
  return dict(
      temp_dir=TEMP_DIR + '/chrome',
      rpm=rpm,
      file_name=file_name,
      )


def install_chrome():
  """Install Chrome."""
  metadata = get_chrome_environment()
  commands = """
mkdir -p {temp_dir}
wget -O {temp_dir}/{file_name} {rpm}
yum localinstall -y {temp_dir}/{file_name}
""".format(
    **metadata
).strip().split('\n')
  run_commands(commands)


def get_stackdriver_environment():
  """Returns Stackdriver metadata dictionary."""
  return dict(
      temp_dir=TEMP_DIR + '/stackdriver',
      server_url='https://dl.google.com/cloudagents',
      monitoring_installer='install-monitoring-agent.sh',
      logging_installer='install-logging-agent.sh',
      )


def install_stackdriver():
  """Install Stackdriver monitoring and logging."""
  metadata = get_stackdriver_environment()
  commands = """
mkdir -p {temp_dir}
curl -sS {server_url}/{monitoring_installer} -o {temp_dir}/{monitoring_installer}
bash {temp_dir}/{monitoring_installer}
curl -sS {server_url}/{logging_installer} -o {temp_dir}/{logging_installer}
bash {temp_dir}/{logging_installer} --structured
""".format(**metadata).strip().split('\n')
  run_commands(commands)


def get_djv_metadata():
  """Returns DJV metadata dictionary."""
  version = '1.2.5'
  tarball = 'https://managedway.dl.sourceforge.net/project/djv/djv-stable/{version}/DJV-{version}-Linux.tar.gz'.format(
      version=version,
      )
  file_name = os.path.basename(tarball)
  directory = file_name.split('.tar')[0]
  install_root = '/opt'
  install_dir = '{install_root}/{directory}'.format(
      install_root=install_root,
      directory=directory,
      )
  bin_dir = '{install_root}/djv/bin'.format(
      install_root=install_root,
      )
  lib_dir = '{install_root}/djv/lib'.format(
      install_root=install_root,
      )
  return dict(
      temp_dir=TEMP_DIR + '/djv',
      tarball=tarball,
      file_name=os.path.basename(tarball),
      install_root='/opt',
      install_dir=install_dir,
      bin_dir=bin_dir,
      lib_dir=lib_dir,
      )


def install_djv():
  """Installs DJV."""
  metadata = get_djv_metadata()
  commands = """
mkdir -p {temp_dir}
wget -O {temp_dir}/{file_name} {tarball}
tar xvfz {temp_dir}/{file_name} -C {install_root}
chown -R root:root {install_dir}
ln -s {install_dir} {install_root}/djv
""".format(**metadata).strip().split('\n')
  run_commands(commands)


def install_djv_environment():
  """Installs DJV."""
  metadata = get_djv_metadata()

  # Write bash file
  file_name = '/etc/profile.d/remotedesktop_djv.sh'
  with open(file_name, 'w') as output_file:
    content = (
        '# Put all handy things from DJV in the path\n'
        '[[ ":$PATH:" != *":{bin_dir}:"* ]] && '
        'export PATH=$PATH:{bin_dir}\n'
        ).format(**metadata)
    output_file.write(content)

  # Write bash shell wrappers for binaries in the DJV bin path
  # Set LD_LIBRARY_PATH explicitly before executing binary so that the Qt
  # version does not conflict with other packages like OpenCue.
  # See http://b/128946645
  # Notice that djv_view is not wrapped as djv_view.sh is already provided.
  executables = """
djv_convert
djv_info
djv_ls
""".strip().split('\n')
  for executable in executables:
    # Write wrapper
    file_name = '{bin_dir}/{executable}.sh'.format(
        bin_dir=metadata['bin_dir'],
        executable=executable,
        )
    with open(file_name, 'w') as output_file:
      content = (
          '# Put correct Qt libraries in the path\n'
          'LD_LIBRARY_PATH={lib_dir} {executable} "$@"\n'
          ).format(
              lib_dir=metadata['lib_dir'],
              executable=executable,
              )
      output_file.write(content)
      # Make wrapper executable
      command = 'chmod a+x {file_name}'.format(file_name=file_name)
      run(command)


def get_zync_metadata():
  """Returns Zync metadata dictionary."""
  zync_site = get_metadata('attributes/zync_site', 'https://demo.zync.io')
  version = '1.26.60'
  url = 'http://storage.googleapis.com/zync-public/installers/client_app'
  rpm = '{url}/{version}/zync-{version}-2.noarch.rpm'.format(
      url=url,
      version=version,
      )
  file_name = os.path.basename(rpm)
  directory = 'zync-{version}'.format(version=version)
  plugins_root = '/opt'
  plugins_dir_versionless = '{plugins_root}/zync'.format(
      plugins_root=plugins_root,
      )
  plugins_dir = '{plugins_root}/{directory}'.format(
      plugins_root=plugins_root,
      directory=directory,
      )
  bin_dir = '{plugins_dir_versionless}/bin'.format(
      plugins_dir_versionless=plugins_dir_versionless,
      )
  lib_dir = '{plugins_dir_versionless}/lib'.format(
      plugins_dir_versionless=plugins_dir_versionless,
      )
  return dict(
      version=version,
      zync_site=zync_site,
      temp_dir=TEMP_DIR + '/zync',
      rpm=rpm,
      file_name=file_name,
      plugins_root='/opt',
      plugins_dir=plugins_dir,
      plugins_dir_versionless=plugins_dir_versionless,
      bin_dir=bin_dir,
      lib_dir=lib_dir,
      )


def install_zync():
  """Installs Zync."""
  metadata = get_zync_metadata()
  commands = """
mkdir -p {temp_dir}
wget -O {temp_dir}/{file_name} {rpm}
rpm -ivh {temp_dir}/{file_name} --replacefiles
mkdir -p {plugins_dir}
ln -s {plugins_dir} {plugins_dir_versionless}
virtualenv {plugins_dir_versionless}
""".format(**metadata).strip().split('\n')
  run_commands(commands)
  install_zync_python()
  install_zync_maya()
  install_zync_nuke()


def install_zync_python():
  """Installs Zync Python API."""
  metadata = get_zync_metadata()
  local_dir = '{temp_dir}/zync-python'.format(**metadata)
  commands = """
git clone https://github.com/zync/zync-python.git {local_dir}
echo 'ZYNC_URL = "{zync_site}"' > {local_dir}/zync_config.py
cp -R {local_dir} {lib_dir}/python2.7/site-packages/
""".format(
    local_dir=local_dir,
    **metadata
    ).strip().split('\n')
  run_commands(commands)


def install_zync_maya():
  """Installs Zync Maya."""
  metadata = get_zync_metadata()
  local_dir = '{temp_dir}/zync-maya'.format(**metadata)
  commands = """
git clone https://github.com/zync/zync-maya.git {local_dir}
echo "API_DIR = '{lib_dir}/python2.7/site-packages/zync-python'" > {local_dir}/scripts/config_maya.py
cp -R {local_dir} {lib_dir}/python2.7/site-packages/
mkdir -p /opt/remotedesktop/maya/2018
echo '+ zync 1.0 {lib_dir}/python2.7/site-packages/zync-maya' > /opt/remotedesktop/maya/2018/zync.mod
""".format(
    local_dir=local_dir,
    **metadata
    ).strip().split('\n')
  run_commands(commands)


def install_zync_nuke():
  """Installs Zync Nuke."""
  metadata = get_zync_metadata()
  local_dir = '{temp_dir}/zync-nuke'.format(**metadata)
  commands = """
git clone https://github.com/zync/zync-nuke.git {local_dir}
echo "API_DIR = '{lib_dir}/python2.7/site-packages/zync-python'" > {local_dir}/config_nuke.py
cp -R {local_dir} {lib_dir}/python2.7/site-packages/
mkdir -p /opt/remotedesktop/nuke
""".format(
    local_dir=local_dir,
    **metadata
    ).strip().split('\n')
  run_commands(commands)

  with open('/opt/remotedesktop/nuke/menu.py', 'w') as output_file:
    content = """
import nuke
nuke.pluginAddPath('{lib_dir}/python2.7/site-packages/zync-nuke')
import zync_nuke
menubar = nuke.menu('Nuke')
menu = menubar.addMenu('&Render')
menu.addCommand('Render on Zync', 'zync_nuke.submit_dialog()')
""".format(**metadata).lstrip()
    output_file.write(content)


def install_zync_environment():
  """Installs Zync environment."""
  metadata = get_zync_metadata()

  # Write bash file
  maya_module_path = '/opt/remotedesktop/maya/2018'
  nuke_path = '/opt/remotedesktop/nuke'
  file_name = '/etc/profile.d/remotedesktop_zync.sh'
  with open(file_name, 'w') as output_file:
    content = (
        '# Put all handy things from Zync in the path\n'
        '[[ ":$PATH:" != *":{bin_dir}:"* ]] && '
        'export PATH=$PATH:{bin_dir}\n'
        '# Load Zync for Maya plugin\n'
        '[[ ":$MAYA_MODULE_PATH:" != *":{maya_module_path}:"* ]] && '
        'export MAYA_MODULE_PATH=$MAYA_MODULE_PATH:{maya_module_path}\n'
        '# Load Zync for Nuke plugin\n'
        '[[ ":$NUKE_PATH:" != *":{nuke_path}:"* ]] && '
        'export NUKE_PATH=$NUKE_PATH:{nuke_path}\n'
        ).format(
            maya_module_path=maya_module_path,
            nuke_path=nuke_path,
            **metadata
            )
    output_file.write(content)

  # Write convenience bash shell wrapper to launch zync.
  file_name = '{bin_dir}/zync'.format(
      bin_dir=metadata['bin_dir'],
      )
  with open(file_name, 'w') as output_file:
    content = (
        '#!/bin/sh\n'
        'java -jar /usr/local/zync/Zync.jar\n'
        )
    output_file.write(content)
    # Make wrapper executable
    command = 'chmod a+x {file_name}'.format(file_name=file_name)
    run(command)


def get_gcsfuse_metadata():
  """Returns gcsfuse metadata dictionary."""
  shots_bucket = get_metadata('attributes/gcsfuse_shots_bucket', 'shots')
  local_shots = get_metadata('attributes/gcsfuse_local_shots', '/shots')
  return dict(
      shots_bucket=shots_bucket,
      local_shots=local_shots,
      )


def install_gcsfuse():
  """Installs gcsfuse."""
  metadata = get_gcsfuse_metadata()

  # Configure the gcsfuse repo
  file_name = '/etc/yum.repos.d/gcsfuse.repo'
  with open(file_name, 'w') as output_file:
    content = """
[gcsfuse]
name=gcsfuse (packages.cloud.google.com)
baseurl=https://packages.cloud.google.com/yum/repos/gcsfuse-el7-x86_64
enabled=1
gpgcheck=1
repo_gpgcheck=1
gpgkey=https://packages.cloud.google.com/yum/doc/yum-key.gpg
       https://packages.cloud.google.com/yum/doc/rpm-package-key.gpg
""".lstrip()
    output_file.write(content)

  # Install gcsfuse
  commands = """
mkdir -m 0777 {local_shots}
yum update -y
yum install -y gcsfuse
""".format(**metadata).strip().split('\n')
  run_commands(commands)

  # TODO(lartola) http://b/129718602
  # Commenting out because adding to gcsfuse mount point to /etc/fstab causes
  # permissions issues and have not been able to resolve. There is an acceptable
  # workflow for now by having user explicitly mounting /shots. See ticket for
  # more details.
  #
  # # Make sure mount point is added only once to fstab
  # file_name = '/etc/fstab'
  # with open(file_name, 'r+') as stream:
  #   line = (
  #       '\n{shots_bucket} {local_shots} gcsfuse rw,noauto,user\n'
  #       ).format(
  #           **metadata
  #           )
  #   content = stream.read()
  #   if line not in content:
  #     stream.seek(0)
  #     stream.write(content)
  #     stream.write(line)
  #     stream.truncate()


def get_arnold_metadata():
  """Returns Arnold metadata dictionary."""
  version = '3.2.0.gpu18'
  tarball = '{bucket}/MtoA-{version}-linux-2018.run'.format(
      bucket=ORCHESTRATE_BUCKET,
      version=version,
      )
  installer = os.path.basename(tarball)
  return dict(
      version=version,
      temp_dir=TEMP_DIR + '/arnold',
      tarball=tarball,
      installer=installer,
      )


def install_arnold():
  """Installs Arnold renderer for Maya."""
  metadata = get_arnold_metadata()

  commands = """
mkdir -p {temp_dir}
gsutil cp {tarball} {temp_dir}
sh {temp_dir}/{installer} -- silent
""".format(**metadata).strip().split('\n')
  run_commands(commands)


def get_resolve_metadata():
  """Returns DaVinci Resolve metadata dictionary."""
  version = '16.1.2'
  zip_file = '{bucket}/DaVinci_Resolve_{version}_Linux.zip'.format(
      bucket=ORCHESTRATE_BUCKET,
      version=version,
      )
  base_name = os.path.basename(zip_file)
  installer = os.path.splitext(base_name)[0] + '.run'
  return dict(
      version=version,
      temp_dir=TEMP_DIR + '/resolve',
      base_name=base_name,
      zip_file=zip_file,
      installer=installer,
      bin_dir='/opt/resolve/bin',
      )


def install_resolve():
  """Installs DaVinci Resolve."""
  metadata = get_resolve_metadata()

  commands = """
mkdir -p {temp_dir}
gsutil cp {zip_file} {temp_dir}
unzip -u {temp_dir}/{base_name} -d {temp_dir}
{temp_dir}/{installer} --install --noconfirm --nonroot --allowroot
""".format(**metadata).strip().split('\n')
  run_commands(commands)


def install_resolve_environment():
  """Installs DaVinci Resolve environment."""
  metadata = get_resolve_metadata()

  # Write bash file
  file_name = '/etc/profile.d/remotedesktop_resolve.sh'
  with open(file_name, 'w') as output_file:
    content = (
        '# Put all handy things from DaVinci Resolve in the path\n'
        '[[ ":$PATH:" != *":{bin_dir}:"* ]] && '
        'export PATH=$PATH:{bin_dir}\n'
        ).format(**metadata)
    output_file.write(content)


#
# Bootstrap
#


def install(step, function, force=False):
  """Runs given installation step.

  Args:
    step: Installation step name.
    function: Function that executes installation commands.
    force: Executes step regardless of whether it has been previously run or not
      when set to True. Executes only if step hasn't been run before by default.
  """
  if force or can_run_step(step):
    with enter_step(step):
      function()


def finalize(request_id, success):
  """Finalizes the image provisioning operation according to success result.

  Assumes that this is was triggered by Orchestrate if request_id is not empty.
  Otherwise, it does not publish a notification.

  Args:
    request_id (str): Orchestrate request id for this operation.
    success (bool): Indicates whether all provisioning steps ran completely.
  """
  log.info('Provisioning finished.')

  if request_id:
    notify_end(request_id, success)
  else:
    log.info('There is not Orchestrate request_id. Skipping notification.')

  if success:
    cleanup()


def notify_end(request_id, success):
  """Notifies Orchestrate that this image provisioning operation is complete.

  Assumes that this is was triggered by Orchestrate if request_id is not empty.
  Otherwise, it does not publish a notification.

  Args:
    request_id (str): Orchestrate request id for this operation.
    success (bool): Indicates whether all provisioning steps ran completely.
  """
  try:
    log.info('Provisioning finished.')
    if not request_id:
      log.info('There is not Orchestrate request_id. Skipping notification.')
      return

    # Import here because googleapiclient is not available by default. It only
    # becomes available after explicitly pip installing it during install_tools
    # pylint: disable=g-import-not-at-top
    from googleapiclient import discovery

    topic_end = 'image_provisioning_end'
    pubsub = discovery.build('pubsub', 'v1')
    topic = 'projects/{project}/topics/{topic}'.format(
        project=ORCHESTRATE_PROJECT,
        topic=topic_end,
        )
    log.info('Sending message to %s', topic)

    image = get_metadata('attributes/orchestrate_image', None)
    parameters = dict(
        request_id=request_id,
        image=image,
        success=success,
        )
    data = json.dumps(parameters)
    message = dict(data=base64.b64encode(data))
    response = pubsub.projects().topics().publish(
        topic=topic,
        body=dict(messages=[message])
        ).execute()
    log.info('Message publish result: %s', response)

  except:  # pylint: disable=bare-except
    # We want full visibility in the logs of any unexpected errors that occur.
    log.exception('Unexpected error trying to notify end of provisioning.')


def cleanup():
  """Remove all temporary state and files as needed."""
  log.info('Cleaning up')
  if os.path.isfile(STEP_FILE_NAME):
    os.remove(STEP_FILE_NAME)


def main(argv):
  """Performs installation steps.

  Args:
    argv: List of arguments.
  """
  if not can_run():
    sys.exit(1)

  try:
    request_id = get_metadata('attributes/orchestrate_request_id', '')
    log.info('Provisioning started: request_id=%s', request_id)

    parser = optparse.OptionParser(usage=USAGE)
    parser.add_option(
        '-m', '--metadata', help=(
            'Metadata to override the instance metadata. '
            'Same format as gcloud compute instances add-metadata.')
        )
    parser.add_option(
        '-f', '--force', action='store_true', default=False, help=(
            'Force installation of explicitly requested steps even if they have'
            ' been installed before. This is only an option when running'
            ' interactively from a shell. The script will never force'
            ' installation when running as a stratup script because this could'
            ' cause an infinite restarting loop if some of the steps cause a'
            ' reboot.')
        )
    options, arguments = parser.parse_args(argv)
    parse_metadata(options.metadata)

    global ORCHESTRATE_PROJECT
    global ORCHESTRATE_BUCKET
    ORCHESTRATE_PROJECT = get_metadata('attributes/orchestrate_project')
    ORCHESTRATE_BUCKET = 'gs://{project}/software'.format(
        project=ORCHESTRATE_PROJECT)

    requested_steps = arguments
    if not requested_steps:
      requested_steps = get_metadata('attributes/steps', '')
      requested_steps = requested_steps.split(':') if requested_steps else None
    headless_worker = get_metadata('attributes/headless_worker', False)

    # Order matters - this is the order in which we want steps to execute
    steps['core'] = install_core
    steps['stackdriver'] = install_stackdriver
    steps['tools'] = install_tools
    steps['chrome'] = install_chrome
    # Install nvidia drivers regardless of whether it's headless or not.
    # The driver includes both CUDA for compute and virtual desktop support.
    steps['nvidia'] = install_nvidia
    if not headless_worker:
      steps['teradici'] = install_teradici
      steps['teradici_registration'] = install_teradici_registration
    steps['storage'] = install_storage
    steps['storage_environment'] = install_storage_environment
    steps['maya'] = install_maya
    steps['maya_license'] = install_maya_license
    steps['vray'] = install_vray
    steps['vray_license'] = install_vray_license
    steps['vray_environment'] = install_vray_environment
    steps['opencue'] = install_opencue
    steps['opencue_environment'] = install_opencue_environment
    steps['blender'] = install_blender
    steps['nuke'] = install_nuke
    steps['nuke_license'] = install_nuke_license
    steps['houdini'] = install_houdini
    steps['houdini_license'] = install_houdini_license
    steps['djv'] = install_djv
    steps['djv_environment'] = install_djv_environment
    steps['zync'] = install_zync
    steps['zync_environment'] = install_zync_environment
    steps['gcsfuse'] = install_gcsfuse
    steps['arnold'] = install_arnold
    steps['resolve'] = install_resolve
    steps['resolve_environment'] = install_resolve_environment

    if requested_steps:
      # Execute specific steps provided by user
      for step in requested_steps:
        function = steps[step]
        install(step, function, force=options.force)
    else:
      # b/154015547 - If no explicit steps provided, execute steps that install
      # open-source software only, or third-party software licensed or otherwise
      # already bundled by GCP, e.g. NVIDIA drivers.
      default_steps = [
          'core',
          'stackdriver',
          'tools',
          'chrome',
          'nvidia',
          'teradici',
          'storage',
          'storage_environment',
      ]
      for step in default_steps:
        function = steps[step]
        install(step, function)

    # All done! Notify success
    finalize(request_id, success=True)

  except RebootInProgressError:
    log.info('System is rebooting...')

  except:  # pylint: disable=bare-except
    # We want full visibility in the logs of any unexpected errors that occur.
    log.exception('Unexpected error occurred while provisoning image.')
    notify_end(request_id, success=False)


if __name__ == '__main__':
  main(sys.argv[1:])
