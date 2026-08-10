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

"""Workload API HTTP client and Pulumi dynamic-resource plumbing.

No agent-deployment decisions live here — that's the agent's ``*_infra/workload.py``
job. Source upload for image builds is a stand-in in ``artifact_code.py`` until
native Pulumi ``ArtifactCode`` support ships.
"""

from .artifact_code import source_hash
from .client import (
    WorkloadArtifactSpecFromImageUri,
    build_artifact_from_image_uri,
)
from .resources import (
    WorkloadGeneratedImageArtifact,
    WorkloadImageArtifact,
)

__all__ = [
    "source_hash",
    "WorkloadArtifactSpecFromImageUri",
    "build_artifact_from_image_uri",
    "WorkloadGeneratedImageArtifact",
    "WorkloadImageArtifact",
]
