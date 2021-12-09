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

r"""Performs post-creation configuration on a visual remote desktop."""

import collections
import contextlib
import logging
import optparse
import os
import subprocess
import sys

import requests

BIN_DIR = '/usr/local/bin'
TEMP_DIR = '/var/tmp'
TEMPLATES_DIR = '/opt/remotedesktop/templates'
STEP_FILE_NAME = TEMP_DIR + '/remotedesktop-configure.step'

steps = collections.OrderedDict()
METADATA = dict()

USAGE = """Usage: %prog [options] [steps]

Configures steps necessary to finalize the configuration of a Linux Remote
Desktop that uses NVIDIA and Teradici. The instance must already have these
installed, most likely by using remotedesktopstartup.py
Examples of things that are configured by this script are registering the PCoIP
license, setting the password for primary user, etc.

Typical usage:

1. Autoprovision machine upon creation:

  gcloud compute instances create YOUR_VM_NAME \
    --machine-type=custom-24-32768 \
    --accelerator=type=nvidia-tesla-t4-vws,count=1 \
    --can-ip-forward \
    --maintenance-policy TERMINATE \
    --tags 'https-server' \
    --image-project=playground-remotedesktop \
    --image-family=playground-centos-7-visual \
    --boot-disk-size=200 \
    --metadata \
startup-script-url=gs://YOUR_ORCHESTRATE_PROJECT/remotedesktopconfigure.py,\
teradici_registration_code=$TERADICI_REGISTRATION_CODE

2. Run explicitly on an existing VM and provide metadata from the command-line.
   This will override the instance metadata.

  gsutil cp gs://YOUR_ORCHESTRATE_PROJECT/remotedesktopconfigure.py .
  python remotedesktoconfigure.py --metadata \
    teradici_registration_code=$TERADICI_REGISTRATION_CODE
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

LOG_FILE_NAME = '/var/log/remotedesktop-configure.log'
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
  """Determines whether the script can run in the current host.

  Returns:
    True if script is running on a GCE VM. False otherwise.
  """
  try:
    get_metadata('id')
  except:
    log.error('Please run from a GCE VM.')
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
  run('sudo reboot')
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


def configure_teradici():
  """Configures Teradici registration code."""
  registration_code = get_metadata('attributes/teradici_registration_code')
  command = 'pcoip-register-host --registration-code={registration_code}'.format(
      registration_code=registration_code,
      )
  run(command)


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


def main(argv):
  """Performs installation steps.

  Args:
    argv: List of arguments.
  """
  if not can_run():
    sys.exit(1)

  parser = optparse.OptionParser(usage=USAGE)
  parser.add_option('-m', '--metadata', help=(
      'Metadata to override the instance metadata. Same format as gcloud'
      ' compute instances add-metadata.'))
  options, arguments = parser.parse_args(argv)
  parse_metadata(options.metadata)

  requested_steps = arguments
  try:
    # Order matters - this is the order in which we want steps to execute
    steps['teradici'] = configure_teradici

    if requested_steps:
      # Execute specific steps provided by user
      for step in requested_steps:
        function = steps[step]
        install(step, function, force=True)
    else:
      # Execute all steps
      for step, function in steps.items():
        install(step, function)
  except RebootInProgressError:
    log.info('System is rebooting...')
  except Exception:
    log.exception('Unexpected error occurred.')


if __name__ == '__main__':
  main(sys.argv[1:])
