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
"""Configure DataRobot Memory Space settings not yet exposed by pulumi-datarobot."""

from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

import pulumi
import pulumi_command as command

from . import project_dir

if TYPE_CHECKING:
    import pulumi_datarobot as datarobot

_CONFIGURE_SCRIPT = project_dir / "dev_tools" / "configure_memory_space_llm.py"


def memory_space_llm_model_name(llm_default_model: str) -> str:
    """Return the LLM Gateway catalog name for MemorySpace ``llm_model_name``."""
    return llm_default_model.removeprefix("datarobot/")


def configure_memory_space_llm(
    resource_name: str,
    memory_space: datarobot.MemorySpace,
    llm_model_name: str,
) -> command.local.Command:
    """Patch ``llm_model_name`` on a MemorySpace after Pulumi creates it."""
    configure_command = memory_space.id.apply(
        lambda space_id: _build_configure_command(space_id, llm_model_name)
    )
    return command.local.Command(
        resource_name,
        create=configure_command,
        update=configure_command,
        triggers=[llm_model_name],
        opts=pulumi.ResourceOptions(depends_on=[memory_space]),
    )


def _build_configure_command(space_id: str, llm_model_name: str) -> str:
    return (
        f"uv run --directory {shlex.quote(str(project_dir))} "
        f"python {shlex.quote(str(_CONFIGURE_SCRIPT))} "
        f"{shlex.quote(space_id)} {shlex.quote(llm_model_name)}"
    )
