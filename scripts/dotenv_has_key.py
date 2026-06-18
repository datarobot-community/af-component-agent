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
"""Exit 0 when a key has a non-empty value in .env (invoked from copier _tasks)."""

from __future__ import annotations

import sys
from pathlib import Path

# Copier invokes this script from the destination tree; src_path is on PYTHONPATH.
from extensions.dotenv_lookup import _dotenv_value


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: dotenv_has_key <KEY>", file=sys.stderr)
        return 2

    key = sys.argv[1]
    return 0 if _dotenv_value(Path(".env"), key) is not None else 1


if __name__ == "__main__":
    sys.exit(main())
