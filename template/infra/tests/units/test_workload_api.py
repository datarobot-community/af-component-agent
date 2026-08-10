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
"""Tests for the workload_api package: Workload API HTTP client + Pulumi plumbing.

Not templated (workload_api has no Jinja-conditional content -- see its module
docstrings), so this test file isn't templated either.
"""

import sys
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from workload_api.artifact_code import (
    source_archive,
    source_hash,
    upload_source,
)
from workload_api.client import (
    DATAROBOT_API_TOKEN_ENV,
    ContainerImageUri,
    ReadinessProbe,
    WorkloadClient,
    _to_wire,
    build_artifact_from_image_uri,
    build_artifact_with_generated_dockerfile,
    datarobot_api_token,
)
from workload_api.resources import (
    WorkloadGeneratedImageArtifactProvider,
    _readiness_probe_from_props,
    _GENERATED_TRACKED_KEYS,
)


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text="", method="GET", url=""):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text
        self.reason = "error" if status_code >= 400 else "OK"
        self.request = MagicMock(method=method)
        self.url = url

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)


class TestToWire:
    def test_drops_none_fields(self):
        probe = ReadinessProbe()
        wire = _to_wire(probe)
        assert wire["path"] == "/health"
        assert "port" in wire

    def test_camel_cases_field_names(self):
        probe = ReadinessProbe(initial_delay_seconds=15)
        wire = _to_wire(probe)
        assert wire["initialDelaySeconds"] == 15

    def test_omits_none_optional_field(self):
        container = ContainerImageUri(
            name="agent", primary=True, port=8080, image_uri="img:latest"
        )
        wire = _to_wire(container)
        assert "entrypoints" not in wire
        assert "readinessProbe" not in wire

    def test_includes_readiness_probe_when_set(self):
        container = ContainerImageUri(
            name="agent",
            primary=True,
            port=8080,
            image_uri="img:latest",
            readiness_probe=ReadinessProbe(port=9090),
        )
        wire = _to_wire(container)
        assert wire["readinessProbe"]["port"] == 9090
        assert wire["readinessProbe"]["path"] == "/health"

    def test_passes_through_lists_and_dicts(self):
        assert _to_wire([{"a": 1}, "x"]) == [{"a": 1}, "x"]
        assert _to_wire({"a": 1}) == {"a": 1}
        assert _to_wire("plain") == "plain"


class TestBuildArtifactFromImageUri:
    def test_basic_payload_shape(self):
        spec = build_artifact_from_image_uri(
            artifact_name="agent-artifact",
            container_name="agent",
            container_port=8080,
            image_uri="registry.example.com/agent:latest",
        )
        payload = spec.to_payload()
        container = payload["spec"]["containerGroups"][0]["containers"][0]
        assert container["imageUri"] == "registry.example.com/agent:latest"
        assert container["port"] == 8080
        assert "entrypoints" not in container
        assert "readinessProbe" not in container

    def test_with_readiness_probe(self):
        spec = build_artifact_from_image_uri(
            artifact_name="agent-artifact",
            container_name="agent",
            container_port=8080,
            image_uri="registry.example.com/agent:latest",
            readiness_probe=ReadinessProbe(port=8080),
        )
        payload = spec.to_payload()
        container = payload["spec"]["containerGroups"][0]["containers"][0]
        assert container["readinessProbe"]["port"] == 8080

    def test_entrypoints_passed_through(self):
        spec = build_artifact_from_image_uri(
            artifact_name="agent-artifact",
            container_name="agent",
            container_port=8080,
            image_uri="registry.example.com/agent:latest",
            entrypoints=["python", "main.py"],
        )
        payload = spec.to_payload()
        container = payload["spec"]["containerGroups"][0]["containers"][0]
        assert container["entrypoints"] == ["python", "main.py"]


