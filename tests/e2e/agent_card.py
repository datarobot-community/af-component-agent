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
A2A agent-card assertions shared by both E2E runtimes.

Checks the card from both ends: the **live card** the container serves at
``{a2a_base_url}/.well-known/agent-card.json``, and the **registry row** the
platform ingests into ``api/v2/agentCards``, which is what makes a remote
workflow's ``registry: external_id:`` lookup resolve.
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pytest
import requests
import yaml
from datarobot.errors import ClientError, ServerError
from datarobot.rest import RESTClientObject

from ._process import fprint, retry

# Mirrors datarobot_genai.dragent.frontends.a2a. Duplicated rather than
# imported: this asserts the wire contract a deployed container produces, and
# importing from the library that produced it would let a renamed URI pass on
# both sides at once.
INTERNAL_IDENTITY_URI = "urn:datarobot:agent:identity:internal"
EXTERNAL_IDENTITY_URI = "urn:datarobot:agent:identity:external"

# (connect, read) for the card GET -- a small static document from a warm container.
AGENT_CARD_TIMEOUT_S = (10, 30)

_REGISTRY_PATH = "agentCards/"

# Registration is asynchronous: the platform ingests the card after the
# workload/deployment reports ready, so the row lags the first A2A call.
AGENT_CARD_REGISTRY_TIMEOUT_S = int(
    os.environ.get("E2E_AGENT_CARD_REGISTRY_TIMEOUT_S", "300")
)
AGENT_CARD_REGISTRY_POLL_S = 10


@dataclass(frozen=True)
class AgentIdentity:
    """Which platform object hosts the agent, so helpers take one arg not two."""

    kind: Literal["workload", "deployment"]
    id: str

    @property
    def camel_key(self) -> str:
        """The registry row's own id field: `workloadId` / `deploymentId`."""
        return f"{self.kind}Id"

    @property
    def query_param(self) -> str:
        """The registry's plural filter: `workloadIds` / `deploymentIds`."""
        return f"{self.kind}Ids"

    def __str__(self) -> str:
        return f"{self.kind} {self.id}"


def make_external_id(*, runtime: str, agent_framework: str) -> str:
    """This run's `a2a.external.id` -- unique, and greppable in a registry dump.

    `E2E_AGENT_EXTERNAL_ID` overrides it, for reruns against a pinned stack.
    """
    if override := os.environ.get("E2E_AGENT_EXTERNAL_ID", "").strip():
        return override
    return f"af-e2e-{runtime}-{agent_framework}-{uuid.uuid4().hex}"


def patch_workflow_external_id(*, rendered_dir: Path, external_id: str) -> Path:
    """Set `general.front_end.a2a.external.id` in the rendered workflow.yaml.

    MUST run after `render_project()` (which wipes the rendered dir) and before
    the first Pulumi invocation: the infra program reads this file at import
    time, and `task build` archives the agent directory into the artifact.
    """
    path = rendered_dir / "agent" / "workflow.yaml"
    if not path.exists():
        pytest.fail(f"Rendered workflow.yaml missing: {path}")

    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    a2a = ((config.get("general") or {}).get("front_end") or {}).get("a2a")
    if not isinstance(a2a, dict):
        pytest.fail(
            f"No `general.front_end.a2a` mapping in {path}: got {a2a!r}. The "
            "template's A2A block moved or was removed."
        )
    a2a["external"] = {**(a2a.get("external") or {}), "id": external_id}
    path.write_text(
        yaml.safe_dump(config, sort_keys=False, width=1000, allow_unicode=True),
        encoding="utf-8",
    )
    fprint(f"Patched a2a.external.id = {external_id} in {path}")
    return path


# --- Live agent card --------------------------------------------------------


def assert_live_agent_card(
    *, a2a_base_url: str, identity: AgentIdentity, external_id: str, token: str
) -> dict[str, Any]:
    """GET the served card, assert both identity extensions, return the card.

    Always sent with auth, regardless of `enable_unauthenticated_well_known_route`:
    that flag only widens who may fetch the card, and an anonymous caller gets a
    redacted copy with the identity extensions stripped.
    """
    url = f"{a2a_base_url.rstrip('/')}/.well-known/agent-card.json"
    fprint(f"Fetching agent card: {url}")
    response = requests.get(
        url, headers={"Authorization": f"Bearer {token}"}, timeout=AGENT_CARD_TIMEOUT_S
    )
    if response.status_code == 404:
        pytest.fail(
            f"Agent card at {url} returned 404 -- either A2A is not mounted on "
            "this agent or direct access is not enabled for it."
        )
    response.raise_for_status()

    try:
        card = response.json()
    except ValueError:
        pytest.fail(f"Agent card at {url} was not JSON:\n{response.text[:2000]}")
    if not isinstance(card.get("url"), str) or not card["url"]:
        pytest.fail(f"Agent card at {url} has no usable 'url' field: {card}")

    # Before the extension checks, not after: a redacted card has them stripped,
    # so otherwise the failure reads "extension missing" and blames the patch.
    if not card.get("skills"):
        pytest.fail(
            f"Agent card from {url} came back redacted (skills stripped): the "
            f"Authorization header was not honoured. Card: {_trim_card(card)}"
        )

    _assert_identity_extensions(
        card=card, identity=identity, external_id=external_id, source=f"card at {url}"
    )
    fprint(f"Agent card advertises {identity} and external id {external_id!r}")
    return card


