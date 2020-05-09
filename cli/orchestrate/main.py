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

"""Executes main command-line entry-point.
"""

import inspect
import logging
import optparse
import os
import pkgutil
import sys

from orchestrate import utils
# We need to import this module in order to configure loggers.
# pylint: disable=unused-import
import orchestrate.logger

log = logging.getLogger(__name__)


def execute_command(name, parents, loader, arguments):
  """Executes the given command.

  Args:
    name: Command name, e.g. create.
    parents: Names of parent commands, e.g. ['orchestrate', 'images']
    loader: Object that can load the module containing the command.
    arguments: Arguments relevant to the command.
  """
  log.debug('execute %(parents)s %(command)s %(arguments)s', dict(
      parents=' '.join(parents),
      command=name,
      arguments=arguments,
      ))
  log.debug('loading module from %s', loader)

  # Load module
  module = loader.find_module(name).load_module(name)

  # Instantiate command
  try:
    command_type = getattr(module, 'Command')
    if not inspect.isclass(command_type):
      raise TypeError()
  except (AttributeError, TypeError):
    log.error('Could not find implementation of OrchestrateCommand in module %s',
              module.__file__)
    return
  command = command_type()

  # Parse arguments
  usage = """Usage: {parents} {command} [OPTIONS] [ARGUMENTS]

{description}""".format(
    parents=' '.join(parents),
    command=name,
    description=command.description,
    )
  parser = optparse.OptionParser(usage=usage)

  defaults = dict()
  defaults.update(utils.get_common_option_defaults())
  defaults.update(command.defaults)
  parser.set_defaults(**defaults)

  common_options_group = optparse.OptionGroup(parser, 'Global options')
  common_options_group.add_options(utils.get_common_options())
  parser.add_option_group(common_options_group)
  parser.add_options(command.options)

  options, arguments = parser.parse_args(arguments)

  if options.verbose:
    logging.getLogger().setLevel(logging.DEBUG)

  # Execute command
  command.run(options, arguments)


def find_valid_commands(path):
  """Returns list of valid commands in the given path.

  A valid command is either a module, or a package that contains at least one
  package or a module. This would effectively trim empty command packages.

  Args:
    path: Path to package to introspect.
  """
  commands = []
  for module_info in pkgutil.walk_packages([path]):
    if not module_info.ispkg:
      commands.append(module_info.name)
    else:
      submodule_path = os.path.sep.join([path, module_info.name])
      for _ in pkgutil.walk_packages([submodule_path]):
        # Add module (not submodule) if it contains at least one valid submodule
        commands.append(module_info.name)
        break
  return commands


def suggest_recovery_options(command, parents, path, children_names):
  """Suggest sensible recovery options when no command is found.

  There is likely a syntax error, or a non-existent command, e.g.
    orchestrate images crate (instead of create)
    orchestrate foobar create (foobar in not a command)

  User could have typed a non-leaf command, e.g.:
    orchestrate images (instead of orchestrate images create)

  Let's provide user with information about recovery options and possible
  subcommands at the deepest level we managed to get.

  Args:
    command: Attempted command.
    parents: Upper command levels.
    path: Path to last valid command.
    children_names: Names of valid commands found at immediate parent above.
  """
  parent_path = os.path.dirname(path)
  valid_commands = find_valid_commands(path)

  # Was it a syntax error?
  if command not in children_names[parent_path]:
    log.error('Invalid choice: %s', command)
    log.info('Maybe you meant:')
  else:
    # It was an incomplete command
    if valid_commands:
      log.info('Command name argument expected.')
      full_command = ' '.join(parents)
    else:
      log.error('Invalid choice: %s', command)
      full_command = ' '.join(parents[:-1])
    log.info('Available commands for %s:', full_command)

  # If no commands at the current level, provide suggestions at the level above.
  if not valid_commands:
    valid_commands = find_valid_commands(parent_path)
  for valid_command in valid_commands:
    log.info('  %s', valid_command.replace('_', '-'))


def main(arguments=None):
  """Runs command-line.

  Args:
    arguments: Command arguments. If none specified, it uses the default
      provided from the command-line, i.e. sys.argv.
  """
  if arguments is None:
    arguments = sys.argv[1:]

  loaders = dict()
  parents = ['orchestrate']
  directory = os.path.dirname(__file__)
  path = os.path.abspath(os.path.sep.join([directory, 'commands']))
  children_names = {
      directory: parents[:],
  }
  command = ''

  # Iterate arguments trying to find a matching command by name.
  # If we find a submodule with a matching name, we try to load a command
  # instance from the submodule and execute it with the remaining arguments.
  # For example:
  #   orchestrate images create test-image-1 --packages=maya,nuke,houdini
  # Would walk looking for the following commands in this order:
  #   1. images
  #   2. create
  # When it reaches "create", it would load the orchestrate.commands.image.create
  # module and will attempt to run Command.run() with the remaining arguments:
  #   test-image-1 --packages=maya,nuke,houdini
  for index, command in enumerate(arguments):
    command = command.replace('-', '_')
    children_names[path] = []
    can_continue = False
    for loader, name, is_package in pkgutil.walk_packages([path]):
      # Save reference to modules in every level so that we can provide more
      # information to user in case we fail to find a matching command.
      module_path = os.path.sep.join([path, name])
      loaders[module_path] = loader
      children_names[path].append(name)
      # Execute command if we reach a submodule with a matching name
      if command == name:
        if is_package:
          # Matching command that expects a subcommand, let's advance to
          # next level searching for a leaf command
          parents.append(command)
          path = os.path.sep.join([path, command])
          can_continue = True
          break
        else:
          execute_command(command, parents, loader, arguments[index+1:])
          # nothing further to do
          return
    if not can_continue:
      # No matching command at current level. Don't look further.
      break

  suggest_recovery_options(command, parents, path, children_names)


if __name__ == '__main__':
  main()
