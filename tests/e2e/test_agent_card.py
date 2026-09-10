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
Offline tests for `agent_card`'s pure logic.

Not marked `e2e`: these need no platform, and they cover the two pieces that
could otherwise fail silently -- `patch_workflow_external_id`, which can no-op
if a template moves, and the extension assertions, which are worthless if they
pass on a card that doesn't actually carry the ids.

Fixtures come from the checked-in `workflow_*.yaml.j2` templates rather than
from inline copies. Those files contain no Jinja and are `{% include %}`d
verbatim, so they are byte-for-byte what `render_project()` produces -- an
inline copy would drift the moment someone edits a template.
"""

from __future__ import annotations

from pathlib import Path
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
    _classify_row,
    _get_registry_rows,
    assert_live_agent_card,
    deployment_a2a_base_url,
    make_external_id,
    patch_workflow_external_id,
)

_TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2]
    / "template"
    / "{{agent_app_name}}"
    / "workflow_templates"
)
_FRAMEWORKS = ("base", "crewai", "langgraph", "llamaindex", "nat")

_EXTERNAL_ID = "af-e2e-test-0123456789abcdef"
_WORKLOAD = AgentIdentity.workload("6aa1793ef35363612b153173")
_DEPLOYMENT = AgentIdentity.deployment("68f0000000000000000000aa")


def _rendered_dir(tmp_path: Path, framework: str) -> Path:
    """A stand-in for `.rendered/agent_<fw>` holding that framework's workflow.yaml."""
    source = _TEMPLATE_DIR / f"workflow_{framework}.yaml.j2"
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "workflow.yaml").write_text(
        source.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return tmp_path


def _card(
    *,
    id_param_key: str = "workload_id",
    id_value: str = _WORKLOAD.id,
    external_id: str | None = _EXTERNAL_ID,
    skills: bool = True,
) -> dict:
    extensions: list[dict] = [
        {
            "uri": INTERNAL_IDENTITY_URI,
            "required": True,
            "params": {id_param_key: id_value},
        }
    ]
    if external_id is not None:
        extensions.append(
            {
                "uri": EXTERNAL_IDENTITY_URI,
                "required": False,
                "params": {"id": external_id},
            }
        )
    return {
        "name": "Agent 2",
        "url": "https://example.invalid/a2a/",
        "capabilities": {"extensions": extensions, "streaming": True},
        "skills": [{"id": "call", "name": "Agent 2"}] if skills else [],
    }


# --- patch_workflow_external_id ---------------------------------------------


@pytest.mark.parametrize("framework", _FRAMEWORKS)
def test_patch_lands_where_the_agent_reads_it(tmp_path: Path, framework: str) -> None:
    rendered = _rendered_dir(tmp_path, framework)
    path = patch_workflow_external_id(rendered_dir=rendered, external_id=_EXTERNAL_ID)

    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    a2a = config["general"]["front_end"]["a2a"]
    assert a2a["external"]["id"] == _EXTERNAL_ID
    # The skill list must be untouched -- the commented `external:` example in
    # the templates used to sit inside it, so a regression there would silently
    # nest our patch in the wrong mapping.
    assert a2a["skills"][0]["id"]
    assert "external" not in a2a["skills"][0]


@pytest.mark.parametrize("framework", _FRAMEWORKS)
def test_patch_adds_exactly_two_lines(tmp_path: Path, framework: str) -> None:
    """The rendered file is the deployed artifact; the diff must stay reviewable."""
    source = (_TEMPLATE_DIR / f"workflow_{framework}.yaml.j2").read_text(
        encoding="utf-8"
    )
    rendered = _rendered_dir(tmp_path, framework)
    patched = patch_workflow_external_id(
        rendered_dir=rendered, external_id=_EXTERNAL_ID
    ).read_text(encoding="utf-8")

    before = source.splitlines()
    after = patched.splitlines()
    assert len(after) - len(before) == 2
    added = [line for line in after if line not in before]
    assert added == ["      external:", f'        id: "{_EXTERNAL_ID}"']


def test_patch_refuses_a_second_run(tmp_path: Path) -> None:
    rendered = _rendered_dir(tmp_path, "base")
    patch_workflow_external_id(rendered_dir=rendered, external_id=_EXTERNAL_ID)
    with pytest.raises(
        pytest.fail.Exception, match="already ships a real `external:` block"
    ):
        patch_workflow_external_id(rendered_dir=rendered, external_id="second")


def test_patch_fails_loudly_when_the_a2a_block_is_gone(tmp_path: Path) -> None:
    rendered = _rendered_dir(tmp_path, "base")
    path = rendered / "agent" / "workflow.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("    a2a:", "    not_a2a:"),
        encoding="utf-8",
    )
    with pytest.raises(
        pytest.fail.Exception, match="Expected exactly one uncommented `a2a:` key"
    ):
        patch_workflow_external_id(rendered_dir=rendered, external_id=_EXTERNAL_ID)


