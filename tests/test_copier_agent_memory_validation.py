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

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COPIER_YML = REPO_ROOT / "copier.yml"
VALIDATE_SCRIPT = (
    REPO_ROOT / "template/infra/dev_tools/validate_agent_memory_config.py"
)
POST_COPY_SCRIPT = (
    REPO_ROOT / "template/infra/copier/post_copy_validate_agent_memory.sh"
)


def _load_validate_module():
    spec = importlib.util.spec_from_file_location(
        "validate_agent_memory_config", VALIDATE_SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_copier_runs_memory_validation_when_datarobot_memory_service_selected():
    content = COPIER_YML.read_text(encoding="utf-8")

    assert "_tasks:" in content
    assert "post_copy_validate_agent_memory.sh" in content
    assert "use_agent_memory == 'datarobot_memory_service'" in content


def test_template_includes_copier_post_copy_validation_script():
    content = POST_COPY_SCRIPT.read_text(encoding="utf-8")

    assert "validate_agent_memory_config" in content
    assert "set -euo pipefail" in content


def test_validate_agent_memory_config_rejects_conflicting_mem0_key():
    module = _load_validate_module()

    errors = module.validate_agent_memory_config(
        use_agent_memory="datarobot_memory_service",
        mem0_api_key="secret",
    )
    assert len(errors) == 1
    assert "MEM0_API_KEY" in errors[0]
