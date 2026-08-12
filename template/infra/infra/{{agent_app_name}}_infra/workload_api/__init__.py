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

Vendored provider plumbing, not agent code: it exists only because
``pulumi-datarobot`` has no resource yet for "artifact whose image the platform
builds from uploaded source". It lives inside the agent's package (rather than
as a top-level sibling of ``infra/``) so that ownership is unambiguous and so
that it cannot collide with the same-named package shipped by other components
into the shared ``infra/`` project.

No agent-deployment decisions live here — that's the agent's ``../workload.py``
job, which chooses the deployment scenario and assembles the payloads (container
env vars, the pre-built-image artifact args) from the models exported below.
Source upload for image builds is a stand-in in ``artifact_code.py`` until
native Pulumi ``ArtifactCode`` support ships.
"""

from .artifact_code import source_hash
from .client import WORKLOAD_ARTIFACT_TYPE, ReadinessProbe
from .resources import WorkloadGeneratedImageArtifact

__all__ = [
    "WORKLOAD_ARTIFACT_TYPE",
    "ReadinessProbe",
    "WorkloadGeneratedImageArtifact",
    "source_hash",
]
