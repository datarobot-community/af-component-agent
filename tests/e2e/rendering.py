# Copyright 2025 DataRobot, Inc.
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

"""
Template rendering helpers for E2E tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from subprocess_utils import _run_live
from task_runner import _task_cmd


@dataclass(frozen=True)
class RenderedProject:
    agent_framework: str
    repo_root: Path
    rendered_dir: Path
    infra_dir: Path
    agent_dir: Path  # The agent subdirectory within rendered_dir


def validate_rendered_project(project: RenderedProject, *, expected_framework: str) -> None:
    if project.agent_framework != expected_framework:
        raise AssertionError(
            "RenderedProject framework mismatch: "
            f"expected={expected_framework!r} got={project.agent_framework!r}"
        )
    if not project.rendered_dir.exists():
        raise AssertionError(f"Rendered dir missing: {project.rendered_dir}")
    if not project.infra_dir.exists():
        raise AssertionError(f"Rendered infra dir missing: {project.infra_dir}")
    if not project.agent_dir.exists():
        raise AssertionError(f"Rendered agent dir missing: {project.agent_dir}")


def render_project(*, repo_root: Path, agent_framework: str) -> RenderedProject:
    rendered_dir = repo_root / ".rendered" / f"agent_{agent_framework}"
    infra_dir = rendered_dir / "infra"
    agent_dir = rendered_dir / "agent"

    _run_live(_task_cmd("render-template-e2e", f"AGENT={agent_framework}"), cwd=repo_root)

    if not infra_dir.exists():
        raise AssertionError(f"Rendered infra dir missing: {infra_dir}")
    if not agent_dir.exists():
        raise AssertionError(f"Rendered agent dir missing: {agent_dir}")

    return RenderedProject(
        agent_framework=agent_framework,
        repo_root=repo_root,
        rendered_dir=rendered_dir,
        infra_dir=infra_dir,
        agent_dir=agent_dir,
    )


