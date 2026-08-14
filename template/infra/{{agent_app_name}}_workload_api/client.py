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

"""Workload API wire models, HTTP client, and image-build orchestration.

The HTTP client covers the platform-built-image path only: the pre-built-image
path needs no client at all, since the agent's ``workload.py`` hands its payload straight
to ``pulumi_datarobot.Artifact``. The wire models here are shared by both paths.
Source upload for image builds lives in ``artifact_code.py`` (stand-in for
native Pulumi ``ArtifactCode`` support).
"""

from __future__ import annotations

import dataclasses
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

from .artifact_code import upload_source

BUILD_SUCCESS = "COMPLETED"
BUILD_FAILURES = frozenset({"FAILED", "CANCELLED"})
WORKLOAD_ARTIFACT_TYPE = "service"
DEFAULT_REQUEST_TIMEOUT_S = 60
DATAROBOT_API_TOKEN_ENV = "DATAROBOT_API_TOKEN"
# Tolerated consecutive poll failures (e.g. transient 502s) while a build runs.
MAX_TRANSIENT_POLL_FAILURES = 3


def datarobot_api_token() -> str:
    """Read the API token from the environment (never from Pulumi state).

    Dynamic resource inputs/outputs are serialized into the Pulumi state file,
    so the token must be sourced here inside provider operations rather than
    passed as a resource property.
    """
    token = os.getenv(DATAROBOT_API_TOKEN_ENV, "").strip()
    if not token:
        raise RuntimeError(
            f"{DATAROBOT_API_TOKEN_ENV} must be set in the environment for workload "
            "provisioning (including `pulumi destroy`); it is intentionally not "
            "stored in Pulumi state."
        )
    return token


