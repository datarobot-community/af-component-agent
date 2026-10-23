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
"""Copier migration (11.11.115): a one-time note for projects that bundle an MCP server.

The Agentic Starter template no longer bundles one. Projects that only update the agent
(`dr component update`) see this before they pull the template. It only prints, so it
never blocks an update. It lives in a file, not inline in copier.yml, because copier
prints a migration's whole command before running it.
"""

import glob
import sys

found = sorted(glob.glob(".datarobot/answers/drmcp-*.y*ml") + glob.glob(".datarobot/answers/fastmcp-*.y*ml"))
if found:
    print(
        f"\nNOTE: This project includes an MCP server ({', '.join(found)}).\n"
        "      The latest Agentic Starter template removes it, a breaking change: MCP\n"
        "      servers now run as standalone apps. This update doesn't change your MCP\n"
        "      server. When you pull the latest template, your agent loses the old\n"
        "      server's tools, and a deployed app's next deploy stops until you move\n"
        "      them to a standalone MCP server or confirm you don't need them. See\n"
        "      docs/mcp-migration.md in\n"
        "      https://github.com/datarobot-community/datarobot-agent-application\n",
        file=sys.stderr,
    )
