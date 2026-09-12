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

"""
Offline tests for `agent_card`'s pure logic -- no platform needed, so not
marked `e2e`. They cover what an e2e run cannot catch on its own: a patcher
that silently no-ops after a template moves, and assertions that would pass on
a card carrying nothing.

Fixtures come from the checked-in `workflow_*.yaml.j2` templates, which contain
no Jinja and are `{% include %}`d verbatim -- an inline copy would drift.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import yaml
from datarobot.errors import ClientError
from datarobot.rest import RESTClientObject

from .agent_card import (
    EXTERNAL_IDENTITY_URI,
    INTERNAL_IDENTITY_URI,
    AgentIdentity,
    _assert_identity_extensions,
    _get_registry_rows,
    _row_matches,
    assert_live_agent_card,
    make_external_id,
    patch_workflow_external_id,
)

_TEMPLATES = (
    Path(__file__).resolve().parents[2]
    / "template"
    / "{{agent_app_name}}"
    / "workflow_templates"
)
_FRAMEWORKS = ("base", "crewai", "langgraph", "llamaindex", "nat")

_EXTERNAL_ID = "af-e2e-test-0123456789abcdef"
_WORKLOAD = AgentIdentity("workload", "6aa1793ef35363612b153173")


def _rendered_dir(tmp_path: Path, framework: str) -> Path:
    """A stand-in for `.rendered/agent_<fw>` holding that framework's workflow.yaml."""
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "workflow.yaml").write_text(
        (_TEMPLATES / f"workflow_{framework}.yaml.j2").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return tmp_path


def _card(
    *,
    id_key: str = "workload_id",
    id_value: str = _WORKLOAD.id,
    external_id: str | None = _EXTERNAL_ID,
    skills: bool = True,
) -> dict[str, Any]:
    extensions: list[dict[str, Any]] = [
        {"uri": INTERNAL_IDENTITY_URI, "params": {id_key: id_value}}
    ]
    if external_id is not None:
        extensions.append({"uri": EXTERNAL_IDENTITY_URI, "params": {"id": external_id}})
    return {
        "name": "Agent 2",
        "url": "https://example.invalid/a2a/",
        "capabilities": {"extensions": extensions},
        "skills": [{"id": "call"}] if skills else [],
    }


# --- patch_workflow_external_id ---------------------------------------------


@pytest.mark.parametrize("framework", _FRAMEWORKS)
def test_patch_changes_only_the_external_id(tmp_path: Path, framework: str) -> None:
    """The patched config must equal the original plus `external.id`, nothing else.

    This is what makes the YAML round-trip safe: it would catch `safe_dump`
    mangling a scalar (e.g. `mode: "off"`, a YAML 1.1 boolean) anywhere in the
    real template content.
    """
    source = (_TEMPLATES / f"workflow_{framework}.yaml.j2").read_text(encoding="utf-8")
    path = patch_workflow_external_id(
        rendered_dir=_rendered_dir(tmp_path, framework), external_id=_EXTERNAL_ID
    )

    expected = yaml.safe_load(source)
    expected["general"]["front_end"]["a2a"]["external"] = {"id": _EXTERNAL_ID}
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == expected


def test_patch_fails_loudly_when_the_a2a_block_is_gone(tmp_path: Path) -> None:
    rendered = _rendered_dir(tmp_path, "base")
    path = rendered / "agent" / "workflow.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("    a2a:", "    not_a2a:"),
        encoding="utf-8",
    )
    with pytest.raises(pytest.fail.Exception, match="No `general.front_end.a2a`"):
        patch_workflow_external_id(rendered_dir=rendered, external_id=_EXTERNAL_ID)


# --- Identity extension assertions ------------------------------------------


