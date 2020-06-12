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

from setuptools import find_packages
from setuptools import setup


DESCRIPTION = """Orchestrate API - Orchestration solution backed."""

with open('requirements.txt', 'r') as input_file:
  requirements = input_file.readlines()

setup(
    name='orchestrateapi',
    description=DESCRIPTION,
    long_description=DESCRIPTION,
    author='Luis Artola',
    author_email='luisartola@google.com',
    url='https://github.com/GoogleCloudPlatform/solutions-cloud-orchestrate',
    packages=find_packages(),
    entry_points=dict(
        console_scripts=[
            'orchestrateapi = orchestrateapi.main:main',
        ],
    ),
    install_requires=requirements,
    include_package_data=False,
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
        'License :: Other/Proprietary License',
        'Natural Language :: English',
        'Topic :: System :: Systems Administration',
        ],
)
