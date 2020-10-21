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
output_dir=$(dirname $current_dir)/orchestrateapi
orchestrate_dir=$(dirname $api_dir)
source $orchestrate_dir/environ.sh

echo "Compiling protos..."

python -m grpc_tools.protoc \
  --proto_path=$api_dir/protos \
  --python_out=$output_dir \
  --grpc_python_out=$output_dir \
  orchestrate.proto

# Fix weird Python import error when attempting to import orchestrate_pb2_grpc
# because it cannot find its sibling orchestrate_pb2.
echo "Fixing Python import statements with relative imports..."
file=$output_dir/orchestrate_pb2_grpc.py
sed -e 's/^import orchestrate_pb2 as orchestrate__pb2$/from . import orchestrate_pb2 as orchestrate__pb2/g' \
  $file > $file.fixed
cp $file.fixed $file
rm -f $file.fixed

echo "Done."
