# Runtime parameters

Runtime parameters are the mechanism DataRobot uses to configure a deployed custom model without changing code. They consist of a key/value entry declared under `runtimeParameterDefinitions` in `model-metadata.yaml` for the custom model. This file is generated automatically — never hand-edited — by `_generate_metadata_yaml()` in `infra/infra/<agent_app_name>.py` from the list of `pulumi_datarobot.CustomModelRuntimeParameterValueArgs` entries built during `dr run deploy`.

Each entry has a `type` that determines how it is exposed to the running deployment:

| Type | Description |
|---|---|
| `string` | A plain text value, exposed to the running deployment as an environment variable named after the runtime parameter key. |
| `numeric` | A numeric value, also exposed as an environment variable named after the runtime parameter key. |
| `credential` | A value backed by a DataRobot credential object (for example, an `ApiTokenCredential`) rather than a plain string. Used for secrets so they aren't stored as raw text on the custom model, and are exposed as a DataRobot credential ID rather than a raw string value. |

Once deployed, the value of a runtime parameter can be viewed and edited directly on the registered model or deployment in DataRobot — no redeploy of code is required to change it. This is what distinguishes a runtime parameter from a plain environment variable that only exists in the local shell or `.env` file, or a Python-level default baked into the build.

The `Config` class in `agent/config.py` reads runtime parameters the same way it reads any other environment variable — see [Configuration](./README.md#configuration) for the full priority order (env variables including runtime parameters, then `.env`, then file secrets, then Pulumi output variables).

## Default runtime parameters

This component provisions the following runtime parameters automatically during `dr run deploy`:

| Runtime parameter | Type | Source | Description |
|---|---|---|---|
| `CUSTOM_MODEL_WORKERS` | numeric | `infra/infra/<agent_app_name>.py` | Number of Gunicorn workers for the deployed agent. `2` by default, `5` when `ENABLE_AGENT_HA_MODE=true` is set at deploy time (see [Deploy-time infra variables are not runtime parameters](#deploy-time-infra-variables-are-not-runtime-parameters)). |
| `AGENT_GUNICORN_WORKER_TIMEOUT` | string | `infra/infra/<agent_app_name>.py` | Gunicorn worker timeout in seconds. Defaults to `600`, raised above Gunicorn's 30s default so long agent turns aren't killed mid-stream. |
| `LLM_DEPLOYMENT_ID`, `LLM_DEFAULT_MODEL`, `LLM_NIM_DEPLOYMENT_ID`, `LLM_USE_DATAROBOT_LLM_GATEWAY` (namespaced per LLM component) | string | The `llm` component's own infra module | LLM routing configuration. See [Configuration](./README.md#configuration) for the full variable table and [LLM component](../llm.md) for details. |
| `MCP_DEPLOYMENT_ID`, `EXTERNAL_MCP_URL`, `EXTERNAL_MCP_HEADERS` | string | `get_mcp_runtime_parameters_from_env()` in `infra/infra/<agent_app_name>.py` | MCP server connection details, when an MCP deployment or external MCP URL is configured. See [MCP server](../mcp-server.md). |

The following are provisioned conditionally, depending on which optional features are enabled for the project. Their tables appear on the pages that document those features rather than being duplicated here:

| Runtime parameter | Type | When provisioned | Documented in |
|---|---|---|---|
| `AGENT_MEMORY_TTL_DAYS` | string | `use_agent_memory` is set to `mem0` or `datarobot_memory_service` | [Agent memory: Configuration and runtime parameters](./agent-memory.md#configuration-and-runtime-parameters) |
| `AGENT_MEMORY_SPACE_ID` | string | `use_agent_memory: datarobot_memory_service` | [Agent memory: Configuration and runtime parameters](./agent-memory.md#configuration-and-runtime-parameters) |
| `MEM0_API_KEY` | credential | `use_agent_memory: mem0`, and `MEM0_API_KEY` is set in the Pulumi environment | [Agent memory: Configuration and runtime parameters](./agent-memory.md#configuration-and-runtime-parameters) |
| `SESSION_SECRET_KEY` | credential | `SESSION_SECRET_KEY` is set in the Pulumi environment | `infra/infra/<agent_app_name>.py` |
| `IDP_AGENT_ID` | string | A2A XAA auth is configured and `IDP_AGENT_ID` is set | [A2A Authentication: Infrastructure](./agent2agent-auth.md#infrastructure-automatic-runtime-parameter-provisioning) |
| `IDP_AGENT_PRIVATE_KEY_JWK` | credential | A2A XAA auth is configured and `IDP_AGENT_PRIVATE_KEY_JWK` is set | [A2A Authentication: Infrastructure](./agent2agent-auth.md#infrastructure-automatic-runtime-parameter-provisioning) |

Only parameters listed in the `SERVER_PARAMS_WITH_DEFAULTS` allowlist (`CUSTOM_MODEL_WORKERS` and `AGENT_GUNICORN_WORKER_TIMEOUT`) get a `defaultValue` written into `model-metadata.yaml`; all other parameters must have their value supplied at deploy time.

## Deploy-time infra variables are not runtime parameters

Some environment variables only control what `infra/infra/<agent_app_name>.py` does while `dr run deploy` runs — they shape values that get baked into runtime parameters or deployment settings, but are never themselves registered as a runtime parameter and can't be edited later without redeploying.

`ENABLE_AGENT_HA_MODE` is the main example: set `ENABLE_AGENT_HA_MODE=true` in the `.env` file or Pulumi environment to switch the deployment to a high-availability profile (`CUSTOM_MODEL_WORKERS=5`, `cpu.3xlarge` resource bundle, 2 replicas, autoscaling up to 4 computes) versus the default (`CUSTOM_MODEL_WORKERS=2`, `cpu.xlarge`, 1 replica, autoscaling up to 2 computes). `ENABLE_AGENT_HA_MODE` itself never appears in `model-metadata.yaml` — only the derived `CUSTOM_MODEL_WORKERS` runtime parameter does.

## Overriding values

Override the value of a runtime parameter depending on when the change needs to take effect:

- **Local development** — set the variable in the project `.env` file. `Config` picks it up directly; no deploy is needed.
- **At deploy time** — set the variable in the environment that `dr run deploy` (Pulumi) runs in. This is how `MEM0_API_KEY`, `SESSION_SECRET_KEY`, `IDP_AGENT_ID`, and `IDP_AGENT_PRIVATE_KEY_JWK` are provisioned — the infra script reads them from `os.environ` at deploy time and creates the corresponding runtime parameter (and DataRobot credential, for `credential`-type parameters).
- **After deployment** — edit the value directly on the registered model or deployment in DataRobot. This updates the runtime parameter without requiring a code change or redeploy, and is the fastest way to tune something like `AGENT_GUNICORN_WORKER_TIMEOUT` in a live environment.

## Add a custom runtime parameter

Adding a custom runtime parameter has two parts: a `Config` field so the agent code can read it, and an infra registration so it is declared on the deployed custom model.

1. Add a field to `Config` in `agent/config.py`. A field named `foo_bar` is read from `FOO_BAR` (environment variable, runtime parameter, `.env`, file secret, or Pulumi output):

   ```python
   class Config(DataRobotAppFrameworkBaseSettings):
       ...
       foo_bar: str | None = None
   ```

2. Register it in infra so it is included in `model-metadata.yaml` and provisioned by Pulumi. In `infra/infra/<agent_app_name>.py`, append to `agent_runtime_parameter_values`.

   A plain string value:

   ```python
   agent_runtime_parameter_values.append(
       pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
           key="FOO_BAR",
           type="string",
           value=os.environ.get("FOO_BAR", "default-value"),
       )
   )
   ```

   A secret, stored as a DataRobot credential:

   ```python
   if foo_bar_secret := os.environ.get("FOO_BAR_SECRET"):
       foo_bar_cred = pulumi_datarobot.ApiTokenCredential(
           agent_asset_name + " Foo Bar Secret",
           args=pulumi_datarobot.ApiTokenCredentialArgs(api_token=str(foo_bar_secret)),
       )
       agent_runtime_parameter_values.append(
           pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
               type="credential",
               key="FOO_BAR_SECRET",
               value=foo_bar_cred.id,
           ),
       )
   ```

   If the value is safe to publish as a default (not a secret, and meaningful without deploy-time context), add its key to `SERVER_PARAMS_WITH_DEFAULTS` so it is written into the `defaultValue` field in `model-metadata.yaml`. This sets a default value for the runtime parameter that is used when no value is provided at deploy time.

For a complete worked example of a conditional, feature-gated runtime parameter (including a `credential`-type one), see the memory space and Mem0 provisioning in [Agent memory: Infrastructure provisioning](./agent-memory.md#infrastructure-provisioning).
