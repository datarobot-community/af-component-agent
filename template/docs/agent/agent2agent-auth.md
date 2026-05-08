# A2A Authentication

This page outlines how to configure authentication for Agent-to-Agent (A2A) communication. There are two supported authentication methods:

1. **DataRobot API key** — A simple bearer token auth for DataRobot-hosted agents. Configured by default in all templates.
2. **Okta cross-application access (XAA)** — A two-step token exchange for federated Okta environments (hybrid RFC 8693 / RFC 7523 flow). Opt-in via `workflow.yaml`.

Both methods use the `authenticated_a2a_client` function group on the client side. See [Agent2Agent](./agent2agent.md) for how to expose A2A endpoints and connect to remote agents.

## Option 1: DataRobot API key authentication

This is the default and requires no additional configuration. The `datarobot_auth` provider is already defined in all generated `workflow.yaml` files.

### How it works

On each A2A call, the `datarobot_api_key` auth provider injects `DATAROBOT_API_TOKEN` as an `Authorization: Bearer <token>` header. The remote agent's A2A endpoint validates the token against the DataRobot platform.

### `workflow.yaml`

The template already includes this configuration:

```yaml
authentication:
  datarobot_auth:
    _type: datarobot_api_key
```

To connect to a remote agent using DataRobot API key auth, uncomment the `remote_agent` block in `workflow.yaml`:

```yaml
function_groups:
  remote_agent:
    _type: authenticated_a2a_client
    url: "https://app.datarobot.com/api/v2/deployments/<deployment-id>/directAccess/a2a/"
    auth_provider: datarobot_auth
```

## Option 2: Okta cross-application access (XAA)

Use this when calling an agent protected by Okta's federated identity model. The flow obtains a scoped access token through a two-step exchange.

### Prerequisites

- An Okta organization with Cross-Application Access enabled.
- A registered AI agent principal in Okta with a private key pair.
- `PRINCIPAL_ID` and `PRIVATE_JWK` environment variables set in your `.env` file.

### Environment variables

| Variable | Description |
|----------|-------------|
| `PRINCIPAL_ID` | Okta AI agent principal ID (used as `iss`/`sub` in JWT client assertions). |
| `PRIVATE_JWK` | Base64-encoded or raw-JSON private JWK (signs JWT client assertions). |

Both are loaded automatically from env vars, `.env`, or DataRobot Runtime Parameters.

### Installation

The `auth` extra is included in the generated `pyproject.toml` and provides the `okta-client-python` dependency. No additional installation steps are required.

### `workflow.yaml` configuration

1. Enable XAA on this agent's A2A server (server-side). Uncomment the `cross_application_access` block under `general.front_end.a2a`:

```yaml
general:
  front_end:
    _type: dragent_fastapi
    a2a:
      server:
        name: "My Agent"
        description: "My agent description."
      cross_application_access:
        token_exchange:
          trusted_issuer: "https://your-org.okta.com"
          audience: "https://your-org.okta.com/oauth2/ausXXXXXXXXXXXXXXX"
        token_request:
          token_url: "https://your-org.okta.com/oauth2/ausXXXXXXXXXXXXXXX/v1/token"
          audience: "https://app.datarobot.com/<org_id>/<agent_id>"
          scopes:
            - "read_data"
```

**Step 2** — Add the Okta auth provider (client-side). Uncomment the `okta_auth` block in the `authentication` section:

```yaml
authentication:
  datarobot_auth:
    _type: datarobot_api_key
  okta_auth:
    _type: okta_cross_app_access
```

3. Connect to a remote XAA-protected agent. Uncomment and configure the `remote_agent` function group:

```yaml
function_groups:
  remote_agent:
    _type: authenticated_a2a_client
    url: "https://app.datarobot.com/api/v2/deployments/<deployment-id>/directAccess/a2a/"
    auth_provider: okta_auth
```

### Infrastructure: automatic runtime parameter provisioning

When `cross_application_access` is configured in `workflow.yaml`, the infra module automatically detects it and provisions the required runtime parameters on deployment:

- `PRINCIPAL_ID` — Injected as a plain string runtime parameter from the `PRINCIPAL_ID` environment variable.
- `PRIVATE_JWK` — Stored securely as a DataRobot credential (`ApiTokenCredential`) and injected as a `credential`-type runtime parameter from the `PRIVATE_JWK` environment variable.

Set both in your `.env` file before running `dr run deploy`.

### How XAA works

The XAA flow operates in two steps:

1. **Token Exchange (RFC 8693)** — The caller's incoming Okta access token is exchanged for an ID-JAG (Identity Assertion Authorization Grant) via the org-level Authorization Server (`token_exchange.trusted_issuer`).
2. **JWT Bearer Grant (RFC 7523)** — The ID-JAG is exchanged for a scoped access token at the resource AS token endpoint (`token_request.token_url`), granting access to the target agent with the requested scopes.

Both steps authenticate the client using a private JWT key, signing assertions with the key from `PRIVATE_JWK`.

## Server-side configuration reference: `cross_application_access`

| Field | Required | Purpose |
|-------|----------|---------|
| `token_exchange.trusted_issuer` | Yes | Org-level Authorization Server issuer URL. |
| `token_exchange.audience` | Yes | Resource AS base URL (where ID-JAG is fetched from). |
| `token_request.token_url` | Yes | Token endpoint of the resource AS. |
| `token_request.audience` | Yes | Final resource identifier for the agent. |
| `token_request.scopes` | No | Scopes the caller must request. Defaults to `["read_data"]`. |

## Client-side configuration reference: `okta_cross_app_access`

| Field | Default | Purpose |
|-------|---------|---------|
| `okta_token_header` | `x-datarobot-okta-access-token` | Incoming request header carrying the caller's Okta access token. |
| `principal_id` | `PRINCIPAL_ID` env var | Okta AI agent principal ID. |
| `private_jwk` | `PRIVATE_JWK` env var | Base64-encoded or raw-JSON private JWK. |
| `id_jag_scopes` | `["read_data"]` | Scopes for the Step 1 ID-JAG request. |

Example with non-default options:

```yaml
authentication:
  okta_auth:
    _type: okta_cross_app_access
    okta_token_header: "x-custom-header"
    id_jag_scopes: ["openid", "profile"]
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `RuntimeError: Header 'x-datarobot-okta-access-token' not found` | The incoming request doesn't carry the Okta token. | Ensure the upstream caller forwards the Okta access token in the expected header. |
| `ValueError: principal_id is required` | `PRINCIPAL_ID` env var not set. | Set `PRINCIPAL_ID` in your `.env` file or Runtime Parameters. |
| `ValueError: Could not parse private_jwk` | `PRIVATE_JWK` is neither valid base64-encoded JSON nor raw JSON. | Verify your JWK — try `echo $PRIVATE_JWK | base64 -d | python -m json.tool`. |
| `ValueError: Agent card ... missing required fields` | Remote agent card doesn't have the XAA extension. | Verify the remote agent has `cross_application_access` configured in its `workflow.yaml`. |
| `RuntimeError: Failed to fetch agent card` | Network/auth issue reaching the agent card URL. | Check the `url` in your `function_groups` config and network connectivity. |
| PRIVATE_JWK not provisioned to runtime | `cross_application_access` not present in `workflow.yaml` at deploy time. | Ensure `workflow.yaml` has the `cross_application_access` block uncommented before deploying. |