def post_a2a_message(*, a2a_url: str, token: str, user_prompt: str) -> str:
    """POST a `message/send` JSON-RPC request; return the agent's reply text.

    Calls the card's *self-advertised* URL rather than a locally reconstructed
    one -- that URL is server-derived from the agent's own environment (see
    datarobot_genai's `get_a2a_endpoint_url`), so this proves the card
    advertises an entrypoint a real client could reach.
    """
    message_id = f"e2e-{uuid.uuid4().hex[:8]}"
    response = requests.post(
        a2a_url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "jsonrpc": "2.0",
            "id": message_id,
            "method": "message/send",
            "params": {
                "message": {
                    "kind": "message",
                    "messageId": message_id,
                    "role": "user",
                    "parts": [{"kind": "text", "text": user_prompt}],
                },
            },
        },
        timeout=(30, 300),
    )
    response.raise_for_status()

    try:
        data = response.json()
    except ValueError:
        pytest.fail(
            f"A2A response from {a2a_url} was not JSON:\n{response.text[:2000]}"
        )
    if "error" in data:
        pytest.fail(f"A2A message/send to {a2a_url} returned an error: {data['error']}")

    result = data.get("result") or {}
    text_parts = [
        part.get("text", "")
        for part in result.get("parts", [])
        if part.get("kind") == "text" and part.get("text")
    ]
    if not text_parts:
        pytest.fail(f"A2A result has no text parts: {data}")
    return "".join(text_parts)


# --- Extension assertions ---------------------------------------------------


def _extension_params(card: dict[str, Any], *, uri: str) -> dict[str, Any] | None:
    extensions = ((card.get("capabilities") or {}).get("extensions")) or []
    for extension in extensions:
        if isinstance(extension, dict) and extension.get("uri") == uri:
            return extension.get("params") or {}
    return None


def _extension_uris(card: dict[str, Any]) -> list[str]:
    extensions = ((card.get("capabilities") or {}).get("extensions")) or []
    return [e.get("uri", "") for e in extensions if isinstance(e, dict)]


def _internal_runtime_id(params: dict[str, Any]) -> str | None:
    """The runtime id from an internal-identity extension, in either spelling.

    The live card serves snake_case; the copy embedded in an `agentCards` row is
    camelCased by the platform. Accepting both keeps one assertion for both.
    """
    for key in ("workload_id", "workloadId", "deployment_id", "deploymentId"):
        if params.get(key):
            return str(params[key])
    return None


def _assert_identity_extensions(
    *, card: dict[str, Any], identity: AgentIdentity, external_id: str, source: str
) -> None:
    """Assert the card advertises both identity extensions with the expected ids."""
    internal = _extension_params(card, uri=INTERNAL_IDENTITY_URI)
    if internal is None:
        pytest.fail(
            f"{source} has no {INTERNAL_IDENTITY_URI} extension. "
            f"Present URIs: {_extension_uris(card)}"
        )
    found = _internal_runtime_id(internal)
    if found != identity.id:
        pytest.fail(
            f"Internal identity extension on {source} advertises {found!r}, "
            f"expected {identity.id!r}. params={internal!r}"
        )

    external = _extension_params(card, uri=EXTERNAL_IDENTITY_URI)
    if external is None:
        pytest.fail(
            f"{source} has no {EXTERNAL_IDENTITY_URI} extension, so "
            "`general.front_end.a2a.external.id` never reached the running "
            f"agent. Present URIs: {_extension_uris(card)}"
        )
    if external.get("id") != external_id:
        pytest.fail(
            f"External identity extension on {source} advertises "
            f"id={external.get('id')!r}, expected {external_id!r}."
        )


# --- Registry ---------------------------------------------------------------


def _trim_card(card: dict[str, Any]) -> dict[str, Any]:
    """A card reduced to what a failure message needs."""
    return {
        "name": card.get("name"),
        "url": card.get("url"),
        "skills": len(card.get("skills") or []),
        "extensionUris": _extension_uris(card),
    }