def test_commented_external_example_is_not_mistaken_for_a_real_block(
    tmp_path: Path,
) -> None:
    """Every template ships a commented `# external:`; it must not block the patch."""
    rendered = _rendered_dir(tmp_path, "langgraph")
    assert "# external:" in (rendered / "agent" / "workflow.yaml").read_text()
    patch_workflow_external_id(rendered_dir=rendered, external_id=_EXTERNAL_ID)


# --- Identity extension assertions ------------------------------------------


def test_live_card_snake_case_passes() -> None:
    _assert_identity_extensions(
        card=_card(id_param_key=_WORKLOAD.snake_key),
        identity=_WORKLOAD,
        external_id=_EXTERNAL_ID,
        id_param_key=_WORKLOAD.snake_key,
        source="live card",
    )


def test_registry_card_camel_case_passes() -> None:
    _assert_identity_extensions(
        card=_card(id_param_key=_WORKLOAD.camel_key),
        identity=_WORKLOAD,
        external_id=_EXTERNAL_ID,
        id_param_key=_WORKLOAD.camel_key,
        source="registry row",
    )


def test_deployment_identity_uses_its_own_spellings() -> None:
    assert (_DEPLOYMENT.snake_key, _DEPLOYMENT.camel_key, _DEPLOYMENT.query_param) == (
        "deployment_id",
        "deploymentId",
        "deploymentIds",
    )
    _assert_identity_extensions(
        card=_card(id_param_key="deployment_id", id_value=_DEPLOYMENT.id),
        identity=_DEPLOYMENT,
        external_id=_EXTERNAL_ID,
        id_param_key=_DEPLOYMENT.snake_key,
        source="live card",
    )


def test_wrong_external_id_fails() -> None:
    """The assertion must not be vacuous -- this is the whole point of the check."""
    with pytest.raises(pytest.fail.Exception, match="External identity extension"):
        _assert_identity_extensions(
            card=_card(external_id="someone-elses-agent"),
            identity=_WORKLOAD,
            external_id=_EXTERNAL_ID,
            id_param_key=_WORKLOAD.snake_key,
            source="live card",
        )


def test_missing_external_extension_names_the_config_key() -> None:
    with pytest.raises(
        pytest.fail.Exception, match=r"general\.front_end\.a2a\.external\.id"
    ):
        _assert_identity_extensions(
            card=_card(external_id=None),
            identity=_WORKLOAD,
            external_id=_EXTERNAL_ID,
            id_param_key=_WORKLOAD.snake_key,
            source="live card",
        )


def test_wrong_internal_id_fails() -> None:
    with pytest.raises(pytest.fail.Exception, match="Internal identity extension"):
        _assert_identity_extensions(
            card=_card(id_value="0000000000000000000000ff"),
            identity=_WORKLOAD,
            external_id=_EXTERNAL_ID,
            id_param_key=_WORKLOAD.snake_key,
            source="live card",
        )


def test_swapped_spelling_is_reported_as_a_contract_change() -> None:
    """A platform-side rename must read as a rename, not as 'extension missing'."""
    with pytest.raises(
        pytest.fail.Exception, match="serialisation of the card changed"
    ):
        _assert_identity_extensions(
            card=_card(id_param_key="workload_id"),
            identity=_WORKLOAD,
            external_id=_EXTERNAL_ID,
            id_param_key=_WORKLOAD.camel_key,
            source="registry row",
        )


