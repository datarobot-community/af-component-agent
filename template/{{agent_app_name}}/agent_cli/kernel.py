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
import json
import os
import time
from typing import Any, Dict, Optional

import requests
from openai import OpenAI
from openai.types.chat import ChatCompletion


class Kernel:
    def __init__(
        self,
        api_token: str,
        codespace_id: str,
        base_url: Optional[str] = "https://staging.datarobot.com",
    ):
        self.base_url = base_url
        self.codespace_id = codespace_id
        self.api_token = api_token

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Token {self.api_token}",
        }

    @property
    def nbx_session_url(self) -> str:
        return f"{self.base_url}/api-gw/nbx/session"

    @property
    def nbx_orchestrator_url(self) -> str:
        return f"{self.base_url}/api-gw/nbx/orchestrator/notebooks"

    def start_codespace(self) -> None:
        """
        Starts a codespace in DataRobot.
        """
        print("Starting codespace...")
        url = f"{self.nbx_orchestrator_url}/{self.codespace_id}/start/"
        response = requests.post(url, headers=self.headers)
        assert response.status_code == 200
        print("Waiting for codespace to start...")
        for _ in range(2 * 60):  # Waiting 2 minutes
            resp = requests.get(
                f"{self.nbx_orchestrator_url}/{self.codespace_id}/",
                headers=self.headers,
            )
            assert resp.status_code == 200, (resp.status_code, resp.text)
            data = resp.json()
            if data.get("status") == "running":
                break
            time.sleep(1)
        print("Codespace started!")

    def stop_codespace(self) -> None:
        """
        Starts a codespace in DataRobot.
        """
        print("Stopping codespace...")
        url = f"{self.nbx_orchestrator_url}/{self.codespace_id}/stop/"
        response = requests.post(url, headers=self.headers)
        assert response.status_code == 200
        print("Waiting for codespace to stop...")
        for _ in range(2 * 60):  # Waiting 2 minutes
            resp = requests.get(
                f"{self.nbx_orchestrator_url}/{self.codespace_id}/",
                headers=self.headers,
            )
            assert resp.status_code == 200, (resp.status_code, resp.text)
            data = resp.json()
            if data.get("status") == "stopped":
                break
            time.sleep(1)
        print("Codespace stopped!")

    def await_kernel_execution(self, kernel_id: str, max_wait: int = 120) -> None:
        for _ in range(max_wait):
            resp = requests.get(
                f"{self.nbx_session_url}/{self.codespace_id}/kernels/{kernel_id}",
                headers=self.headers,
            )
            if resp.status_code == 404:
                break

            assert resp.status_code == 200
            time.sleep(1)


class AgentKernel(Kernel):
    def __init__(
        self,
        api_token: str,
        codespace_id: str,
        base_url: str,
    ):
        super().__init__(
            api_token=api_token, codespace_id=codespace_id, base_url=base_url
        )

    def execute(
        self,
        user_prompt: str,
        use_remote: bool = False,
        custom_model_dir: str = "",
        output_path: str = "",
    ) -> Any:
        if len(user_prompt) == 0:
            raise ValueError("user_prompt must be provided.")

        if len(custom_model_dir) == 0:
            if use_remote:
                custom_model_dir = "/home/notebooks/storage/custom_model"
            else:
                custom_model_dir = os.path.join(os.getcwd(), "custom_model")

        if len(output_path) == 0:
            if use_remote:
                output_path = "/home/notebooks/storage/custom_model/output.json"
            else:
                output_path = os.path.join(os.getcwd(), "custom_model", "output.json")

        extra_body = json.dumps(
            {
                "api_key": self.api_token,
                "api_base": self.base_url,
                "verbose": True,
            }
        )
        command_args = (
            f"--user_prompt '{user_prompt}' "
            f"--extra_body '{extra_body}'"
            f" --custom_model_dir '{custom_model_dir}'"
            f" --output_path '{output_path}'"
        )

        if use_remote:
            remote_cmd = {
                "filePath": "/home/notebooks/storage/run_agent.py",
                "commandType": "python",
                "commandArgs": command_args,
            }
            response = requests.post(
                f"{self.nbx_session_url}/{self.codespace_id}/scripts/execute/",
                json=remote_cmd,
                headers=self.headers,
            )
            print(response.json())
            assert response.status_code == 200

            print("Executing kernel...")
            self.await_kernel_execution(response.json()["kernelId"])
            return self.get_output_remote(output_path)
        else:
            local_cmd = f"python3 docker_context/run_agent.py {command_args}"
            os.system(local_cmd)
            return self.get_output_local(output_path)

    @staticmethod
    def get_output_local(output_path: str) -> Any:
        """Read the local output file and remove it."""
        with open(output_path, "r") as f:
            output = f.read()

        if os.path.exists(output_path):
            os.remove(output_path)
        return output

    def get_output_remote(self, output_path: str) -> Any:
        """Download the output file from the remote and remove it."""
        data = {"paths": [output_path]}
        response = requests.post(
            f"{self.nbx_session_url}/{self.codespace_id}/filesystem/objects/download/",
            json=data,
            headers=self.headers,
        )
        assert response.status_code == 200
        output = response.json()

        # Delete the output file after downloading
        response = requests.delete(
            f"{self.nbx_session_url}/{self.codespace_id}/filesystem/objects/delete/",
            headers=self.headers,
            json={
                "paths": [output_path],
            },
        )
        assert response.status_code == 204

        return output

    def deployment(self, deployment_id: str, user_prompt: str) -> ChatCompletion:
        chat_api_url = f"{self.base_url}/api/v2/deployments/{deployment_id}/"
        print(chat_api_url)
        openai_client = OpenAI(
            base_url=chat_api_url,
            api_key=self.api_token,
            _strict_response_validation=False,
        )

        print(f'Querying deployment with prompt: "{user_prompt}"')
        completion = openai_client.chat.completions.create(
            model="datarobot-deployed-agent",
            messages=[
                {
                    "role": "system",
                    "content": "Explain your thoughts using at least 100 words.",
                },
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=512,  # omit if you want to use the model's default max
            extra_body={
                "api_key": self.api_token,
                "api_base": self.base_url,
                "verbose": False,
            },
        )
        return completion
