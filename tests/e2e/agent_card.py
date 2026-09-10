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

The agent card is the contract other agents discover us through, so this module
checks it from both ends:

* the **live card** the running container serves at
  ``{a2a_base_url}/.well-known/agent-card.json``, and
* the **registry row** the platform ingests into ``api/v2/agentCards``, which is
  what makes a remote workflow's ``registry: external_id:`` lookup resolve.

Everything here is written once against :class:`AgentIdentity` rather than twice
against workload/deployment ids -- see that class for why.
"""

from __future__ import annotations

import os
import re
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

# --- Agent card contract ----------------------------------------------------
#
# Mirrors datarobot_genai.dragent.frontends.a2a. Duplicated rather than
# imported on purpose: this asserts the wire contract a deployed container
# produces, and importing the constants from the library that produced them
# would let a renamed URI pass on both sides at once.
INTERNAL_IDENTITY_URI = "urn:datarobot:agent:identity:internal"
EXTERNAL_IDENTITY_URI = "urn:datarobot:agent:identity:external"

# The card is a small static JSON document served by an already-warm container.
AGENT_CARD_CONNECT_TIMEOUT_S = 10
AGENT_CARD_READ_TIMEOUT_S = 30

# --- Agent card registry ----------------------------------------------------

_REGISTRY_PATH = "agentCards/"

# The registry's own client caps a page at 100 (datarobot_genai
# dragent/agent_card_registry.py). We filter by a unique id, so one page is
# always enough -- a second would itself be the bug.
_REGISTRY_PAGE_LIMIT = "100"

# Registration is asynchronous: the platform ingests the card after the
# workload/deployment reports ready, so the row can lag the first successful
# A2A call. Generous against a job that already spends 20-40min in `pulumi up`,
# and short enough to fail before eating the CI budget when the
# ENABLE_GENAI_AGENT_TO_AGENT_SUPPORT feature flag is off on this cluster.
AGENT_CARD_REGISTRY_TIMEOUT_S = int(
    os.environ.get("E2E_AGENT_CARD_REGISTRY_TIMEOUT_S", "300")
)
AGENT_CARD_REGISTRY_POLL_S = 10

# Namespace for the uuid5 fallback -- see `make_external_id`.
_EXTERNAL_ID_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")

# --- workflow.yaml patching -------------------------------------------------

_A2A_KEY_RE = re.compile(r"^(?P<indent>[ ]*)a2a:[ \t]*(?:#.*)?$")
_COMMENT_RE = re.compile(r"^[ \t]*#")

RegistryLookup = Literal["identity", "external"]
_RowVerdict = Literal["match", "pending", "wrong"]


# --- Identity ---------------------------------------------------------------


@dataclass(frozen=True)
class AgentIdentity:
    """A deployed agent's platform identity, plus the three spellings its id takes.

    Exists so every helper below is written once against ``identity`` instead of
    twice against ``workload_id`` / ``deployment_id``. All three spellings are
    derived from ``kind`` by string formatting, so nothing downstream branches
    on the runtime:

    * ``snake_key``   -- what the *live* card's internal-identity extension uses.
    * ``camel_key``   -- what the row, and the card re-serialised inside it, use
      once the platform has ingested them into ``agentCards``.
    * ``query_param`` -- the registry's plural filter key.
    """

    kind: Literal["workload", "deployment"]
    id: str

    @classmethod
    def workload(cls, workload_id: str) -> AgentIdentity:
        return cls(kind="workload", id=workload_id)

    @classmethod
    def deployment(cls, deployment_id: str) -> AgentIdentity:
        return cls(kind="deployment", id=deployment_id)

    @property
    def snake_key(self) -> str:
        return f"{self.kind}_id"

    @property
    def camel_key(self) -> str:
        return f"{self.kind}Id"

    @property
    def query_param(self) -> str:
        return f"{self.kind}Ids"

    def __str__(self) -> str:
        return f"{self.kind} {self.id}"


def make_external_id(*, runtime: str, agent_framework: str) -> str:
    """Return this run's ``a2a.external.id``: unique, and greppable in a registry dump.

    A bare uuid4 would satisfy uniqueness but be untraceable back to this suite
    when a leaked row turns up in the catalog, hence the prefix.

    ``E2E_AGENT_EXTERNAL_ID`` overrides it, which is also the escape hatch when
    ``E2E_PULUMI_STACK`` is pinned and reused across runs: a changing external
    id changes the source archive, which would surface as a diff in the
    workload path's idempotency re-plan.

    If the platform ever validates ``externalIds`` as a real UUID, swap the
    body for ``str(uuid.uuid5(_EXTERNAL_ID_NAMESPACE, ...))``.
    """
    if override := os.environ.get("E2E_AGENT_EXTERNAL_ID", "").strip():
        return override
    return f"af-e2e-{runtime}-{agent_framework}-{uuid.uuid4().hex}"


# --- workflow.yaml ----------------------------------------------------------


def patch_workflow_external_id(*, rendered_dir: Path, external_id: str) -> Path:
    """Insert ``general.front_end.a2a.external.id`` into the rendered workflow.yaml.

    MUST run after ``render_project()`` (which wipes the rendered dir) and
    before the first Pulumi invocation: the infra program reads this file at
    import time for ``base.IS_A2A_SERVER_ENABLED``, and ``task build`` archives
    the whole agent directory into the custom model / workload artifact.

    Edits the text rather than round-tripping through PyYAML. The rendered
    ``workflow.yaml`` *is* the artifact under test, and ``safe_dump`` would drop
    every explanatory comment, reflow block scalars and rewrite quoting -- the
    deployed file would then be a normalised derivative rather than what the
    template renders. Keeping the diff to exactly two lines is also what makes
    a failed run diffable against the template.

    The parse-back below proves the insert landed in the right block; the real
    proof it reached the running container is the live card's ``external``
    extension, asserted by `assert_live_agent_card`. No further local check is
    worth adding here.
    """
    path = rendered_dir / "agent" / "workflow.yaml"
    if not path.exists():
        pytest.fail(f"Rendered workflow.yaml missing: {path}")

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

    # Comment lines are skipped throughout: all five templates ship a commented
    # `# external:` example, so matching them would break every framework.
    matches = [
        (index, match)
        for index, line in enumerate(lines)
        if not _COMMENT_RE.match(line) and (match := _A2A_KEY_RE.match(line))
    ]
    if len(matches) != 1:
        found = [f"  line {i + 1}: {lines[i].rstrip()}" for i, _ in matches]
        pytest.fail(
            f"Expected exactly one uncommented `a2a:` key in {path}, found "
            f"{len(matches)}. The template's A2A block moved or was duplicated; "
            "`patch_workflow_external_id` needs updating.\n" + "\n".join(found)
        )

    index, match = matches[0]
    indent = match.group("indent")
    _fail_on_existing_external(lines=lines, start=index + 1, indent=indent, path=path)

    # Insert at the top of the a2a block rather than the end: the block is
    # followed by column-0 comments, so finding its end is needlessly fiddly.
    newline = "\r\n" if lines[index].endswith("\r\n") else "\n"
    lines[index + 1 : index + 1] = [
        f"{indent}  external:{newline}",
        f'{indent}    id: "{external_id}"{newline}',
    ]
    path.write_text("".join(lines), encoding="utf-8", newline="")

    _verify_external_id(path=path, external_id=external_id)
    fprint(f"Patched a2a.external.id = {external_id} in {path}")
    return path


def _fail_on_existing_external(
    *, lines: list[str], start: int, indent: str, path: Path
) -> None:
    """Fail if the a2a block already declares a real (uncommented) `external:`."""
    external_re = re.compile(rf"^{re.escape(indent)}  external:[ \t]*(?:#.*)?$")
    for line in lines[start:]:
        if not line.strip() or _COMMENT_RE.match(line):
            continue
        # Dedent to `a2a:`'s level or shallower means the block has ended.
        if len(line) - len(line.lstrip(" ")) <= len(indent):
            return
        if external_re.match(line):
            pytest.fail(
                f"{path} already ships a real `external:` block under `a2a:`. "
                "Merge the E2E's external id into it instead of inserting a "
                "second one."
            )


def _verify_external_id(*, path: Path, external_id: str) -> None:
    """Re-parse the patched file and assert the id is where the agent will look.

    This is the same parse `base.check_a2a_server_enabled()` performs at Pulumi
    time, so a failure here would otherwise have surfaced as a Pulumi stack
    trace twenty minutes later.
    """
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        pytest.fail(f"Patched {path} is no longer valid YAML: {e}")

    a2a = (((config or {}).get("general") or {}).get("front_end") or {}).get("a2a")
    if not isinstance(a2a, dict):
        pytest.fail(
            f"Patched {path} has no `general.front_end.a2a` mapping: got {a2a!r}"
        )
    found = (a2a.get("external") or {}).get("id")
    if found != external_id:
        pytest.fail(
            f"Patch did not land where the agent reads it: "
            f"general.front_end.a2a.external.id is {found!r}, expected "
            f"{external_id!r}. Parsed a2a block: {a2a!r}"
        )


# --- Live agent card --------------------------------------------------------


def fetch_agent_card(
    *,
    a2a_base_url: str,
    datarobot_api_token: str,
    read_timeout_s: int = AGENT_CARD_READ_TIMEOUT_S,
) -> dict[str, Any]:
    """GET ``{a2a_base_url}/.well-known/agent-card.json`` and return it as a dict.

    Takes the *A2A base URL* rather than a host, so the workload's
    ``{endpoint}/a2a/`` and the deployment's
    ``{dr_url}/deployments/{id}/directAccess/a2a/`` both work unchanged.

    A2A is on in every framework's default `workflow.yaml` (see
    `base.IS_A2A_SERVER_ENABLED`), so this card should always be there for this
    E2E's own render -- failing to fetch it is a real bug, not a skip case.
    Sent with auth regardless of `enable_unauthenticated_well_known_route`: that
    flag only widens who can fetch the card, an authenticated caller works either
    way, and this keeps the check independent of that toggle.
    """
    url = f"{a2a_base_url.rstrip('/')}/.well-known/agent-card.json"
    fprint(f"Fetching agent card: {url}")
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {datarobot_api_token}"},
        timeout=(AGENT_CARD_CONNECT_TIMEOUT_S, read_timeout_s),
    )
    if response.status_code == 404:
        pytest.fail(
            f"Agent card at {url} returned 404 -- either A2A is not mounted on "
            "this agent or direct access is not enabled for it. The workload "
            "runtime's equivalent check is the control for this."
        )
    response.raise_for_status()

    try:
        card = response.json()
    except ValueError:
        pytest.fail(f"Agent card at {url} was not JSON:\n{response.text[:2000]}")
    if not isinstance(card.get("url"), str) or not card["url"]:
        pytest.fail(f"Agent card at {url} has no usable 'url' field: {card}")
    return card


def assert_live_agent_card(
    *,
    a2a_base_url: str,
    identity: AgentIdentity,
    external_id: str,
    datarobot_api_token: str,
    read_timeout_s: int = AGENT_CARD_READ_TIMEOUT_S,
) -> dict[str, Any]:
    """Fetch the served card, assert both identity extensions, return the card."""
    card = fetch_agent_card(
        a2a_base_url=a2a_base_url,
        datarobot_api_token=datarobot_api_token,
        read_timeout_s=read_timeout_s,
    )

    # Checked before the extension assertions, not after: a redacted card has
    # both identity extensions stripped, so without this the failure would read
    # "external identity extension missing" and point at the workflow.yaml
    # patch -- entirely the wrong place.
    if not card.get("skills"):
        pytest.fail(
            f"Agent card from {a2a_base_url} came back redacted (skills "
            "stripped), which means the Authorization header was not honoured. "
            "Redacted cards also have both identity extensions removed, so any "
            "missing-extension error would be misleading. Card: "
            f"{_trim_card(card)}"
        )

    _assert_identity_extensions(
        card=card,
        identity=identity,
        external_id=external_id,
        id_param_key=identity.snake_key,
        source=f"live agent card at {card.get('url')}",
    )
    fprint(
        f"Agent card advertises {identity} and external id {external_id!r} "
        "as extensions"
    )
    return card


def post_a2a_message(
    *,
    a2a_url: str,
    datarobot_api_token: str,
    user_prompt: str,
    read_timeout_s: int = 300,
) -> str:
    """POST a `message/send` JSON-RPC request to the card's own `url`; return the
    agent's reply text.

    Deliberately calls the card's advertised URL rather than a locally
    reconstructed one -- that URL is server-derived from the agent's own
    `DATAROBOT_ENDPOINT`/workload-id/deployment-id env vars (see
    datarobot_genai's `get_a2a_endpoint_url`), so this is what proves the card
    advertises a URL a real client could actually reach, not just that *some*
    A2A endpoint exists.
    """
    message_id = f"e2e-{uuid.uuid4().hex[:8]}"
    payload: dict[str, Any] = {
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
    }
    response = requests.post(
        a2a_url,
        headers={
            "Authorization": f"Bearer {datarobot_api_token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=(30, read_timeout_s),
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
    if result.get("kind") != "message":
        pytest.fail(f"A2A response has no message result: {data}")

    text_parts = [
        part.get("text", "")
        for part in result.get("parts", [])
        if part.get("kind") == "text" and part.get("text")
    ]
    if not text_parts:
        pytest.fail(f"A2A message result has no text parts: {result}")
    return "".join(text_parts)


def deployment_a2a_base_url(*, deployment_chat_endpoint: str) -> str:
    """`.../deployments/{id}/chat/completions` -> `.../deployments/{id}/directAccess/a2a/`.

    Derived from the exported chat endpoint rather than recomposed from
    `DATAROBOT_ENDPOINT`: the infra builds all deployment URLs from
    `get_datarobot_url()`, which resolves the *external* web-server URL via
    `/clientConfig/` and differs from `DATAROBOT_ENDPOINT` on airgapped
    clusters. The export already has that resolution baked in.
    """
    suffix = "/chat/completions"
    if not deployment_chat_endpoint.endswith(suffix):
        pytest.fail(
            "Expected the deployment chat endpoint to end with "
            f"{suffix!r}, got: {deployment_chat_endpoint!r}"
        )
    return f"{deployment_chat_endpoint[: -len(suffix)]}/directAccess/a2a/"


# --- Extension assertions ---------------------------------------------------


def _extension_params(card: dict[str, Any], *, uri: str) -> dict[str, Any] | None:
    """`params` of the `capabilities.extensions` entry with `uri`, or None."""
    extensions = ((card.get("capabilities") or {}).get("extensions")) or []
    for extension in extensions:
        if isinstance(extension, dict) and extension.get("uri") == uri:
            return extension.get("params") or {}
    return None


def _extension_uris(card: dict[str, Any]) -> list[str]:
    extensions = ((card.get("capabilities") or {}).get("extensions")) or []
    return [e.get("uri", "") for e in extensions if isinstance(e, dict)]


def _assert_identity_extensions(
    *,
    card: dict[str, Any],
    identity: AgentIdentity,
    external_id: str,
    id_param_key: str,
    source: str,
) -> None:
    """Assert the card advertises both identity extensions with the expected ids.

    `id_param_key` is the only thing that differs between the two serialisations
    of the same card: the live card uses snake_case (`workload_id`), while the
    copy embedded in an `agentCards` row is camelCased by the platform
    (`workloadId`). Parameterising it keeps one assertion for both sources.
    """
    internal = _extension_params(card, uri=INTERNAL_IDENTITY_URI)
    if internal is None:
        pytest.fail(
            f"{source} has no {INTERNAL_IDENTITY_URI} extension. Present "
            f"extension URIs: {_extension_uris(card)}"
        )

    if id_param_key not in internal:
        # Report a platform-side rename as the contract change it is, rather
        # than as a bare "missing key" that sends the reader hunting.
        other = (
            identity.camel_key
            if id_param_key == identity.snake_key
            else identity.snake_key
        )
        if other in internal:
            pytest.fail(
                f"Internal identity extension on {source} carries {other!r} "
                f"where {id_param_key!r} was expected. The platform's "
                "serialisation of the card changed; update "
                f"AgentIdentity.snake_key / camel_key. params={internal!r}"
            )
        pytest.fail(
            f"Internal identity extension on {source} has no {id_param_key!r} "
            f"param. params={internal!r}"
        )

    if internal[id_param_key] != identity.id:
        pytest.fail(
            f"Internal identity extension on {source} advertises "
            f"{id_param_key}={internal[id_param_key]!r}, expected {identity.id!r}."
        )

    external = _extension_params(card, uri=EXTERNAL_IDENTITY_URI)
    if external is None:
        pytest.fail(
            f"{source} has no {EXTERNAL_IDENTITY_URI} extension, so "
            "`general.front_end.a2a.external.id` never reached the running "
            f"agent. Present extension URIs: {_extension_uris(card)}"
        )
    if external.get("id") != external_id:
        pytest.fail(
            f"External identity extension on {source} advertises "
            f"id={external.get('id')!r}, expected {external_id!r}."
        )


# --- Registry ---------------------------------------------------------------


def _registry_query(
    *, lookup: RegistryLookup, identity: AgentIdentity, external_id: str
) -> dict[str, str]:
    """Params for one registry lookup.

    Exactly one ID filter per request, never combined: the API rejects
    `deploymentIds` together with `workloadIds` with HTTP 400, and either
    combined with `externalIds` AND-matches to nothing (documented in
    datarobot_genai `dragent/agent_card_registry.py`).
    """
    if lookup == "identity":
        return {identity.query_param: identity.id, "limit": _REGISTRY_PAGE_LIMIT}
    return {"externalIds": external_id, "limit": _REGISTRY_PAGE_LIMIT}


def _get_registry_rows(
    *, client: RESTClientObject, params: dict[str, str]
) -> tuple[list[dict[str, Any]], int]:
    """One page of `agentCards/` rows, plus the reported total.

    A cluster that does not serve the registry at all answers 404/403, which is
    not transient, so `retry` gives up on it immediately. Translated here into
    the same guidance the poll's own deadline message carries -- left to
    propagate it would surface as a bare `ClientError` traceback naming neither
    the cause nor the way out.
    """

    def _fetch() -> dict[str, Any]:
        response = client.get(_REGISTRY_PATH, params=params, timeout=30)
        response.raise_for_status()
        return response.json() or {}

    try:
        body = retry(
            _fetch, max_retries=2, delay_seconds=5, label="agentCards registry query"
        )
    except (ClientError, ServerError, requests.HTTPError) as e:
        status = getattr(e, "status_code", None) or getattr(
            getattr(e, "response", None), "status_code", None
        )
        pytest.fail(
            f"GET {_REGISTRY_PATH} (params={params}) failed with HTTP {status}: "
            f"{e}. If this cluster does not serve the agent card registry -- "
            "ENABLE_GENAI_AGENT_TO_AGENT_SUPPORT off, or the endpoint not "
            "mounted -- set RUN_AGENT_A2A_TESTS=0 to disable the A2A suite."
        )
    rows = [row for row in (body.get("data") or []) if isinstance(row, dict)]
    return rows, int(body.get("totalCount", len(rows)))


def _trim_card(card: dict[str, Any]) -> dict[str, Any]:
    """A card reduced to what a failure message needs."""
    return {
        "name": card.get("name"),
        "url": card.get("url"),
        "skills": len(card.get("skills") or []),
        "extensionUris": _extension_uris(card),
    }


def _trim_row(row: dict[str, Any]) -> dict[str, Any]:
    """A registry row with its embedded card trimmed, so messages stay readable."""
    trimmed = {k: v for k, v in row.items() if k != "agentCard"}
    card = row.get("agentCard")
    trimmed["agentCard"] = _trim_card(card) if isinstance(card, dict) else card
    return trimmed


def _classify_row(
    *, row: dict[str, Any], identity: AgentIdentity, external_id: str
) -> tuple[_RowVerdict, str]:
    """Decide whether a row matches, is still being ingested, or is plain wrong.

    The split is what keeps "not registered yet" (worth waiting for) apart from
    "registered wrong" (never self-heals, so waiting only burns CI time).
    """
    row_identity_id = row.get(identity.camel_key)
    if row_identity_id != identity.id:
        return (
            "wrong",
            f"row is bound to {identity.camel_key}={row_identity_id!r}, "
            f"not {identity.id!r}",
        )

    row_external_id = row.get("externalId")
    if not row_external_id:
        return "pending", "row has no externalId yet"
    if row_external_id != external_id:
        return (
            "wrong",
            f"row carries externalId={row_external_id!r} but this run "
            f"configured a2a.external.id={external_id!r}",
        )

    card = row.get("agentCard")
    if not isinstance(card, dict) or not card:
        return "pending", "row has no agentCard payload yet"

    # Raises with its own message on mismatch; reaching the return means match.
    _assert_identity_extensions(
        card=card,
        identity=identity,
        external_id=external_id,
        id_param_key=identity.camel_key,
        source=f"agentCards registry row {row.get('id')}",
    )
    return "match", "row matches"


def _wait_for_registry_row(
    *,
    client: RESTClientObject,
    identity: AgentIdentity,
    external_id: str,
    lookup: RegistryLookup,
    timeout_s: int,
    poll_s: int,
) -> dict[str, Any]:
    """Poll one registry lookup until a row matches; fail fast on a wrong one."""
    params = _registry_query(lookup=lookup, identity=identity, external_id=external_id)
    started = time.monotonic()
    deadline = started + timeout_s
    polls = 0
    rows_seen = 0
    last_total = 0
    last_reason = "no rows returned"

    while True:
        polls += 1
        rows, last_total = _get_registry_rows(client=client, params=params)
        rows_seen = max(rows_seen, len(rows))
        fprint(
            f"agentCards registry ({lookup}): {len(rows)} row(s) for {identity} "
            f"(poll {polls}, totalCount={last_total})"
        )

        for row in rows:
            verdict, reason = _classify_row(
                row=row, identity=identity, external_id=external_id
            )
            if verdict == "match":
                fprint(f"Agent card registered: row {row.get('id')} ({lookup})")
                return row
            if verdict == "wrong":
                elapsed = int(time.monotonic() - started)
                pytest.fail(
                    f"agentCards registry row for {identity} is registered with "
                    f"the wrong contents: {reason}. This cannot self-heal, so "
                    f"the poll stopped after {elapsed}s. "
                    f"Row: {_trim_row(row)}"
                )
            last_reason = reason

        if time.monotonic() >= deadline:
            break
        time.sleep(poll_s)

    if rows_seen == 0:
        pytest.fail(
            f"No agentCards registry row for {identity} after {timeout_s}s "
            f"(query {params}). The registry answered {polls} time(s) with 0 "
            f"rows (last totalCount={last_total}), so the card was never "
            'registered -- this is "not registered", not "registered wrong". '
            "Registration is asynchronous and requires the "
            "ENABLE_GENAI_AGENT_TO_AGENT_SUPPORT feature flag on this cluster; "
            "set RUN_AGENT_A2A_TESTS=0 to disable the A2A suite if it is off here."
        )
    pytest.fail(
        f"agentCards registry row for {identity} exists but never completed "
        f"after {timeout_s}s ({polls} poll(s), {rows_seen} row(s) seen). "
        f"Last verdict: {last_reason}."
    )


def assert_registered_agent_card(
    *,
    client: RESTClientObject,
    identity: AgentIdentity,
    external_id: str,
    timeout_s: int = AGENT_CARD_REGISTRY_TIMEOUT_S,
    poll_s: int = AGENT_CARD_REGISTRY_POLL_S,
) -> None:
    """Assert the card is discoverable in `agentCards/` by both of its ids.

    Two lookups, because they cover different failure modes: filtering by
    workload/deployment id proves the platform ingested *this* agent's card,
    while filtering by external id proves the catalog-discovery path a remote
    workflow's `registry: external_id:` lookup actually uses.
    """
    for lookup in ("identity", "external"):
        _wait_for_registry_row(
            client=client,
            identity=identity,
            external_id=external_id,
            lookup=lookup,
            timeout_s=timeout_s,
            poll_s=poll_s,
        )


__all__ = [
    "AgentIdentity",
    "EXTERNAL_IDENTITY_URI",
    "INTERNAL_IDENTITY_URI",
    "assert_live_agent_card",
    "assert_registered_agent_card",
    "deployment_a2a_base_url",
    "fetch_agent_card",
    "make_external_id",
    "patch_workflow_external_id",
    "post_a2a_message",
]