def test_redacted_card_is_reported_as_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stripped card must blame auth, not the workflow.yaml patch."""
    from . import agent_card

    monkeypatch.setattr(
        agent_card,
        "fetch_agent_card",
        lambda **_: {"url": "https://example.invalid/a2a/", "skills": []},
    )
    with pytest.raises(pytest.fail.Exception, match="came back redacted"):
        assert_live_agent_card(
            a2a_base_url="https://example.invalid/a2a/",
            identity=_WORKLOAD,
            external_id=_EXTERNAL_ID,
            datarobot_api_token="token",
        )


# --- Registry row classification --------------------------------------------


def _row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": "6aa1799fb2e4ff053064ce4b",
        "workloadId": _WORKLOAD.id,
        "deploymentId": None,
        "externalId": _EXTERNAL_ID,
        "agentCard": _card(id_param_key=_WORKLOAD.camel_key),
    }
    row.update(overrides)
    return row


def test_complete_row_matches() -> None:
    verdict, _ = _classify_row(row=_row(), identity=_WORKLOAD, external_id=_EXTERNAL_ID)
    assert verdict == "match"


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"externalId": None}, id="external-id-not-ingested-yet"),
        pytest.param({"agentCard": None}, id="card-payload-not-ingested-yet"),
        pytest.param({"agentCard": {}}, id="empty-card-payload"),
    ],
)
def test_partial_rows_are_pending(overrides: dict) -> None:
    """Mid-ingest states are worth waiting out."""
    verdict, _ = _classify_row(
        row=_row(**overrides), identity=_WORKLOAD, external_id=_EXTERNAL_ID
    )
    assert verdict == "pending"


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"workloadId": "0000000000000000000000ff"}, id="another-workload"),
        pytest.param({"externalId": "someone-elses-agent"}, id="another-external-id"),
    ],
)
def test_mismatched_rows_are_wrong_not_pending(overrides: dict) -> None:
    """These never self-heal, so waiting out the deadline would only burn CI."""
    verdict, _ = _classify_row(
        row=_row(**overrides), identity=_WORKLOAD, external_id=_EXTERNAL_ID
    )
    assert verdict == "wrong"


# --- URL derivation ---------------------------------------------------------


def test_deployment_a2a_base_url_preserves_the_resolved_host() -> None:
    """Derived from the export, so an airgapped cluster's own host survives."""
    assert (
        deployment_a2a_base_url(
            deployment_chat_endpoint="https://airgap.example.com/api/v2/deployments/abc123/chat/completions"
        )
        == "https://airgap.example.com/api/v2/deployments/abc123/directAccess/a2a/"
    )


def test_deployment_a2a_base_url_rejects_an_unexpected_export() -> None:
    with pytest.raises(pytest.fail.Exception, match="chat/completions"):
        deployment_a2a_base_url(
            deployment_chat_endpoint="https://example.invalid/api/v2/deployments/abc123"
        )


# --- External id ------------------------------------------------------------


def test_external_ids_are_unique_and_traceable() -> None:
    first = make_external_id(runtime="workload-api", agent_framework="base")
    second = make_external_id(runtime="workload-api", agent_framework="base")
    assert first != second
    assert first.startswith("af-e2e-workload-api-base-")


def test_external_id_override_is_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("E2E_AGENT_EXTERNAL_ID", "pinned-id")
    assert (
        make_external_id(runtime="workload-api", agent_framework="base") == "pinned-id"
    )


# --- Registry transport errors ----------------------------------------------


class _RaisingClient:
    """A RESTClientObject stand-in whose GET always fails with `error`."""

    def __init__(self, error: BaseException) -> None:
        self._error = error

    def get(self, *_args: Any, **_kwargs: Any) -> Any:
        raise self._error


def test_registry_404_names_the_gate_instead_of_raising_clienterror() -> None:
    """A cluster that doesn't serve the registry must say so, not throw a traceback.

    404/403 is not transient, so `retry` gives up on it at once; without the
    translation the driver would die on a bare `ClientError` naming neither the
    cause nor the way out.
    """
    client = _RaisingClient(ClientError("not found", 404))
    with pytest.raises(pytest.fail.Exception, match="RUN_AGENT_A2A_TESTS=0"):
        _get_registry_rows(
            client=cast(RESTClientObject, client),
            params={"workloadIds": _WORKLOAD.id},
        )


def test_registry_403_is_translated_too() -> None:
    client = _RaisingClient(ClientError("forbidden", 403))
    with pytest.raises(pytest.fail.Exception, match="HTTP 403"):
        _get_registry_rows(
            client=cast(RESTClientObject, client),
            params={"externalIds": _EXTERNAL_ID},
        )
