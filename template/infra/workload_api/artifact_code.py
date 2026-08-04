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

"""Upload agent source to a Workload API artifact.

Stand-in for pulumi-datarobot's not-yet-shipped ``ArtifactCode`` resource
(PBMP-7947). Delete this module (and the ``code_ref`` field it feeds) once
native Pulumi support lands.
"""

from __future__ import annotations

import hashlib
import io
import os
import time
import zipfile
from collections.abc import Callable
from pathlib import Path

import requests
from gitignore_parser import parse_gitignore  # type: ignore[import-untyped]

WAPI_IGNORE_FILENAME = ".wapiignore"
DEFAULT_UPLOAD_TIMEOUT_S = 300
DEFAULT_STATUS_POLL_TIMEOUT_S = 600
DEFAULT_STATUS_POLL_INTERVAL_S = 2
STATUS_COMPLETED = "COMPLETED"
_STATUS_FAILURES = frozenset({"ERROR", "ABORTED", "EXPIRED"})


def _iter_source_files(application_path: Path) -> list[tuple[Path, str]]:
    ignore_file = application_path / WAPI_IGNORE_FILENAME
    is_ignored = (
        parse_gitignore(ignore_file) if ignore_file.is_file() else lambda _path: False
    )
    files: list[tuple[Path, str]] = []
    for dirpath, dirnames, filenames in os.walk(application_path, followlinks=True):
        dirnames[:] = [d for d in dirnames if not is_ignored(os.path.join(dirpath, d))]
        for filename in filenames:
            file_path = Path(dirpath) / filename
            if is_ignored(str(file_path)):
                continue
            rel_path = file_path.relative_to(application_path).as_posix()
            files.append((file_path.resolve(), rel_path))
    return sorted(files, key=lambda item: item[1])


def source_archive(application_path: Path) -> bytes:
    """Deterministic zip of the agent source, minus ``.wapiignore`` matches."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for abs_path, rel_path in _iter_source_files(application_path):
            info = zipfile.ZipInfo(rel_path)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            stat = abs_path.stat()
            info.external_attr = (stat.st_mode & 0xFFFF) << 16
            archive.writestr(info, abs_path.read_bytes())
    return buffer.getvalue()


def source_hash(application_path: Path) -> str:
    """sha256 of ``source_archive()`` — exactly the bytes we upload."""
    return hashlib.sha256(source_archive(application_path)).hexdigest()


def _wait_until_extracted(
    base: str,
    token: str,
    status_id: str,
    *,
    poll_timeout_s: int,
    poll_interval_s: int,
    sleep: Callable[[float], None],
    now: Callable[[], float],
) -> None:
    deadline = now() + poll_timeout_s
    url = f"{base}/status/{status_id}/"
    headers = {"Authorization": f"Bearer {token}"}
    while True:
        resp = requests.get(url, headers=headers, timeout=60, allow_redirects=False)
        if resp.status_code == 303:
            return
        if resp.status_code != 200:
            raise requests.HTTPError(
                f"{resp.status_code} {resp.reason} for GET {url}\n{resp.text[:2000]}",
                response=resp,
            )
        status = str(resp.json().get("status", "UNKNOWN"))
        if status == STATUS_COMPLETED:
            return
        if status in _STATUS_FAILURES:
            message = resp.json().get("message", "")
            raise RuntimeError(f"files upload {status_id} {status}: {message}")
        if now() >= deadline:
            raise TimeoutError(
                f"files upload {status_id} not done after {poll_timeout_s}s "
                f"(last={status})"
            )
        sleep(poll_interval_s)


def upload_source(
    *,
    endpoint: str,
    token: str,
    application_path: Path,
    timeout_s: int = DEFAULT_UPLOAD_TIMEOUT_S,
    poll_timeout_s: int = DEFAULT_STATUS_POLL_TIMEOUT_S,
    poll_interval_s: int = DEFAULT_STATUS_POLL_INTERVAL_S,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
) -> tuple[str, str]:
    """Upload the archive; return ``(catalog_id, catalog_version_id)``."""
    base = endpoint.rstrip("/")
    zip_bytes = source_archive(application_path)
    url = f"{base}/files/fromFile/?useArchiveContents=true"
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("source.zip", zip_bytes, "application/octet-stream")}
    resp = requests.post(url, headers=headers, files=files, timeout=timeout_s)
    if resp.status_code not in (200, 201, 202):
        raise requests.HTTPError(
            f"{resp.status_code} {resp.reason} for POST {url}\n{resp.text[:2000]}",
            response=resp,
        )
    data = resp.json()
    catalog_id = data["catalogId"]
    catalog_version_id = data.get("catalogVersionId")
    status_id = data.get("statusId")
    if status_id:
        _wait_until_extracted(
            base,
            token,
            status_id,
            poll_timeout_s=poll_timeout_s,
            poll_interval_s=poll_interval_s,
            sleep=sleep,
            now=now,
        )
    if not catalog_version_id:
        raise RuntimeError(
            f"files upload for {application_path} returned no catalogVersionId"
        )
    return catalog_id, catalog_version_id