def _to_camel_case(snake_str: str) -> str:
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def _to_wire(value: Any) -> Any:
    """Serialize spec dataclasses to the camelCase wire format, dropping None fields.

    Dicts are already in wire format and pass through untouched: container env
    vars are built that way by the agent's ``workload.py`` so they reach the platform
    verbatim.
    """
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            _to_camel_case(f.name): _to_wire(getattr(value, f.name))
            for f in dataclasses.fields(value)
            if getattr(value, f.name) is not None
        }
    if isinstance(value, list):
        return [_to_wire(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_wire(item) for key, item in value.items()}
    return value


@dataclass
class ReadinessProbe:
    """Container readiness probe for the workload's HTTP health endpoint.

    Agents built on ``datarobot_genai.dragent`` expose a ``/health`` endpoint,
    and the platform should not route traffic to a replica until it responds.
    The defaults give a replica ``10 + 6 * 10`` = 70 seconds to come up.
    """

    path: str = "/health"
    port: int = 8080
    initial_delay_seconds: int = 10
    period_seconds: int = 10
    timeout_seconds: int = 5
    failure_threshold: int = 6
    scheme: str = "HTTP"

    def to_wire(self) -> dict[str, Any]:
        """camelCase form, for payloads assembled outside this module.

        Nested probes are serialized by ``_to_wire`` along with their container;
        this is for the pre-built-image payload, which the agent's ``workload.py`` builds
        as a plain dict.
        """
        return dict(_to_wire(self))


@dataclass
class DockerfileGenerated:
    execution_environment_id: str
    execution_environment_version_id: str
    entrypoint: list[str]
    source: str = "generated"


@dataclass
class CodeRefDatarobot:
    catalog_id: str
    catalog_version_id: str


@dataclass
class CodeRef:
    datarobot: CodeRefDatarobot


@dataclass
class ImageBuildConfig:
    dockerfile: DockerfileGenerated
    code_ref: CodeRef | None = None


@dataclass
class Container:
    name: str
    primary: bool
    port: int
    image_build_config: ImageBuildConfig
    environment_vars: list[dict[str, str]] = field(default_factory=list)
    routes: list[dict[str, str]] = field(default_factory=list)
    readiness_probe: ReadinessProbe | None = None


@dataclass
class ContainerGroup:
    containers: list[Container]


@dataclass
class ArtifactSpecFromImageBuildConfig:
    container_groups: list[ContainerGroup]


@dataclass
class WorkloadArtifactSpecFromImageBuildConfig:
    name: str
    spec: ArtifactSpecFromImageBuildConfig
    type: str = WORKLOAD_ARTIFACT_TYPE

    def to_payload(self) -> dict:
        return _to_wire(self)


class WorkloadClient:
    def __init__(
        self,
        endpoint: str,
        token: str,
        timeout_s: int = DEFAULT_REQUEST_TIMEOUT_S,
    ) -> None:
        self._base = endpoint.rstrip("/")
        self._timeout_s = timeout_s
        self._session = requests.Session()
        self._session.headers.update(
            {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )

    def _url(self, path: str) -> str:
        return f"{self._base}{path}"

    @staticmethod
    def _raise_for_status(resp: requests.Response) -> None:
        """raise_for_status that surfaces the response body in the error.
        The Workload API returns actionable validation detail (e.g. which field
        was rejected) in the 4xx body; the default requests message drops it.
        """
        if resp.status_code >= 400:
            body = resp.text[:2000]
            raise requests.HTTPError(
                f"{resp.status_code} {resp.reason} for {resp.request.method} {resp.url}\n{body}",
                response=resp,
            )

    def create_artifact(self, spec: WorkloadArtifactSpecFromImageBuildConfig) -> str:
        payload = spec.to_payload()
        resp = self._session.post(
            self._url("/artifacts/"), json=payload, timeout=self._timeout_s
        )
        self._raise_for_status(resp)
        return resp.json()["id"]

    def delete_artifact(self, artifact_id: str) -> None:
        resp = self._session.delete(
            self._url(f"/artifacts/{artifact_id}"), timeout=self._timeout_s
        )
        # 404: already gone. 409: the platform retains artifacts that back a
        # live workload's revision history and refuses to delete them until the
        # workload itself is deleted — treat as released so replacements (e.g.
        # source-change redeploys) don't fail; `pulumi destroy` deletes the
        # workload first, so full teardown still deletes artifacts for real.
        if resp.status_code in (404, 409):
            return
        self._raise_for_status(resp)

    def trigger_build(self, artifact_id: str) -> list[str]:
        resp = self._session.post(
            self._url(f"/artifacts/{artifact_id}/builds"), timeout=self._timeout_s
        )
        self._raise_for_status(resp)
        data = resp.json()
        return data.get("buildIds") or data.get("build_ids") or []

    def get_build(self, artifact_id: str, build_id: str) -> dict:
        resp = self._session.get(
            self._url(f"/artifacts/{artifact_id}/builds/{build_id}"),
            timeout=self._timeout_s,
        )
        resp.raise_for_status()
        return resp.json()

    def get_build_logs(self, artifact_id: str, build_id: str) -> str:
        resp = self._session.get(
            self._url(f"/artifacts/{artifact_id}/builds/{build_id}/logs"),
            timeout=self._timeout_s,
        )
        resp.raise_for_status()
        return resp.text

    def wait_for_build(
        self,
        artifact_id: str,
        build_id: str,
        *,
        timeout_s: int,
        interval_s: int,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.monotonic,
    ) -> str:
        deadline = now() + timeout_s
        last_status = "UNKNOWN"
        transient_failures = 0
        while True:
            try:
                last_status = str(
                    self.get_build(artifact_id, build_id).get("status", "UNKNOWN")
                )
                transient_failures = 0
            except requests.RequestException:
                transient_failures += 1
                if transient_failures >= MAX_TRANSIENT_POLL_FAILURES:
                    raise
            else:
                if last_status == BUILD_SUCCESS:
                    return last_status
                if last_status in BUILD_FAILURES:
                    logs = ""
                    try:
                        logs = self.get_build_logs(artifact_id, build_id)
                    except requests.RequestException:
                        pass
                    raise RuntimeError(
                        f"build {build_id} {last_status}\n{logs[-4000:]}"
                    )
            if now() >= deadline:
                raise TimeoutError(
                    f"build {build_id} not done after {timeout_s}s (last={last_status})"
                )
            sleep(interval_s)


def _create_and_build_artifact(
    client: WorkloadClient,
    spec: WorkloadArtifactSpecFromImageBuildConfig,
    build_timeout_s: int,
    build_interval_s: int = 10,
) -> str:
    artifact_id = client.create_artifact(spec)
    build_ids = client.trigger_build(artifact_id)
    if not build_ids:
        raise RuntimeError("no build id returned from trigger_build")
    client.wait_for_build(
        artifact_id,
        build_ids[0],
        timeout_s=build_timeout_s,
        interval_s=build_interval_s,
    )
    return artifact_id


def _image_build_spec(
    *,
    artifact_name: str,
    dockerfile: DockerfileGenerated,
    container_name: str,
    container_port: int,
    environment_vars: list[dict[str, str]],
    routes: list[dict[str, str]],
    code_ref: CodeRef,
    readiness_probe: ReadinessProbe | None = None,
) -> WorkloadArtifactSpecFromImageBuildConfig:
    container = Container(
        name=container_name,
        primary=True,
        port=container_port,
        image_build_config=ImageBuildConfig(dockerfile=dockerfile, code_ref=code_ref),
        environment_vars=environment_vars,
        routes=routes,
        readiness_probe=readiness_probe,
    )
    return WorkloadArtifactSpecFromImageBuildConfig(
        name=artifact_name,
        spec=ArtifactSpecFromImageBuildConfig(
            container_groups=[ContainerGroup(containers=[container])]
        ),
    )


def build_artifact_with_generated_dockerfile(
    *,
    workload_api_endpoint: str,
    workload_api_token: str,
    artifact_name: str,
    application_path: Path,
    execution_environment_id: str,
    execution_environment_version_id: str,
    entrypoint: list[str],
    container_name: str,
    container_port: int,
    environment_vars: list[dict[str, str]],
    routes: list[dict[str, str]],
    build_timeout_s: int,
    readiness_probe: ReadinessProbe | None = None,
) -> str:
    catalog_id, catalog_version_id = upload_source(
        endpoint=workload_api_endpoint,
        token=workload_api_token,
        application_path=application_path,
    )
    artifact_spec = _image_build_spec(
        artifact_name=artifact_name,
        dockerfile=DockerfileGenerated(
            execution_environment_id=execution_environment_id,
            execution_environment_version_id=execution_environment_version_id,
            entrypoint=entrypoint,
        ),
        container_name=container_name,
        container_port=container_port,
        environment_vars=environment_vars,
        routes=routes,
        code_ref=CodeRef(
            datarobot=CodeRefDatarobot(
                catalog_id=catalog_id, catalog_version_id=catalog_version_id
            )
        ),
        readiness_probe=readiness_probe,
    )
    client = WorkloadClient(endpoint=workload_api_endpoint, token=workload_api_token)
    return _create_and_build_artifact(client, artifact_spec, build_timeout_s)
