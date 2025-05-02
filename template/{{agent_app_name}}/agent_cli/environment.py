# Copyright 2025 DataRobot, Inc. and its affiliates.
#
# All rights reserved.
#
# This is proprietary source code of DataRobot, Inc. and its affiliates.
#
# Released under the terms of DataRobot Tool and Utility Agreement.
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
