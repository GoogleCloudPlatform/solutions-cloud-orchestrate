#!/usr/bin/env python3
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

import os
import sys


def replace(file_path, source, target):
  """Replace occurrences of `source` with `target` on given `file_path`.

  Replace text and their title and upper case variants, e.g. hello, Hello, and
  HELLO. Skip this script to preserve the original text we are using to replace.

  Args:
    file_path: File path.
    source: Text to search and replace.
    target: Replacement text.
  """
  print('Replacing', file_path)
  lines = []
  with open(file_path, 'r') as input_file:
    for line in input_file:
      line = line.replace(source, target)
      line = line.replace(source.title(), target.title())
      line = line.replace(source.upper(), target.upper())
      lines.append(line)
  with open(file_path, 'w') as output_file:
    content = ''.join(lines)
    output_file.write(content)


def main(arguments):
  if len(arguments) != 1:
    print('Usage: set_project.py <project>')
    return 1
  path = os.path.abspath(__file__)
  directory = os.path.dirname(path)
  top = os.path.dirname(directory)
  source = 'PLACEHOLDER_ORCHESTRATE_PROJECT'
  target = arguments[0]
  print('Replacing from', top)
  file_names = [
      'api/Dockerfile',
      'api/api_config.yaml',
      'api/deployment.yaml',
      'project/required.roles.txt',
      'environ.sh',
  ]
  for file_name in file_names:
    file_path = os.path.join(top, file_name)
    file_extension = os.path.splitext(file_name)[1]
    if os.path.abspath(file_path) == os.path.abspath(__file__) or \
        file_extension in ['.pb']:
      print('Skipping', file_path)
    else:
      replace(file_path, source, target)


if __name__ == '__main__':
  main(sys.argv[1:])