class TestBuildArtifactWithDockerfile:
    def test_generated_dockerfile_builds_and_creates(self, monkeypatch):
        monkeypatch.setattr(
            "workload_api.client.upload_source",
            MagicMock(return_value=("cat-2", "ver-2")),
        )
        monkeypatch.setattr(
            "workload_api.client._create_and_build_artifact",
            MagicMock(return_value="artifact-2"),
        )
        artifact_id = build_artifact_with_generated_dockerfile(
            workload_api_endpoint="https://wapi.example.com",
            workload_api_token="tok",
            artifact_name="agent-artifact",
            application_path=Path("/tmp/agent-app"),
            execution_environment_id="ee-1",
            execution_environment_version_id="ee-v1",
            entrypoint=["sh", "run_server.sh"],
            container_name="agent",
            container_port=8080,
            environment_vars=[],
            routes=[],
            build_timeout_s=100,
        )
        assert artifact_id == "artifact-2"
        from workload_api.client import _create_and_build_artifact

        spec = _create_and_build_artifact.call_args[0][1]
        payload = spec.to_payload()
        container = payload["spec"]["containerGroups"][0]["containers"][0]
        assert container["imageBuildConfig"]["dockerfile"]["source"] == "generated"
        assert container["imageBuildConfig"]["dockerfile"]["entrypoint"] == [
            "sh",
            "run_server.sh",
        ]
        assert container["imageBuildConfig"]["codeRef"]["datarobot"] == {
            "catalogId": "cat-2",
            "catalogVersionId": "ver-2",
        }


class TestArtifactCode:
    def test_archive_is_deterministic(self, tmp_path):
        (tmp_path / "b.py").write_text("b")
        (tmp_path / "a.py").write_text("a")
        assert source_archive(tmp_path) == source_archive(tmp_path)

    def test_hash_changes_when_content_changes(self, tmp_path):
        f1 = tmp_path / "a.py"
        f1.write_text("print(1)")
        original = source_hash(tmp_path)
        f1.write_text("print(2)")
        assert source_hash(tmp_path) != original

    def test_wapiignore_excludes_files(self, tmp_path):
        (tmp_path / ".wapiignore").write_text("tests/\n.env\n")
        (tmp_path / "workflow.yaml").write_text("general: {}\n")
        (tmp_path / ".env").write_text("SECRET=1\n")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_x.py").write_text("")

        archive = source_archive(tmp_path)
        with zipfile.ZipFile(BytesIO(archive)) as zf:
            names = set(zf.namelist())
        assert "workflow.yaml" in names
        assert ".env" not in names
        assert "tests/test_x.py" not in names

    def test_upload_source_sync_response(self, monkeypatch, tmp_path):
        (tmp_path / "main.py").write_text("print('hi')\n")
        mock_post = MagicMock(
            return_value=_FakeResponse(
                status_code=201,
                json_data={
                    "catalogId": "cat-1",
                    "catalogVersionId": "ver-1",
                },
            )
        )
        monkeypatch.setattr("workload_api.artifact_code.requests.post", mock_post)

        catalog_id, catalog_version_id = upload_source(
            endpoint="https://wapi.example.com",
            token="tok",
            application_path=tmp_path,
        )
        assert catalog_id == "cat-1"
        assert catalog_version_id == "ver-1"
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["files"]["file"][0] == "source.zip"

    def test_upload_source_async_polls_to_completion(self, monkeypatch, tmp_path):
        (tmp_path / "main.py").write_text("print('hi')\n")
        monkeypatch.setattr(
            "workload_api.artifact_code.requests.post",
            MagicMock(
                return_value=_FakeResponse(
                    status_code=202,
                    json_data={
                        "catalogId": "cat-1",
                        "catalogVersionId": "ver-1",
                        "statusId": "status-1",
                    },
                )
            ),
        )
        monkeypatch.setattr(
            "workload_api.artifact_code.requests.get",
            MagicMock(return_value=_FakeResponse(status_code=303)),
        )

        catalog_id, catalog_version_id = upload_source(
            endpoint="https://wapi.example.com",
            token="tok",
            application_path=tmp_path,
            sleep=lambda _s: None,
            now=lambda: 0,
        )
        assert catalog_id == "cat-1"
        assert catalog_version_id == "ver-1"

    def test_upload_source_raises_on_failed_status(self, monkeypatch, tmp_path):
        (tmp_path / "main.py").write_text("print('hi')\n")
        monkeypatch.setattr(
            "workload_api.artifact_code.requests.post",
            MagicMock(
                return_value=_FakeResponse(
                    status_code=202,
                    json_data={
                        "catalogId": "cat-1",
                        "catalogVersionId": "ver-1",
                        "statusId": "status-1",
                    },
                )
            ),
        )
        monkeypatch.setattr(
            "workload_api.artifact_code.requests.get",
            MagicMock(
                return_value=_FakeResponse(
                    status_code=200,
                    json_data={"status": "ERROR", "message": "bad archive"},
                )
            ),
        )

        with pytest.raises(RuntimeError, match="bad archive"):
            upload_source(
                endpoint="https://wapi.example.com",
                token="tok",
                application_path=tmp_path,
                sleep=lambda _s: None,
                now=lambda: 0,
            )

    def test_upload_source_times_out(self, monkeypatch, tmp_path):
        (tmp_path / "main.py").write_text("print('hi')\n")
        monkeypatch.setattr(
            "workload_api.artifact_code.requests.post",
            MagicMock(
                return_value=_FakeResponse(
                    status_code=202,
                    json_data={
                        "catalogId": "cat-1",
                        "catalogVersionId": "ver-1",
                        "statusId": "status-1",
                    },
                )
            ),
        )
        monkeypatch.setattr(
            "workload_api.artifact_code.requests.get",
            MagicMock(
                return_value=_FakeResponse(
                    status_code=200, json_data={"status": "INITIALIZED"}
                )
            ),
        )
        times = iter([0, 0, 700])

        with pytest.raises(TimeoutError):
            upload_source(
                endpoint="https://wapi.example.com",
                token="tok",
                application_path=tmp_path,
                poll_timeout_s=600,
                sleep=lambda _s: None,
                now=lambda: next(times),
            )


