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
Pytest configuration for E2E tests.

This module provides session-scoped fixtures that run once before all E2E tests,
including pre-rendering all selected agent templates to catch issues early.
"""

from __future__ import annotations

import os

import pytest

from .helpers import _is_truthy, fprint, render_all_selected_frameworks, selected_frameworks


@pytest.fixture(scope="session", autouse=True)
def prerender_all_agents():
    """
    Session-scoped fixture that pre-renders all selected agent templates
    before any E2E tests run.

    This catches template rendering issues early, before spending time on
    build/deploy cycles. If any template fails to render, all E2E tests
    will fail immediately.
    """
    # Only run when E2E is enabled
    if not _is_truthy(os.environ.get("RUN_E2E")):
        yield
        return

    frameworks = selected_frameworks()
    if not frameworks:
        yield
        return

    fprint("\n")
    fprint("=" * 70)
    fprint("E2E PRE-FLIGHT: Rendering all selected agent templates...")
    fprint("=" * 70)

    # This will raise if any template fails to render
    rendered_projects = render_all_selected_frameworks()

    fprint(f"Pre-flight complete: {len(rendered_projects)} templates ready")
    fprint("=" * 70)
    fprint("\n")

    yield rendered_projects

