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
from typing import Dict, Any, Tuple, Union, Iterator, Optional

import openai
import datarobot as dr
import pandas as pd
import json
from datarobot_predict.deployment import (
    predict_unstructured,
    predict,
    PredictionResult,
    UnstructuredPredictionResult,
)
from openai.types import CompletionCreateParams
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from auth import get_authorization_context


class ToolClient:
    """Client for interacting with Agent Tools Deployments.

    This class provides methods to call the custom model tool using various hooks:
    `score`, `score_unstructured`, and `chat`. When the `authorization_context` is set,
    the client automatically propagates it to the agent tool. The `authorization_context`
    is required for retrieving access tokens to connect to external services.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """Initialize the ToolClient.

        Args:
            api_key (Optional[str]): API key for authentication. Defaults to environment variable `DATAROBOT_API_TOKEN`.
            base_url (Optional[str]): Base URL for the DataRobot API. Defaults to environment variable `DATAROBOT_BASE_URL`.
        """
        self.api_key = api_key or os.getenv("DATAROBOT_API_TOKEN")
        self.base_url = base_url or os.getenv(
            "DATAROBOT_BASE_URL", "https://app.datarobot.com"
        )

    def get_deployment(self, deployment_id: str) -> dr.Deployment:
        """Retrieve a deployment by its ID.

        Args:
            deployment_id (str): The ID of the deployment.

        Returns:
            dr.Deployment: The deployment object.
        """
        dr.Client(self.api_key, self.base_url)
        return dr.Deployment.get(deployment_id=deployment_id)

    def _get_authorization_context(self) -> Dict[str, Any]:
        """Retrieve the authorization context.

        Returns:
            Dict[str, Any]: The authorization context.
        """
        return get_authorization_context()

    def call(
        self, deployment_id: str, payload: Dict[str, Any], **kwargs
    ) -> UnstructuredPredictionResult:
        """Run the custom model tool using score_unstructured hook.

        Args:
            deployment_id (str): The ID of the deployment.
            payload (Dict[str, Any]): The input payload.
            **kwargs: Additional keyword arguments.

        Returns:
            UnstructuredPredictionResult: The response content and headers.
        """
        data = {
            "payload": payload,
            "authorization_context": self._get_authorization_context(),
        }
        return predict_unstructured(
            deployment=self.get_deployment(deployment_id),
            data=json.dumps(data),
            content_type="application/json",
            **kwargs,
        )

    def score(
        self, deployment_id: str, data_frame: pd.DataFrame, **kwargs
    ) -> PredictionResult:
        """Run the custom model tool using score hook.

        Args:
            deployment_id (str): The ID of the deployment.
            data_frame (pd.DataFrame): The input data frame.
            **kwargs: Additional keyword arguments.

        Returns:
            PredictionResult: The response content and headers.
        """
        return predict(
            deployment=self.get_deployment(deployment_id),
            data_frame=data_frame,
            **kwargs,
        )

    def chat(
        self,
        completion_create_params: CompletionCreateParams,
        model: str,
    ) -> Union[ChatCompletion, Iterator[ChatCompletionChunk]]:
        """Run the custom model tool with the chat hook.

        Args:
            completion_create_params (CompletionCreateParams): Parameters for the chat completion.
            model (str): The model to use.

        Returns:
            Union[ChatCompletion, Iterator[ChatCompletionChunk]]: The chat completion response.
        """
        extra_body = {
            "authorization_context": self._get_authorization_context(),
        }
        return openai.chat.completions.create(
            **completion_create_params,
            model=model,
            extra_body=extra_body,
        )