class TestWorkloadClient:
    def _client(self):
        return WorkloadClient(endpoint="https://wapi.example.com", token="tok")

    def test_create_artifact_posts_payload(self):
        client = self._client()
        client._session = MagicMock()
        client._session.post.return_value = _FakeResponse(
            status_code=200, json_data={"id": "artifact-1"}
        )
        spec = build_artifact_from_image_uri(
            artifact_name="a", container_name="c", container_port=8080, image_uri="img"
        )
        assert client.create_artifact(spec) == "artifact-1"

    def test_delete_artifact_swallows_404(self):
        client = self._client()
        client._session = MagicMock()
        client._session.delete.return_value = _FakeResponse(status_code=404)
        client.delete_artifact("artifact-1")  # must not raise

    def test_delete_artifact_swallows_409_retained_by_live_workload(self):
        client = self._client()
        client._session = MagicMock()
        client._session.delete.return_value = _FakeResponse(status_code=409)
        client.delete_artifact("artifact-1")  # must not raise

    def test_delete_artifact_raises_on_other_errors(self):
        client = self._client()
        client._session = MagicMock()
        client._session.delete.return_value = _FakeResponse(
            status_code=500,
            text="internal error",
            method="DELETE",
            url="https://x/artifacts/1",
        )
        with pytest.raises(requests.HTTPError, match="internal error"):
            client.delete_artifact("artifact-1")

    def test_trigger_build_reads_build_ids(self):
        client = self._client()
        client._session = MagicMock()
        client._session.post.return_value = _FakeResponse(
            status_code=200, json_data={"buildIds": ["build-1"]}
        )
        assert client.trigger_build("artifact-1") == ["build-1"]

    def test_wait_for_build_succeeds(self):
        client = self._client()
        client.get_build = MagicMock(return_value={"status": "COMPLETED"})
        result = client.wait_for_build(
            "artifact-1",
            "build-1",
            timeout_s=100,
            interval_s=1,
            sleep=lambda s: None,
            now=lambda: 0,
        )
        assert result == "COMPLETED"

    def test_wait_for_build_raises_on_failure_with_logs(self):
        client = self._client()
        client.get_build = MagicMock(return_value={"status": "FAILED"})
        client.get_build_logs = MagicMock(return_value="boom trace")
        with pytest.raises(RuntimeError, match="FAILED"):
            client.wait_for_build(
                "artifact-1",
                "build-1",
                timeout_s=100,
                interval_s=1,
                sleep=lambda s: None,
                now=lambda: 0,
            )

    def test_wait_for_build_times_out(self):
        client = self._client()
        client.get_build = MagicMock(return_value={"status": "RUNNING"})
        times = iter([0, 0, 200])
        with pytest.raises(TimeoutError):
            client.wait_for_build(
                "artifact-1",
                "build-1",
                timeout_s=100,
                interval_s=1,
                sleep=lambda s: None,
                now=lambda: next(times),
            )

    def test_wait_for_build_tolerates_transient_failures(self):
        client = self._client()
        call_count = {"n": 0}

        def flaky_get_build(artifact_id, build_id):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise requests.ConnectionError("transient")
            return {"status": "COMPLETED"}

        client.get_build = flaky_get_build
        result = client.wait_for_build(
            "artifact-1",
            "build-1",
            timeout_s=100,
            interval_s=1,
            sleep=lambda s: None,
            now=lambda: 0,
        )
        assert result == "COMPLETED"

    def test_wait_for_build_raises_after_max_transient_failures(self):
        client = self._client()
        client.get_build = MagicMock(side_effect=requests.ConnectionError("down"))
        with pytest.raises(requests.ConnectionError):
            client.wait_for_build(
                "artifact-1",
                "build-1",
                timeout_s=100,
                interval_s=1,
                sleep=lambda s: None,
                now=lambda: 0,
            )


