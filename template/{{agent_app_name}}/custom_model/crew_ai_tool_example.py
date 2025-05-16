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
from typing import Tuple, Dict

from tools.client import ToolClient
from crewai.tools import tool


@tool
def create_google_drive_file(file_name: str, mimetype: str, file_content: str) -> Tuple[bytes, Dict[str, str]]:
    """Create a file in Google Drive using the Drive API.

    Args:
        file_name (str): The name of the file to create.
        mimetype (str): The MIME type of the file.
        file_content (str): The content of the file.

    Returns:
        Tuple[bytes, Dict[str, str]]: The response content and headers.
    """
    content, headers = ToolClient().call(
        deployment_id="<your-tool-deployment-id>",
        payload={
            "file_name": file_name,
            "mimetype": mimetype,
            "file_content": file_content,
        },
    )
    return content, headers


if __name__ == "__main__":

    # To run the CrewAI tool, run it with input parameters
    response = create_google_drive_file.run(
        file_name="agent-tool-test-file.txt",
        mimetype="text/plain",
        file_content="Hello, from Agent Tool!",
    )

    response_content, response_headers = response
    print("Response Content:", json.loads(response_content))
    print("Response Headers:", response_headers)