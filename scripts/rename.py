#!/usr/bin/env python
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
import shutil
import sys


def main(arguments):
  if len(arguments) != 3:
    print('Usage: rename.py <directory> <source> <target>')
    return 1
  top, source, target = arguments
  print('Renaming from', top)
  for path, directory_names, file_names in os.walk(top):
    for directory_name in directory_names:
      directory_path = os.path.join(path, directory_name)
      if source in directory_path:
        new_directory_path = directory_path.replace(source, target)
        print('Renaming', directory_path, new_directory_path)
        shutil.move(directory_path, new_directory_path)
    for file_name in file_names:
      file_path = os.path.join(path, file_name)
      if os.path.abspath(file_path) == os.path.abspath(__file__):
        print('Skipping', file_path)
      elif source in file_name:
        new_file_path = file_path.replace(source, target)
        print('Renaming', file_path, new_file_path)
        shutil.move(file_path, new_file_path)


if __name__ == '__main__':
  main(sys.argv[1:])
