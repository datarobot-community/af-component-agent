# A2A authentication

This page outlines how to configure authentication for Agent-to-Agent (A2A) communication. There are two supported authentication methods:

1. DataRobot API key — A simple bearer token auth for DataRobot-hosted agents. Configured by default in all templates.
2. Okta cross-application access (XAA) — A two-step token exchange for federated Okta environments (hybrid RFC 8693 / RFC 7523 flow). Opt-in via `workflow.yaml`.

Both methods use the `authenticated_a2a_client` function group on the client side. See [Agent-to-Agent (A2A)](./agent2agent.md) for how to expose A2A endpoints and connect to remote agents.

## Option 1: DataRobot API key authentication

This is the default and requires no additional configuration. The `datarobot_auth` provider is already defined in all generated `workflow.yaml` files.

### How it works

On each A2A call, the `datarobot_api_key` auth provider injects `DATAROBOT_API_TOKEN` as an `Authorization: Bearer <token>` header. The A2A endpoint of the remote agent validates the token against the DataRobot platform.

### `workflow.yaml` configuration for DataRobot API key authentication

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
- `IDP_AGENT_ID` and `IDP_AGENT_PRIVATE_KEY_JWK` environment variables in the `.env` file (default), or the same values supplied via `principal_id` / `private_jwk` in `workflow.yaml` as described under [Environment variables](#environment-variables).

### Environment variables

| Variable | Description |
|----------|-------------|
| `IDP_AGENT_ID` | Okta AI agent principal ID used in the XAA token exchange flow (as `iss`/`sub` in JWT client assertions). Not used to check the audience of inbound tokens. To accept only tokens issued for this agent, see [Validate the inbound token audience](#validate-the-inbound-token-audience). |
| `IDP_AGENT_PRIVATE_KEY_JWK` | Base64-encoded or raw-JSON private JWK. Required for the XAA token exchange flow — the agent uses it to sign JWT client assertions for authentication and grant generation. |

Both load automatically from environment variables, `.env`, or DataRobot runtime parameters when `principal_id` or `private_jwk` are not set on the `okta_cross_app_access` block.

Alternatively, define `principal_id` and `private_jwk` directly under `authentication.okta_auth` (or whichever key holds `_type: okta_cross_app_access`) in `workflow.yaml`:

- Static values — Use a plain string for the Okta principal ID or for the private JWK (same formats as the `IDP_AGENT_ID` / `IDP_AGENT_PRIVATE_KEY_JWK` environment variables).
- Dynamic values — Use placeholders of the form `${VAR_NAME}` so the value is read from an environment variable at runtime when the workflow is loaded. This requires the `ENABLE_RUNTIME_PARAMETERS_IMPROVEMENTS` feature flag to be enabled in DataRobot so `${VAR_NAME}` entries in `workflow.yaml` are substituted from the environment.

### Installation

The `auth` extra is included in the generated `pyproject.toml` and provides the `okta-client-python` dependency. No additional installation steps are required.

### `workflow.yaml` configuration for Okta XAA

1. Enable XAA on the A2A server for this agent (server-side). Uncomment the `cross_application_access` block under `general.front_end.a2a`. To reject tokens issued for any other audience, also set `oauth_claim_validation: true`, as described in [Validate the inbound token audience](#validate-the-inbound-token-audience):

```yaml
general:
  front_end:
    _type: dragent_fastapi
    a2a:
      server:
        name: "My Agent"
        description: "My agent description."
      oauth_claim_validation: true
      cross_application_access:
        token_exchange:
          trusted_issuer: "https://your-org.okta.com"
          audience: "https://your-org.okta.com/oauth2/ausXXXXXXXXXXXXXXX"
        token_request:
          token_url: "https://your-org.okta.com/oauth2/ausXXXXXXXXXXXXXXX/v1/token"
          audience: "https://example.com/agents/my-agent-id"
          scopes:
            - "dr.impersonation"
```

2. Add the Okta auth provider (client-side). Uncomment the `okta_auth` block in the `authentication` section:

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

For the general runtime parameter mechanism, see [Runtime parameters](./runtime-parameters.md).

The infra module provisions `IDP_AGENT_ID` and `IDP_AGENT_PRIVATE_KEY_JWK` as runtime parameters automatically whenever the corresponding environment variables are set at `dr run deploy` time:

- `IDP_AGENT_ID` — Injected as a plain string runtime parameter from the `IDP_AGENT_ID` environment variable.
- `IDP_AGENT_PRIVATE_KEY_JWK` — Stored securely as a DataRobot credential (`ApiTokenCredential`) and injected as a `credential`-type runtime parameter from the `IDP_AGENT_PRIVATE_KEY_JWK` environment variable.

Set both in the `.env` file before running `dr run deploy`.

### How XAA works

The XAA flow operates in two steps:

1. Token Exchange (RFC 8693) — The incoming Okta access token from the caller is exchanged for an ID-JAG (Identity Assertion Authorization Grant) via the org-level Authorization Server (`token_exchange.trusted_issuer`).
2. JWT Bearer Grant (RFC 7523) — The ID-JAG is exchanged for a scoped access token at the resource AS token endpoint (`token_request.token_url`), granting access to the target agent with the requested scopes.

Both steps authenticate the client using a private JWT key, signing assertions with the key from `IDP_AGENT_PRIVATE_KEY_JWK`.

### Validate the inbound token audience

The DataRobot API gateway verifies that an inbound IdP token is well-formed and signed by a trusted issuer, then forwards it to the agent unchanged in the `x-datarobot-external-access-token` header. The gateway doesn't check which resource the token was issued for. Without audience validation, the agent accepts any trusted token, including one issued for a broader audience, such as the DataRobot base URL, or for a different agent.

To accept only tokens issued for this agent, set `oauth_claim_validation: true` under `general.front_end.a2a`. The agent then requires the token `aud` claim to contain the value of `cross_application_access.token_request.audience`:

```yaml
general:
  front_end:
    _type: dragent_fastapi
    a2a:
      oauth_claim_validation: true
      cross_application_access:
        token_request:
          audience: "https://example.com/agents/my-agent-id"
          # ...remaining cross_application_access fields
```

The check behaves as follows:

- **Opt-in**. Validation is off by default. Setting `IDP_AGENT_ID` or configuring `cross_application_access` doesn't turn it on.
- **Exact match**. One entry in the `aud` claim must equal `token_request.audience` exactly. Case and trailing slashes aren't normalized.
- **Every route**. The check covers every route the agent serves, not only `/a2a`. A request for the agent card that carries a token is validated before the card is returned.
- **IdP tokens only**. Requests authenticated with a DataRobot API key carry no IdP token and pass through. The agent doesn't re-verify signature, issuer, or expiry; the gateway checks those.
- **Fail fast**. When `oauth_claim_validation` is `true` and `token_request.audience` is unset, the agent fails at startup.

A request whose token audience doesn't match returns `401 Unauthorized`. A header value that isn't a decodable JWT returns `422 Unprocessable Entity`. The agent logs each rejection with `reason=audience_mismatch` or `reason=undecodable_token`, and an audience mismatch entry includes the expected and received audiences.

## Server-side configuration reference: `cross_application_access`

| Field | Required | Purpose |
|-------|----------|---------|
| `token_exchange.trusted_issuer` | Yes | Org-level Authorization Server issuer URL. |
| `token_exchange.audience` | Yes | Resource AS base URL (where ID-JAG is fetched from). |
| `token_request.token_url` | Yes | Token endpoint of the resource AS. |
| `token_request.audience` | Yes | Final resource identifier for the agent. |
| `token_request.scopes` | No | Scopes the caller must request. Defaults to `["read_data"]`. |

To enforce `token_request.audience` on inbound tokens, set `oauth_claim_validation: true` under `general.front_end.a2a`. See [Validate the inbound token audience](#validate-the-inbound-token-audience).

## Client-side configuration reference: `okta_cross_app_access`

| Field | Default | Purpose |
|-------|---------|---------|
| `okta_token_header` | `x-datarobot-external-access-token` | Incoming request header carrying the Okta access token from the caller. |
| `principal_id` | `IDP_AGENT_ID` environment variable | Okta AI agent principal ID used in JWT client assertions for the XAA exchange. |
| `private_jwk` | `IDP_AGENT_PRIVATE_KEY_JWK` environment variable | Private JWK used to sign JWT client assertions for the XAA exchange. |

Example with non-default options:

```yaml
authentication:
  okta_auth:
    _type: okta_cross_app_access
    okta_token_header: "x-custom-header"
    # principal_id: "my-agent-principal-id"  # Optional: override IDP_AGENT_ID environment variable
    # private_jwk: "..."                     # Optional: override IDP_AGENT_PRIVATE_KEY_JWK environment variable
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `RuntimeError: Header 'x-datarobot-external-access-token' not found` | The incoming request doesn't carry the Okta token. | Ensure the upstream caller forwards the Okta access token in the expected header. |
| `ValueError: principal_id is required` | `IDP_AGENT_ID` environment variable not set. | Set `IDP_AGENT_ID` in the `.env` file or runtime parameters. |
| `ValueError: Could not parse private_jwk` | `IDP_AGENT_PRIVATE_KEY_JWK` is neither valid base64-encoded JSON nor raw JSON. | Verify the JWK — try `echo $IDP_AGENT_PRIVATE_KEY_JWK | base64 -d | python -m json.tool`. |
| `ValueError: Agent card ... missing required fields` | Remote agent card doesn't have the XAA extension. | Verify the remote agent has `cross_application_access` configured in its `workflow.yaml`. |
| `RuntimeError: Failed to fetch agent card` | Network/auth issue reaching the agent card URL. | Check the `url` in the `function_groups` config and network connectivity. |
| `GET /.well-known/agent-card.json` returns 401 when testing locally | Unauthenticated access is disabled by default (`datarobot-genai` 0.27.0+). | Send `X-DataRobot-User-Id` (any value) or `X-DataRobot-Authorization-Context` for the full card, or set `enable_unauthenticated_well_known_route: true` in `workflow.yaml` to allow a redacted card. See [Debugging agents → Local agent card](./debugging.md#local-agent-card). |
| Agent card shows `"skills": []` when testing locally | Unauthenticated request with `enable_unauthenticated_well_known_route: true` returns a redacted card. | Send `X-DataRobot-User-Id` (any value) or `X-DataRobot-Authorization-Context` on the request for the full card. See [Debugging agents → Local agent card](./debugging.md#local-agent-card). |
| The agent accepts a trusted token issued for a different audience | `oauth_claim_validation` is off, which is the default. | Set `oauth_claim_validation: true` under `general.front_end.a2a`. See [Validate the inbound token audience](#validate-the-inbound-token-audience). |
| `401 {"detail": "Authorization audience claim validation failed"}` | The token `aud` claim doesn't exactly match `cross_application_access.token_request.audience`. | Compare `expected_audience` and `token_aud` in the `audience_mismatch` log entry, then align the Okta resource audience or `token_request.audience`. |
| `422` with `Malformed authorization token` | The `x-datarobot-external-access-token` header doesn't hold a decodable JWT. | Ensure the caller forwards the Okta access token, not another credential, in that header. |
| `ValueError: a2a.oauth_claim_validation is true but no expected audience is configured` | `oauth_claim_validation` is `true`, but `cross_application_access.token_request.audience` is unset. | Set `token_request.audience`, or set `oauth_claim_validation` to `false`. |
| `IDP_AGENT_PRIVATE_KEY_JWK` not provisioned to runtime | The variable was not set in `.env` at deploy time. | Set `IDP_AGENT_PRIVATE_KEY_JWK` in the `.env` file and redeploy. |
