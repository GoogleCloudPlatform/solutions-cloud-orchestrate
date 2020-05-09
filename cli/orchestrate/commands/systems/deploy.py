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

r"""Orchestrates the deployment of complete systems.

Usage: orchestrate systems deploy [OPTIONS] <SYSTEM,...>
"""

import logging
import optparse
import os
import pkgutil
import subprocess

import orchestrate
from orchestrate import base

log = logging.getLogger(__name__)


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
  log.debug('Executing: %(message)s', dict(message=message))
  subprocess.call(command, shell=True)


def find_valid_systems(path):
  """Returns valid systems in the given path.

  A valid system is either a module, or a non-empty package.

  Args:
    path: Path to package to introspect.

  Returns:
    A dict that includes the module loader indexed by system name.
  """
  systems = dict()
  for module_info in pkgutil.walk_packages([path]):
    name = module_info.name.replace('_', '-')
    if not module_info.ispkg:
      systems[name] = module_info
    else:
      submodule_path = os.path.sep.join([path, module_info.name])
      for _ in pkgutil.walk_packages([submodule_path]):
        # Add module (not submodule) if it contains at least one valid submodule
        systems[name] = module_info
        break
  return systems


def find_all_valid_systems():
  """Returns dict of all valid systems."""
  directory = os.path.dirname(orchestrate.__file__)
  path = os.path.abspath(os.path.sep.join([directory, 'systems']))
  systems = find_valid_systems(path)
  return systems


class ExecutionOptions:

  def __init__(self, options):
    self.__dict__.update(options)

SYSTEMS = find_all_valid_systems()


class Command(base.OrchestrateCommand):
  """Orchestrates the deployment of various complete systems."""
  system_classes = dict()

  @property
  def description(self):
    system_names = ['- ' + name for name in sorted(SYSTEMS)]
    system_names = '\n'.join(system_names)
    return """Orchestrates the deployment of various complete systems.

Available systems:
{systems}

Sample usage:

1. Deploy an Elastfile cluster and a Virtual Studio layout with the prefix vfx
   using the default values for VPCs, DNS Zones, etc.:

    orchestrate systems deploy elastifile virtual-studio --prefix=vfx

2. Deploy an Elastifile cluster and a Virtual Studio layout with the prefix
   animation. Uses a custom IP range for the Elastifile cluster and its
   load balancer virtual IP:

    orchestrate systems deploy elastifile virtual-studio --prefix=animation \\
      --elastifile=cidr=172.16.1.0/24,ip=172.16.2.1
""".format(systems=system_names)

  @property
  def options(self):
    """Returns command parser options."""
    options = [
        optparse.Option('--help-system', action='store_true', help=(
            'Displays help for the deployment scripts for selected systems.')),
        optparse.Option('-x', '--prefix', default='', help=(
            'Prefix to use for orchestrated resources')),
        optparse.Option(
            '-d', '--dry-run', action='store_true', default=False, help=(
            'Show what it would run but do not actually run it.')),
        ]
    for system in SYSTEMS:
      options.append(optparse.Option('--' + system.replace('_', '-')))
    return options

  def run(self, options, arguments):
    """Executes command.

    Args:
      options: Command-line options for all systems organized by system name.
      arguments: Command-line positional arguments

    Returns:
      True if successful. False, otherwise.
    """
    log.debug('deploy %(options)s %(arguments)s', dict(
        options=options, arguments=arguments))

    system_names = arguments
    if not system_names:
      log.info('Please specify systems to deploy. See --help for more'
               ' information.')
      return False

    try:
      unknown_systems = set(system_names).difference(set(SYSTEMS))
      if unknown_systems:
        log.error(
            'The following systems are not available: %s.'
            ' See --help for list of available systems.',
            ', '.join(list(unknown_systems)))
        return False

      # Initialize systems with their options provided from the command-line
      systems = self.initialize_systems(options, system_names)

      # Deploy one at a time
      for system_name, system in systems.items():
        log.info('Deploying %s', system_name)
        if options.help_system:
          log.info(system.usage)
        else:
          system.run()
    except TypeError:
      log.exception('Unexpected error deploying system')
      return False

    return True

  def load_system(self, name, force=False):
    """Locate and instantiate first instance of OrchestrateSystem.

    It caches the loaded class to expedite multiple calls for the same system.

    Args:
      name: Name of module to load.
      force: Uses cached class previously loaded for performance reasons when
        set to False (default). Locate module and load it otherwise.

    Returns:
      An instance of OrchestrateSystem.

    Raises:
      TypeError if no OrchestrateSystem subclass is found.
    """
    system_type = self.system_classes.get(name)

    if not system_type or force:
      try:
        # Locate and load module
        module_info = SYSTEMS[name]
        module_name = name.replace('-', '_')
        loader = module_info.module_finder.find_module(module_name)
        module = loader.load_module(module_name)

        # Locate and load OrchestrateSystem instance
        for _, class_type in module.__dict__.items():
          if isinstance(class_type, type) and \
              issubclass(class_type, base.OrchestrateSystem):
            system_type = class_type
            # Cache to expedite subsequent calls for the same system
            self.system_classes[name] = system_type
            break
        if not system_type:
          raise TypeError()
      except TypeError:
        log.error('Could not find implementation of OrchestrateSystem %s', name)
        raise

    # Instantiate system
    system = system_type()
    return system

  def initialize_systems(self, options, system_names):
    """Consolidate options for all systems and override defaults for each one.

    Args:
      options: Command-line options as parsed by the option parser.
      system_names: Names of the systems to load and initialize.

    Returns:
      A dict with OrchestrateSystems instances indexed by system name.
    """
    all_systems = dict()
    for system_name in SYSTEMS:
      all_systems[system_name] = self.load_system(system_name)

    # Get options applicable to all systems excluding select options intended
    # for Orchestrate itself and those that match the name of as supported
    # systems.
    global_options = dict()
    filtered_options = ['api_key', 'api_host', 'api_project', 'help_system'] + \
        list(SYSTEMS.keys())
    all_option_names = vars(options).keys()
    global_option_names = set(all_option_names).difference(filtered_options)
    for global_option_name in global_option_names:
      global_options[global_option_name] = getattr(options, global_option_name)

    # Add a namespace per system name
    # Split the system-specific key=value,... lists
    # e.g. turn: --system1=one=1,two=2,three=3
    #      into: system1=dict(one=1, two=2, three=3)
    consolidated_options = dict()
    for system_name, system in all_systems.items():
      # override system's default values from provided command-line options
      system_options = dict(system.defaults if system else dict())
      provided_options = getattr(options, system_name.replace('-', '_'))
      if provided_options:
        for provided_option in provided_options.split(','):
          key, value = provided_option.split('=')
          key = key.replace('-', '_')
          system_options[key] = value
      consolidated_options[system_name] = system_options

    # hydrate each system data members from options explicitly provided for
    # the system via the command-line plus global options
    for system_name, system in all_systems.items():
      vars(system).update(consolidated_options.get(system_name, dict()))
      vars(system).update(global_options)
      system.name = system_name
      system.others = dict(
          (name, options) for name, options in consolidated_options.items()
          if name != system_name)

    systems = dict()
    for system_name, system in all_systems.items():
      system.configure()
      if system_name in system_names:
        systems[system_name] = system

    return systems
