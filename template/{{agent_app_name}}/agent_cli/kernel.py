# Copyright 2025 DataRobot, Inc. and its affiliates.
#
# All rights reserved.
#
# This is proprietary source code of DataRobot, Inc. and its affiliates.
#
# Released under the terms of DataRobot Tool and Utility Agreement.
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
        agent_root: str,
    ):
        super().__init__(
            api_token=api_token, codespace_id=codespace_id, base_url=base_url
        )
        self.agent_root = agent_root

    def execute_remote(
        self, user_prompt: Optional[str] = None, use_drum: bool = False
    ) -> Any:
        """
        Execute a command and return the output.
        """
        print("Executing agent remotely...")
        if user_prompt is not None:
            extra_body = json.dumps(
                {
                    "api_key": self.api_token,
                    "api_base": self.base_url,
                    "verbose": True,
                }
            )
            command_args = f"--store_output --user_prompt '{user_prompt}' --extra_body '{extra_body}'"
            if use_drum:
                command_args += " --use_drum"
            json_data = {
                "filePath": f"/home/notebooks/storage/{self.agent_root}/run_agent.py",
                "commandType": "python",
                "commandArgs": command_args,
            }
        else:
            raise ValueError("Either user_prompt or data must be provided.")
        response = requests.post(
            f"{self.nbx_session_url}/{self.codespace_id}/scripts/execute/",
            json=json_data,
            headers=self.headers,
        )
        assert response.status_code == 200
        print("Executing kernel...")
        self.await_kernel_execution(response.json()["kernelId"])

        return self.get_output_remote()

    def execute_local(
        self, user_prompt: Optional[str] = None, use_drum: bool = False
    ) -> Any:
        print("Executing agent locally...")
        if user_prompt is not None:
            extra_body = json.dumps(
                {
                    "api_key": self.api_token,
                    "api_base": self.base_url,
                    "verbose": True,
                }
            )
            cmd = (
                f"python3 {self.agent_root}/run_agent.py "
                f"--store_output "
                f"--user_prompt '{user_prompt}' "
                f"--extra_body '{extra_body}'"
            )
            if use_drum:
                cmd += " --use_drum"
        else:
            raise ValueError("Either user_prompt or data must be provided.")
        if os.path.exists(os.path.join(os.getcwd(), self.agent_root, "output.json")):
            os.remove(os.path.join(os.getcwd(), self.agent_root, "output.json"))

        os.system(cmd)

        with open(os.path.join(os.getcwd(), self.agent_root, "output.json"), "r") as f:
            output = f.read()

        if os.path.exists(os.path.join(os.getcwd(), self.agent_root, "output.json")):
            os.remove(os.path.join(os.getcwd(), self.agent_root, "output.json"))
        return output

    def get_output_remote(self) -> Any:
        data = {"paths": [f"/home/notebooks/storage/{self.agent_root}/output.json"]}
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
                "paths": [f"/home/notebooks/storage/{self.agent_root}/output.json"],
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
