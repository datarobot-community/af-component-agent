#!/usr/bin/env bash
# Copyright 2026 DataRobot, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Copier _tasks hook: run immediately after agent component copy/update when
# use_agent_memory=datarobot_memory_service. Wired from af-component-agent/copier.yml.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VALIDATE="$ROOT/infra/dev_tools/validate_agent_memory_config.py"

if [ ! -f "$VALIDATE" ]; then
  exit 0
fi

cd "$ROOT/infra"
exec python3 -m dev_tools.validate_agent_memory_config
