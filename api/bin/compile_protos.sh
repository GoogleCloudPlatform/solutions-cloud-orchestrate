#!/bin/bash
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

current_dir=$(dirname $(realpath ${BASH_SOURCE[0]}))
api_dir=$(dirname $current_dir)
orchestrate_dir=$(dirname $api_dir)
source $orchestrate_dir/environ.sh

echo "Compiling protos..."

python -m grpc.tools.protoc \
    --include_imports \
    --include_source_info \
    --proto_path=$api_dir/protos \
    --python_out=$api_dir \
    --grpc_python_out=$api_dir \
    --descriptor_set_out=$api_dir/api_descriptor.pb \
    orchestrate.proto

echo "Done."
