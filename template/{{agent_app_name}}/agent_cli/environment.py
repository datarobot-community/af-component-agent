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
import os
from typing import Optional

from .kernel import AgentKernel


class Environment:
    def __init__(
        self,
        codespace_id: Optional[str] = None,
        api_token: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.codespace_id = os.environ.get("DATAROBOT_CODESPACE_ID") or codespace_id
        self.api_token = os.environ.get("DATAROBOT_API_TOKEN") or api_token
        self.base_url = (
            os.environ.get("DATAROBOT_ENDPOINT")
            or base_url
            or "https://app.datarobot.com"
        )
        self.base_url = self.base_url.replace("/api/v2", "")
        self.agent_root = "custom_model"

    @property
    def interface(self) -> AgentKernel:
        return AgentKernel(
            codespace_id=str(self.codespace_id),
            api_token=str(self.api_token),
            base_url=str(self.base_url),
            agent_root=str(self.agent_root),
        )
