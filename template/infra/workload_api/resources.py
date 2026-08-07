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

"""Pulumi dynamic resources for Workload API image-build artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pulumi.dynamic import (
    CreateResult,
    DiffResult,
    Resource,
    ResourceProvider,
)

from .client import (
    ReadinessProbe,
    WorkloadClient,
    build_artifact_with_generated_dockerfile,
    build_artifact_with_provided_dockerfile,
    datarobot_api_token,
)

_PROVIDED_TRACKED_KEYS = (
    "source_hash",
    "dockerfile_relative_path",
    "container_name",
    "container_port",
    "environment_vars",
    "routes",
    "readiness_probe",
)

_GENERATED_TRACKED_KEYS = (
    "source_hash",
    "execution_environment_id",
    "execution_environment_version_id",
    "entrypoint",
    "container_name",
    "container_port",
    "environment_vars",
    "routes",
    "readiness_probe",
)


def _diff_changed(
    olds: dict[str, Any], news: dict[str, Any], tracked_keys: tuple[str, ...]
) -> DiffResult:
    if any(olds.get(key) != news.get(key) for key in tracked_keys):
        return DiffResult(changes=True, replaces=["*"])
    return DiffResult(changes=False)


def _delete_artifact(endpoint: str, artifact_id: str) -> None:
    WorkloadClient(endpoint=endpoint, token=datarobot_api_token()).delete_artifact(
        artifact_id
    )


def _readiness_probe_from_props(props: dict[str, Any]) -> ReadinessProbe | None:
    """Reconstruct a `ReadinessProbe` from the plain dict stored in Pulumi state.

    Resource inputs/outputs are serialized to Pulumi's state file, which
    dataclass instances don't survive — so `readiness_probe` travels as a
    plain dict at the Pulumi resource boundary and is only turned back into a
    `ReadinessProbe` here, right before calling into `client.py`.
    """
    raw = props.get("readiness_probe")
    return ReadinessProbe(**raw) if raw else None


class WorkloadImageArtifactProvider(ResourceProvider):
    """Image build using a Dockerfile provided in the uploaded source bundle.

    Any tracked change replaces the artifact (create new + delete old), so no
    update() is implemented.
    """

    def create(self, inputs: dict[str, Any]) -> CreateResult:
        artifact_id = build_artifact_with_provided_dockerfile(
            workload_api_endpoint=inputs["workload_api_endpoint"],
            workload_api_token=datarobot_api_token(),
            artifact_name=inputs["artifact_name"],
            application_path=Path(inputs["application_path"]),
            dockerfile_relative_path=inputs["dockerfile_relative_path"],
            container_name=inputs["container_name"],
            container_port=inputs["container_port"],
            environment_vars=inputs["environment_vars"],
            routes=inputs["routes"],
            build_timeout_s=inputs["build_timeout_s"],
            readiness_probe=_readiness_probe_from_props(inputs),
        )
        outs = {**inputs, "artifact_id": artifact_id}
        return CreateResult(id_=artifact_id, outs=outs)

    def diff(self, _id: str, olds: dict[str, Any], news: dict[str, Any]) -> DiffResult:
        return _diff_changed(olds, news, _PROVIDED_TRACKED_KEYS)

    def delete(self, _id: str, props: dict[str, Any]) -> None:
        _delete_artifact(props["workload_api_endpoint"], _id)


class WorkloadGeneratedImageArtifactProvider(ResourceProvider):
    """Image build using a platform-generated Dockerfile from an execution environment.

    Any tracked change replaces the artifact (create new + delete old), so no
    update() is implemented.
    """

    def create(self, inputs: dict[str, Any]) -> CreateResult:
        artifact_id = build_artifact_with_generated_dockerfile(
            workload_api_endpoint=inputs["workload_api_endpoint"],
            workload_api_token=datarobot_api_token(),
            artifact_name=inputs["artifact_name"],
            application_path=Path(inputs["application_path"]),
            execution_environment_id=inputs["execution_environment_id"],
            execution_environment_version_id=inputs["execution_environment_version_id"],
            entrypoint=inputs["entrypoint"],
            container_name=inputs["container_name"],
            container_port=inputs["container_port"],
            environment_vars=inputs["environment_vars"],
            routes=inputs["routes"],
            build_timeout_s=inputs["build_timeout_s"],
            readiness_probe=_readiness_probe_from_props(inputs),
        )
        outs = {**inputs, "artifact_id": artifact_id}
        return CreateResult(id_=artifact_id, outs=outs)

    def diff(self, _id: str, olds: dict[str, Any], news: dict[str, Any]) -> DiffResult:
        return _diff_changed(olds, news, _GENERATED_TRACKED_KEYS)

    def delete(self, _id: str, props: dict[str, Any]) -> None:
        _delete_artifact(props["workload_api_endpoint"], _id)


class WorkloadImageArtifact(Resource):
    """Workload artifact built from a user-provided Dockerfile in the source bundle."""

    artifact_id: str

    def __init__(
        self,
        name: str,
        *,
        workload_api_endpoint: str,
        artifact_name: str,
        application_path: str,
        dockerfile_relative_path: str,
        container_name: str,
        container_port: int,
        environment_vars: list[dict[str, str]],
        routes: list[dict[str, str]],
        source_hash: str,
        build_timeout_s: int = 6000,
        readiness_probe: dict[str, Any] | None = None,
        opts: Any = None,
    ) -> None:
        super().__init__(
            WorkloadImageArtifactProvider(),
            name,
            {
                "workload_api_endpoint": workload_api_endpoint,
                "artifact_name": artifact_name,
                "application_path": application_path,
                "dockerfile_relative_path": dockerfile_relative_path,
                "container_name": container_name,
                "container_port": container_port,
                "environment_vars": environment_vars,
                "routes": routes,
                "source_hash": source_hash,
                "build_timeout_s": build_timeout_s,
                "readiness_probe": readiness_probe,
                # outputs
                "artifact_id": None,
            },
            opts,
        )


class WorkloadGeneratedImageArtifact(Resource):
    """Workload artifact built via DockerfileGenerated (execution environment + entrypoint)."""

    artifact_id: str

    def __init__(
        self,
        name: str,
        *,
        workload_api_endpoint: str,
        artifact_name: str,
        application_path: str,
        execution_environment_id: Any,
        execution_environment_version_id: Any,
        entrypoint: list[str],
        container_name: str,
        container_port: int,
        environment_vars: list[dict[str, str]],
        routes: list[dict[str, str]],
        source_hash: str,
        build_timeout_s: int = 6000,
        readiness_probe: dict[str, Any] | None = None,
        opts: Any = None,
    ) -> None:
        super().__init__(
            WorkloadGeneratedImageArtifactProvider(),
            name,
            {
                "workload_api_endpoint": workload_api_endpoint,
                "artifact_name": artifact_name,
                "application_path": application_path,
                "execution_environment_id": execution_environment_id,
                "execution_environment_version_id": execution_environment_version_id,
                "entrypoint": entrypoint,
                "container_name": container_name,
                "container_port": container_port,
                "environment_vars": environment_vars,
                "routes": routes,
                "source_hash": source_hash,
                "build_timeout_s": build_timeout_s,
                "readiness_probe": readiness_probe,
                # outputs
                "artifact_id": None,
            },
            opts,
        )
