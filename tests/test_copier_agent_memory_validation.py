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

from pathlib import Path

COPIER_YML = Path(__file__).resolve().parent.parent / "copier.yml"


def test_copier_rejects_mem0_api_key_when_datarobot_memory_service_selected():
    content = COPIER_YML.read_text(encoding="utf-8")

    assert "use_agent_memory == 'datarobot_memory_service'" in content
    assert "MEM0_API_KEY" in content
    assert "datarobot_memory_service" in content
    assert "post_copy_validate_agent_memory.sh" not in content
    assert "agent-agent.yml" not in content
    assert "{{ _copier_conf.answers_file }}" in content
