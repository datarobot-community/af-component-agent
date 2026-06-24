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
"""Set llm_model_name on a DataRobot Memory Space (used by Pulumi deploy hooks)."""

from __future__ import annotations

import argparse

import datarobot


def configure_memory_space_llm(space_id: str, llm_model_name: str) -> None:
    space = datarobot.MemorySpace.get(space_id)
    if space.llm_model_name == llm_model_name:
        return
    space.update(llm_model_name=llm_model_name)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Configure llm_model_name on a DataRobot Memory Space."
    )
    parser.add_argument("space_id", help="Memory space UUID")
    parser.add_argument(
        "llm_model_name",
        help="LLM Gateway catalog model name (without datarobot/ prefix)",
    )
    args = parser.parse_args()
    configure_memory_space_llm(args.space_id, args.llm_model_name)


if __name__ == "__main__":
    main()
