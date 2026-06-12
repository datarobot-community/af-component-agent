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
"""Write MEM0_API_KEY to the project .env file (invoked from copier _tasks)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    key = os.environ.get("MEM0_API_KEY_VALUE", "").strip()
    if not key:
        return 0

    env_path = Path(".env")
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    new_lines: list[str] = []
    updated = False
    for line in lines:
        if line.startswith("MEM0_API_KEY="):
            new_lines.append(f"MEM0_API_KEY={key}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        if new_lines and new_lines[-1] != "":
            new_lines.append("")
        new_lines.append(f"MEM0_API_KEY={key}")
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
