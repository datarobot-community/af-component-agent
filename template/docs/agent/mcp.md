# MCP tools

The agent can call tools served by a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server, in addition to its workflow tools and the tools defined in code. This page describes how the agent finds its MCP server, what it sends to that server, and how the setting reaches a deployed agent.

For where MCP tools are loaded in code, see [MCP tools](./README.md#mcp-tools) and the guide for your framework.

| Section | Description |
|---|---|
| [Point the agent at an MCP server](#point-the-agent-at-an-mcp-server) | The settings, which one wins, and what each sends. |
| [Deployed agents](#deployed-agents) | How the setting reaches the deployed agent. |
| [MCP server deployed with the agent](#mcp-server-deployed-with-the-agent) | Automatic wiring of an MCP server added to the same project. |
| [MCP servers that require Okta XAA](#mcp-servers-that-require-okta-xaa) | The `mcp_client_with_xaa_support` function group, its server URL, and DataRobot 11.13 and older. |
| [Troubleshooting](#troubleshooting) | No MCP tools, and settings that are ignored. |

## Point the agent at an MCP server

Set one of the following in the project's `.env`. When more than one is set, the agent uses the first one in this table.

| Setting | MCP server | Sent to the server |
|---|---|---|
| `MCP_WORKLOAD_ID` | Runs on the DataRobot Workload API. The agent asks the Workload API for the workload's endpoint. | The DataRobot API token as `Authorization` and `x-datarobot-api-key`, and the authorization context |
| `MCP_DEPLOYMENT_ID` | Deployed in DataRobot as a custom model. | The DataRobot API token as `Authorization`, and the authorization context |
| `EXTERNAL_MCP_URL` | Any other endpoint, for example `https://example.com/mcp/`. | Only the headers in `EXTERNAL_MCP_HEADERS` |
| `MCP_SERVER_PORT` | Runs on this machine, at `http://localhost:<port>`. | The DataRobot API token as `Authorization`, and the authorization context |

Workload and deployment IDs are 24 hexadecimal characters. Any other value is ignored, with a warning.

Two more settings apply to `EXTERNAL_MCP_URL` only:

- `EXTERNAL_MCP_HEADERS`: a JSON object of headers, for example `'{"Authorization": "Bearer <token>"}'`.
- `EXTERNAL_MCP_TRANSPORT`: `streamable-http` (default) or `sse`.

For example, the [DataRobot Global MCP](https://docs.datarobot.com/en/docs/agentic-ai/agentic-mcp/agentic-mcp-overview.html), which DataRobot runs on every instance. Its address is the DataRobot endpoint followed by `/genai/globalmcp/mcp`:

```sh
EXTERNAL_MCP_URL=https://app.datarobot.com/api/v2/genai/globalmcp/mcp
EXTERNAL_MCP_HEADERS='{"Authorization": "Bearer <DataRobot API key>"}'
```

The agent then gets every tool the Global MCP has. To give it only some, list their names, separated by commas, in the `x-datarobot-mcp-tools` header (the name starts with `x-`):

```sh
EXTERNAL_MCP_HEADERS='{"Authorization": "Bearer <DataRobot API key>", "x-datarobot-mcp-tools": "<tool name>,<tool name>"}'
```

With none of the table's settings set, the agent uses only its other tools.

## Deployed agents

`dr run deploy` passes the following parameters, if set, from `.env` to the deployed agent as [runtime parameters](./runtime-parameters.md): `MCP_WORKLOAD_ID`, `MCP_DEPLOYMENT_ID`, `EXTERNAL_MCP_URL`, `EXTERNAL_MCP_HEADERS`, and `EXTERNAL_MCP_TRANSPORT`. `MCP_SERVER_PORT` is not passed, because it is only meaningful to the local machine.

To point a deployed agent at another server, change the setting in `.env` and run `dr run deploy` again, or edit the runtime parameter on the deployment in DataRobot.

## MCP server deployed with the agent

A project can also contain an MCP server built from the [DataRobot MCP component](https://github.com/datarobot-community/af-component-datarobot-mcp). When that server is added under the default name `mcp_server`, its infrastructure module `infra/infra/mcp_server.py` exists, and:

- `dr run deploy` deploys the server in the server's default serverless deployment mode and connects the deployed agent to it automatically.
- In that mode, the module decides the deployed agent's MCP settings, and the settings in `.env` are not passed to the deployed agent.

When the server is deployed to the Workload API instead (`ENABLE_MCP_ON_WORKLOAD_API=true`), newer versions of the MCP component pass the workload's ID as `MCP_WORKLOAD_ID`, so the deployed agent connects to it automatically there too, and again the settings in `.env` are not passed to it. Older versions pass no MCP settings: the deployed agent then uses the settings in `.env`, so set `MCP_WORKLOAD_ID` to the server's workload ID.

An MCP server added under any other name is not connected automatically. Point the agent at it with `MCP_DEPLOYMENT_ID` or `MCP_WORKLOAD_ID`.

When `workflow.yaml` connects to the server with the Okta function group, the deployed agent gets the server's URL in place of these settings. See [MCP servers that require Okta XAA](#mcp-servers-that-require-okta-xaa).

When the agent runs locally, it always uses the settings in `.env`.

## MCP servers that require Okta XAA

For an MCP server that only accepts Okta cross-application access (XAA) tokens, connect to it with an `mcp_client_with_xaa_support` function group in `workflow.yaml`. The group exchanges the caller's Okta token for a token the server accepts and sends only that token. It never sends the agent's DataRobot API token.

```yaml
function_groups:
  mcp_tools:
    _type: mcp_client_with_xaa_support
    server:
      url: ${MCP_SERVER_URL}
      auth_provider: okta_auth

authentication:
  okta_auth:
    _type: okta_cross_app_access
```

Then add the group to the agent's tools: `tool_names` of the agent function, for example `functions.langgraph_agent.tool_names`. In the NAT template, replace the existing `mcp_tools` group, which is already in `tool_names`.

The group exchanges tokens with the agent's Okta identity, `IDP_AGENT_ID` and `IDP_AGENT_PRIVATE_KEY_JWK`. See [A2A authentication](./agent2agent-auth.md) for those settings.

### The server URL

`${MCP_SERVER_URL}` is filled from the `MCP_SERVER_URL` setting when the agent starts. When a `mcp_client_with_xaa_support` group has `${MCP_SERVER_URL}` as its `url`, `dr run deploy` does the following:

- It passes `MCP_SERVER_URL` to the deployed agent as a [runtime parameter](./runtime-parameters.md). For an [MCP server deployed with the agent](#mcp-server-deployed-with-the-agent), the value is that server's endpoint, in both deployment modes. Otherwise it is `MCP_SERVER_URL` from `.env`, for example `https://app.datarobot.com/api/v2/deployments/<deployment-id>/directAccess/mcp/`, and the deployment fails when that is not set.
- It does not pass `MCP_WORKLOAD_ID` or `MCP_DEPLOYMENT_ID`, so the agent does not also connect to the server with its DataRobot API token.

`EXTERNAL_MCP_URL` and its settings are passed as before. A group with any other `url` does not change what `dr run deploy` passes.

An agent deployed as a custom model gets `MCP_SERVER_URL` as an environment variable on DataRobot 11.9 and newer. On 11.5 to 11.8, enable the `ENABLE_RUNTIME_PARAMETERS_IMPROVEMENTS` feature flag. An agent on the Workload API always gets it.

When the agent runs locally, set `MCP_SERVER_URL` in `.env`, or give the `url` a default, for example `${MCP_SERVER_URL:-http://localhost:9000/mcp/}`. Without a value the agent does not start. Local runs are otherwise unchanged: with `MCP_SERVER_PORT` set, the agent also connects to that server with your DataRobot API token.

### DataRobot 11.13 and older

Without a `cross_application_access` block, the group reads the Okta settings from the document the MCP server publishes at `/.well-known/oauth-protected-resource`. For an MCP server deployed as a custom model, the agent can read that document on DataRobot 11.14 and newer. On 11.13 and older it cannot, and the agent runs without the server's tools. On those versions, set the block on the group:

```yaml
function_groups:
  mcp_tools:
    _type: mcp_client_with_xaa_support
    server:
      url: ${MCP_SERVER_URL}
      auth_provider: okta_auth
    cross_application_access:
      token_exchange:
        trusted_issuer: "https://your-org.okta.com"
        audience: "https://your-org.okta.com/oauth2/ausXXXXXXXXXXXXXXX"
      token_request:
        token_url: "https://your-org.okta.com/oauth2/ausXXXXXXXXXXXXXXX/v1/token"
        audience: "https://example.com/mcp-servers/my-mcp-server"
        scopes:
          - "dr.impersonation"
```

The values are the ones the MCP server is configured with:

| Field | MCP server setting |
|---|---|
| `token_exchange.trusted_issuer` | `MCP_XAA_TRUSTED_ISSUER` |
| `token_exchange.audience` | `MCP_XAA_EXCHANGE_AUDIENCE` |
| `token_request.token_url` | `MCP_XAA_TOKEN_URL` |
| `token_request.audience` | `MCP_XAA_TOKEN_AUDIENCE` |
| `token_request.scopes` | `MCP_XAA_SCOPES`, and every scope the server's tools require |

With the block, the agent requests exactly the scopes listed. Without it, the agent requests the scopes the server publishes.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| The agent answers without MCP tools, and the log has a warning about the MCP server | The server could not be reached. The agent keeps running without MCP tools. | Check that the server is running and that the setting points at it. |
| A setting in `.env` has no effect | A setting higher in the [table](#point-the-agent-at-an-mcp-server) is also set. | Remove the settings you do not use. |
| The deployed agent ignores the MCP settings in `.env` | The project contains `infra/infra/mcp_server.py`, which connects the deployed agent to its own server: in the default serverless mode, and on the Workload API with newer versions of the MCP component. | See [MCP server deployed with the agent](#mcp-server-deployed-with-the-agent). |
| The deployed agent finds no workload server | The agent's API token cannot read the workload, or the workload is not running yet. | Check the workload in DataRobot. The agent looks the endpoint up again on the next request. |
| The agent answers without MCP tools, and the log has an error about a connection or XAA exchange | The `mcp_client_with_xaa_support` group could not read the server's Okta settings or exchange the caller's token. A request without an Okta token, such as a chat in the playground, always ends this way. | Call the agent with an Okta token. On DataRobot 11.13 and older, set `cross_application_access` on the group. See [MCP servers that require Okta XAA](#mcp-servers-that-require-okta-xaa). |
| `dr run deploy` fails with `MCP_SERVER_URL is not set` | `workflow.yaml` connects to `${MCP_SERVER_URL}`, and the project has no MCP server to take the URL from. | Set `MCP_SERVER_URL` in `.env` to the MCP server's URL. |