def _trim_row(row: dict[str, Any]) -> dict[str, Any]:
    card = row.get("agentCard")
    trimmed = {k: v for k, v in row.items() if k != "agentCard"}
    trimmed["agentCard"] = _trim_card(card) if isinstance(card, dict) else card
    return trimmed


def _row_matches(
    *, row: dict[str, Any], identity: AgentIdentity, external_id: str
) -> bool:
    """Is this row fully ingested and ours? Partial rows are normal mid-ingest."""
    card = row.get("agentCard")
    return (
        row.get(identity.camel_key) == identity.id
        and row.get("externalId") == external_id
        and isinstance(card, dict)
        and bool(card.get("url"))
    )


def _get_registry_rows(
    *, client: RESTClientObject, params: dict[str, str]
) -> list[dict[str, Any]]:
    """One page of `agentCards/` rows.

    A cluster that does not serve the registry answers 404/403, which is not
    transient, so `retry` gives up at once -- translated here rather than left
    to surface as a bare `ClientError` naming neither cause nor way out.
    """
    try:
        body = retry(
            lambda: client.get(_REGISTRY_PATH, params=params, timeout=30).json() or {},
            max_retries=2,
            delay_seconds=5,
            label="agentCards registry query",
        )
    except (ClientError, ServerError) as e:
        pytest.fail(
            f"GET {_REGISTRY_PATH} (params={params}) failed with HTTP "
            f"{e.status_code}: {e}. If this cluster does not serve the agent "
            "card registry -- ENABLE_GENAI_AGENT_TO_AGENT_SUPPORT off, or the "
            "endpoint not mounted -- set RUN_AGENT_A2A_TESTS=0."
        )
    return [row for row in (body.get("data") or []) if isinstance(row, dict)]


def assert_registered_agent_card(
    *,
    client: RESTClientObject,
    identity: AgentIdentity,
    external_id: str,
    timeout_s: int = AGENT_CARD_REGISTRY_TIMEOUT_S,
    poll_s: int = AGENT_CARD_REGISTRY_POLL_S,
) -> None:
    """Assert the card is discoverable in `agentCards/` by both of its ids.

    Two lookups covering different failure modes: by workload/deployment id
    proves the platform ingested this agent's card, by external id proves the
    catalog-discovery path a remote `registry: external_id:` lookup uses. Never
    combined -- the API 400s on two internal filters, and AND-matches to nothing
    when either is mixed with `externalIds`.
    """
    for params in (
        {identity.query_param: identity.id},
        {"externalIds": external_id},
    ):
        deadline = time.monotonic() + timeout_s
        seen: list[dict[str, Any]] = []
        while True:
            rows = _get_registry_rows(client=client, params=params)
            fprint(f"agentCards {params}: {len(rows)} row(s) for {identity}")
            for row in rows:
                if _row_matches(row=row, identity=identity, external_id=external_id):
                    _assert_identity_extensions(
                        card=row["agentCard"],
                        identity=identity,
                        external_id=external_id,
                        source=f"agentCards row {row.get('id')}",
                    )
                    fprint(f"Agent card registered: row {row.get('id')}")
                    break
            else:
                seen = rows or seen
                if time.monotonic() < deadline:
                    time.sleep(poll_s)
                    continue
                pytest.fail(
                    f"No matching agentCards row for {identity} / "
                    f"{external_id!r} after {timeout_s}s (query {params}). "
                    "Registration is asynchronous and needs the "
                    "ENABLE_GENAI_AGENT_TO_AGENT_SUPPORT feature flag; set "
                    "RUN_AGENT_A2A_TESTS=0 if it is off on this cluster. "
                    f"Last rows: {[_trim_row(r) for r in seen] or 'none'}"
                )
            break


def assert_a2a_end_to_end(
    *,
    client: RESTClientObject,
    identity: AgentIdentity,
    external_id: str,
    a2a_base_url: str,
    token: str,
    user_prompt: str,
) -> None:
    """Card -> `message/send` to the card's own URL -> registry row.

    `retry` on the HTTP steps absorbs the 502/503/504 a cold route answers while
    a replica spins; a 404 propagates. The registry check runs last so the
    `message/send` round trip counts against its async ingest lag for free.
    """
    card = retry(
        lambda: assert_live_agent_card(
            a2a_base_url=a2a_base_url,
            identity=identity,
            external_id=external_id,
            token=token,
        ),
        max_retries=2,
        delay_seconds=30,
        label="Agent card fetch",
    )
    reply = retry(
        lambda: post_a2a_message(
            a2a_url=card["url"], token=token, user_prompt=user_prompt
        ),
        max_retries=2,
        delay_seconds=30,
        label="A2A message/send",
    )
    fprint(f"A2A message/send returned {len(reply)} chars")
    assert_registered_agent_card(
        client=client, identity=identity, external_id=external_id
    )
