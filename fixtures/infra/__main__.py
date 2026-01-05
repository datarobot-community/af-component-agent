# Copyright 2025 DataRobot, Inc.
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
Pulumi program entrypoint for infra fixture.

The real Application Framework project provides a shared infra `__main__.py` that
imports all component infra modules. In this component repo we only render the
agent template, so our tests need a minimal entrypoint to make `pulumi up` work.
"""

# Importing the module is enough for Pulumi: resources are created at import time.
# noqa is used because this import is intentionally "unused" by the code.
import infra.agent  # noqa: F401