class TestWorkloadArtifactProviders:
    def test_readiness_probe_from_props_reconstructs_dataclass(self):
        probe = _readiness_probe_from_props(
            {"readiness_probe": {"path": "/health", "port": 9090}}
        )
        assert isinstance(probe, ReadinessProbe)
        assert probe.port == 9090

    def test_readiness_probe_from_props_none_when_absent(self):
        assert _readiness_probe_from_props({}) is None

    def test_generated_tracked_keys_include_readiness_probe(self):
        assert "readiness_probe" in _GENERATED_TRACKED_KEYS

    def test_generated_provider_create_passes_readiness_probe(self, monkeypatch):
        monkeypatch.setenv(DATAROBOT_API_TOKEN_ENV, "tok")
        monkeypatch.setattr(
            "workload_api.resources.build_artifact_with_generated_dockerfile",
            MagicMock(return_value="artifact-1"),
        )
        provider = WorkloadGeneratedImageArtifactProvider()
        result = provider.create(
            {
                "workload_api_endpoint": "https://wapi.example.com",
                "artifact_name": "agent",
                "application_path": "/tmp/agent-app",
                "execution_environment_id": "ee-1",
                "execution_environment_version_id": "ee-v1",
                "entrypoint": ["sh", "run_server.sh"],
                "container_name": "agent",
                "container_port": 8080,
                "environment_vars": [],
                "routes": [],
                "build_timeout_s": 100,
                "readiness_probe": {"path": "/health", "port": 8080},
            }
        )
        assert result.id == "artifact-1"

        from workload_api.resources import build_artifact_with_generated_dockerfile

        _, kwargs = build_artifact_with_generated_dockerfile.call_args
        assert isinstance(kwargs["readiness_probe"], ReadinessProbe)
        assert kwargs["readiness_probe"].port == 8080

    def test_generated_provider_diff_replaces_on_tracked_change(self):
        provider = WorkloadGeneratedImageArtifactProvider()
        result = provider.diff(
            "id",
            {"execution_environment_id": "ee-1"},
            {"execution_environment_id": "ee-2"},
        )
        assert result.changes is True
        assert result.replaces == ["*"]

    def test_generated_provider_diff_no_change(self):
        provider = WorkloadGeneratedImageArtifactProvider()
        olds = {key: "same" for key in _GENERATED_TRACKED_KEYS}
        news = dict(olds)
        result = provider.diff("id", olds, news)
        assert result.changes is False

    def test_provider_delete_calls_delete_artifact(self, monkeypatch):
        monkeypatch.setenv(DATAROBOT_API_TOKEN_ENV, "tok")
        mock_client = MagicMock()
        monkeypatch.setattr(
            "workload_api.resources.WorkloadClient",
            MagicMock(return_value=mock_client),
        )
        provider = WorkloadGeneratedImageArtifactProvider()
        provider.delete(
            "artifact-1", {"workload_api_endpoint": "https://wapi.example.com"}
        )
        mock_client.delete_artifact.assert_called_once_with("artifact-1")


class TestCredentials:
    def test_returns_token_from_env(self, monkeypatch):
        monkeypatch.setenv(DATAROBOT_API_TOKEN_ENV, "my-token")
        assert datarobot_api_token() == "my-token"

    def test_raises_when_unset(self, monkeypatch):
        monkeypatch.delenv(DATAROBOT_API_TOKEN_ENV, raising=False)
        with pytest.raises(RuntimeError, match=DATAROBOT_API_TOKEN_ENV):
            datarobot_api_token()

    def test_raises_when_blank(self, monkeypatch):
        monkeypatch.setenv(DATAROBOT_API_TOKEN_ENV, "   ")
        with pytest.raises(RuntimeError, match=DATAROBOT_API_TOKEN_ENV):
            datarobot_api_token()
