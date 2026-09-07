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
"""
Registers the `dr_mcp_client` function group.

One YAML entry of this type with no `server:` block triggers auto-discovery of
every MCP server configured via env vars on agent/config.py's Config
(Config.resolve_all_mcp_configs()). Any additional entry WITH `server:` filled in
connects to exactly that one server -- unchanged, single-server behavior -- and is
excluded from the auto-discovery entry's sweep, so the same server is never
connected to twice.

DataRobotAuthAdapter, DataRobotMCPStreamableHTTPClient, and
_make_input_schema_enum_safe are intentionally NOT redefined here. They stay in the
installed plugin package -- generic, reusable, security-sensitive connection/auth
plumbing with no dependency on this agent's config -- so upstream fixes to auth or
reconnect behavior keep applying without a manual backport. This module owns only
what's specific to this agent: which env vars map to which servers, and how the
auto-discovery and explicit paths dedupe against each other.
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING

from nat.builder.builder import Builder
from nat.cli.register_workflow import register_per_user_function_group
from nat.data_models.component_ref import AuthenticationRef
from nat.plugins.mcp.client.client_config import MCPServerConfig
from nat.plugins.mcp.client.client_impl import MCPClientConfig
from pydantic import Field

if TYPE_CHECKING:
    from nat.plugins.mcp.client.client_impl import MCPFunctionGroup

logger = logging.getLogger(__name__)


class DrMcpClientConfig(MCPClientConfig, name="datarobot_mcp_client"):  # type: ignore[call-arg]
    """
    `server: None` (the default -- omit the field entirely in YAML) means: auto-
    discover every MCP server configured via env vars on agent/config.py's Config.
    A `server:` block filled in means: connect to exactly that server, and exclude
    it from any sibling auto-discovery entry's sweep.

    Deliberately carries no default_factory magic -- every value here is either
    explicit in this YAML entry, or resolved from agent/config.py's Config, never
    from a separate installed settings class the user hasn't opened.
    """

    server: MCPServerConfig | None = Field(
        default=None,
        description=(
            "Explicit server to connect to. Omit entirely to auto-discover every "
            "MCP server configured via env vars on agent/config.py's Config."
        ),
    )
    auth_provider: str | AuthenticationRef | None = Field(
        default=None,
        description="Auth provider reference, for the explicit-server case.",
    )


def _already_covered_urls(builder: Builder) -> set[str]:
    """
    URLs already claimed by a sibling `dr_mcp_client` entry that has `server:` set
    explicitly, so the auto-discovery sweep doesn't connect to them a second time.

    Walks whichever function actually owns `tool_names` -- which may be the
    workflow function itself, or (as with streaming_memory_agent) a wrapper one
    level up from it via `inner_agent_name`.
    """
    workflow_config = builder.get_workflow_config()
    inner_name = getattr(workflow_config, "inner_agent_name", None)
    target_config = builder.get_function_config(inner_name) if inner_name else workflow_config
    tool_names = getattr(target_config, "tool_names", [])

    covered: set[str] = set()
    for name in tool_names:
        try:
            fg_config = builder.get_function_group_config(name)
        except Exception:
            continue
        if isinstance(fg_config, DrMcpClientConfig) and fg_config.server is not None:
            covered.add(str(fg_config.server.url).rstrip("/"))
    return covered


@register_per_user_function_group(config_type=DrMcpClientConfig)
async def dr_mcp_client_function_group(config: DrMcpClientConfig, _builder: Builder) -> "MCPFunctionGroup":
    # Local imports: keep NAT plugin discovery (which imports this module just to
    # register the type) from eagerly pulling in the MCP adapter stack or this
    # agent's own Config -- matching the discipline already used elsewhere in this
    # agent's register.py.
    from nat.plugins.mcp.client.client_base import MCPSSEClient  # noqa: PLC0415
    from nat.plugins.mcp.client.client_impl import MCPFunctionGroup  # noqa: PLC0415
    from nat.plugins.mcp.client.client_impl import (  # noqa: PLC0415
        mcp_apply_tool_alias_and_description,
    )
    from nat.plugins.mcp.client.client_impl import mcp_session_tool_function  # noqa: PLC0415

    # These three stay defined in the installed library -- only imported here,
    # never redefined -- so upstream fixes to auth/reconnect behavior keep
    # applying without a manual backport into this repo.
    from datarobot_genai.dragent.plugins.datarobot_mcp_client import (
        DataRobotMCPStreamableHTTPClient,
        make_input_schema_enum_safe,
    )

    from agent.config import Config  # noqa: PLC0415

    group = MCPFunctionGroup(config=config)

    async def _populate_from_client(client, tool_overrides) -> None:
        all_tools = await client.get_tools()
        overrides = mcp_apply_tool_alias_and_description(all_tools, tool_overrides)
        for tool_name, tool in all_tools.items():
            override = overrides.get(tool_name)
            function_name = override.alias if override and override.alias else tool_name
            description = override.description if override and override.description else tool.description

            tool_fn = make_input_schema_enum_safe(mcp_session_tool_function(tool, group))
            single_fn = tool_fn.single_fn
            if single_fn is None:
                logger.warning("Skipping tool %s because single_fn is None", function_name)
                continue

            input_schema = tool_fn.input_schema
            if input_schema is type(None):  # noqa: E721
                input_schema = None

            group.add_function(
                name=function_name,
                description=description,
                fn=single_fn,
                input_schema=input_schema,
                converters=tool_fn.converters,
            )

    async def _build_client(url: str, transport: str, auth_provider):
        if transport == "sse":
            return MCPSSEClient(url)
        user_id = getattr(auth_provider.config, "default_user_id", url) if auth_provider else None
        client = DataRobotMCPStreamableHTTPClient(url, auth_provider=auth_provider, user_id=user_id)
        # TODO: for a server with no auth_provider but static headers (the
        # external/third-party case, e.g. weather_mcp_headers), those headers need
        # to reach this client somehow -- not yet wired here. Confirm how the base
        # MCPStreamableHTTPClient / DataRobotMCPStreamableHTTPClient accepts
        # pre-set static headers versus an auth_provider.
        return client

    async with AsyncExitStack() as stack:
        if config.server is not None:
            # Explicit single-server path -- same behavior as the installed
            # plugin's original datarobot_mcp_client_function_group.
            auth_provider = await _builder.get_auth_provider(config.auth_provider) if config.auth_provider else None
            client = await _build_client(str(config.server.url), config.server.transport, auth_provider)
            await stack.enter_async_context(client)
            group.mcp_client = client
            group.mcp_client_server_name = client.server_name
            group.mcp_client_transport = client.transport
            await _populate_from_client(client, config.tool_overrides)
        else:
            # Auto-discovery path -- sweep every MCP server configured via env
            # vars, skipping anything a sibling entry already declared explicitly.
            covered = _already_covered_urls(_builder)
            for mcp_config in Config().resolve_all_mcp_configs():
                url = str(mcp_config.url).rstrip("/")
                if url in covered:
                    logger.debug("Skipping %s: already declared explicitly elsewhere", url)
                    continue

                auth_provider = None
                if getattr(mcp_config, "use_datarobot_auth", False):
                    auth_provider = await _builder.get_auth_provider("datarobot_auth")

                client = await _build_client(
                    str(mcp_config.url),
                    getattr(mcp_config, "transport", "streamable-http"),
                    auth_provider,
                )
                await stack.enter_async_context(client)
                await _populate_from_client(client, tool_overrides={})

        yield group