@pytest.mark.parametrize(
    "id_key", ["workload_id", "workloadId"], ids=["live-snake", "registry-camel"]
)
def test_both_serialisations_pass(id_key: str) -> None:
    """The live card is snake_case; the registry-embedded copy is camelCased."""
    _assert_identity_extensions(
        card=_card(id_key=id_key),
        identity=_WORKLOAD,
        external_id=_EXTERNAL_ID,
        source="card",
    )


@pytest.mark.parametrize(
    ("card", "match"),
    [
        pytest.param(
            _card(id_value="0000000000000000000000ff"),
            "Internal identity extension",
            id="wrong-internal-id",
        ),
        pytest.param(
            _card(external_id="someone-elses-agent"),
            "External identity extension",
            id="wrong-external-id",
        ),
        pytest.param(
            _card(external_id=None),
            r"general\.front_end\.a2a\.external\.id",
            id="missing-external-extension",
        ),
    ],
)
def test_assertions_are_not_vacuous(card: dict[str, Any], match: str) -> None:
    """Without these the live-card check could pass on a card carrying nothing."""
    with pytest.raises(pytest.fail.Exception, match=match):
        _assert_identity_extensions(
            card=card, identity=_WORKLOAD, external_id=_EXTERNAL_ID, source="card"
        )


def test_redacted_card_blames_auth_not_the_patch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from . import agent_card

    redacted = SimpleNamespace(
        status_code=200,
        raise_for_status=lambda: None,
        json=lambda: {"url": "https://example.invalid/a2a/", "skills": []},
    )
    monkeypatch.setattr(agent_card.requests, "get", lambda *a, **k: redacted)
    with pytest.raises(pytest.fail.Exception, match="came back redacted"):
        assert_live_agent_card(
            a2a_base_url="https://example.invalid/a2a/",
            identity=_WORKLOAD,
            external_id=_EXTERNAL_ID,
            token="token",
        )


# --- Registry ---------------------------------------------------------------


def _row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": "6aa1799fb2e4ff053064ce4b",
        "workloadId": _WORKLOAD.id,
        "externalId": _EXTERNAL_ID,
        "agentCard": _card(id_key="workloadId"),
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        pytest.param({}, True, id="complete"),
        pytest.param({"workloadId": None}, False, id="identity-not-ingested-yet"),
        pytest.param({"externalId": None}, False, id="external-id-not-ingested-yet"),
        pytest.param({"agentCard": None}, False, id="card-not-ingested-yet"),
        pytest.param({"externalId": "stale"}, False, id="another-runs-row"),
    ],
)
def test_row_matches(overrides: dict[str, Any], expected: bool) -> None:
    """Partial rows are normal mid-ingest and must keep the poll waiting."""
    assert (
        _row_matches(
            row=_row(**overrides), identity=_WORKLOAD, external_id=_EXTERNAL_ID
        )
        is expected
    )


class _RaisingClient:
    def __init__(self, error: BaseException) -> None:
        self._error = error

    def get(self, *_args: Any, **_kwargs: Any) -> Any:
        raise self._error


@pytest.mark.parametrize("status", [404, 403])
def test_registry_unavailable_names_the_gate(status: int) -> None:
    """A cluster without the registry must say so, not raise a bare ClientError."""
    client = _RaisingClient(ClientError("nope", status))
    with pytest.raises(pytest.fail.Exception, match="RUN_AGENT_A2A_TESTS=0"):
        _get_registry_rows(
            client=cast(RESTClientObject, client),
            params={"workloadIds": _WORKLOAD.id},
        )


# --- Misc -------------------------------------------------------------------


def test_external_ids_are_unique_and_traceable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("E2E_AGENT_EXTERNAL_ID", raising=False)
    first = make_external_id(runtime="workload-api", agent_framework="base")
    assert first != make_external_id(runtime="workload-api", agent_framework="base")
    assert first.startswith("af-e2e-workload-api-base-")

    monkeypatch.setenv("E2E_AGENT_EXTERNAL_ID", "pinned")
    assert make_external_id(runtime="workload-api", agent_framework="base") == "pinned"
