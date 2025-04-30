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

from typing import Any, Dict, Union


class MyAgent:
    def __init__(
        self, api_key: str, api_base: str, verbose: Union[bool, str], **kwargs: Any
    ):
        self.api_key = api_key
        self.api_base = api_base
        if isinstance(verbose, str):
            self.verbose = verbose.lower() == "true"
        elif isinstance(verbose, bool):
            self.verbose = verbose

    def run(self, inputs: Dict[str, str]) -> str:
        _ = inputs, self.api_key
        return "success"
