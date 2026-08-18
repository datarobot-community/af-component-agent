# Application config authority migration

This guide covers the change that makes `agent/config.py` the authoritative configuration for the
whole application, including `datarobot-genai`. It ships with `datarobot-genai` 0.28.0.

## Summary

`datarobot-genai` used to read LLM configuration straight from the environment through a config class
of its own. `agent/config.py` looked authoritative but was not: renaming a field or changing a default
there had no effect on the LLM the agent actually built, because the library never looked at it.

Now the application registers its `Config` with the library, and the library resolves everything
through it:

| | Where LLM settings come from |
|---|---|
| **Before** | `datarobot-genai`'s own config class, reading the environment directly |
| **After** | `Config` in `agent/config.py`, which the library resolves through |

Two consequences:

- A field added to `Config`, or a default changed there, is what the agent runs with.
- LLM settings are namespaced by the name of the LLM component (`llm` by default), so a project can
  configure more than one LLM. Each component's settings are resolved independently by name.

The registration itself lives in `agent/__init__.py` and is two lines. Nothing needs to be registered
per LLM: call `Config().resolve_llm_config(name="llm")` wherever a specific LLM's connection details
are needed.

## Migration steps

### 1. Rename the LLM fields in `agent/config.py`

The per-LLM fields carry the LLM component's name as a prefix. For the default component name `llm`,
two of the four fields change:

**Before:**

```python
llm_deployment_id: str | None = None
llm_default_model: str = "datarobot/azure/gpt-5-mini-2025-08-07"
use_datarobot_llm_gateway: bool = False
```

**After:**

```python
llm_deployment_id: str | None = None
llm_default_model: str = "datarobot/azure/gpt-5-mini-2025-08-07"
llm_nim_deployment_id: str | None = None
llm_use_datarobot_llm_gateway: bool = True
```

Also add the DataRobot connection and the two `datarobot-genai` tunables, so the class covers
everything the library resolves:

```python
datarobot_endpoint: str = "https://app.datarobot.com/api/v2"
datarobot_api_token: str | None = None
max_history_messages: int = Field(
    default=20, ge=0, alias="datarobot_genai_max_history_messages"
)
assume_native_tool_calling_when_unmapped: bool = False
```

`llm_use_datarobot_llm_gateway` defaults to `true`, matching the library's long-standing default. The
old `use_datarobot_llm_gateway: bool = False` field looked like it defaulted routing to a deployment,
but the library never read it, so this is not a behavior change. Set it to `false` explicitly when
routing to a deployment or an external provider.

### 2. Register `Config` in `agent/__init__.py`

```python
from datarobot_genai.core.config import register_config_provider

from agent.config import Config

register_config_provider(Config, default_llm_name="llm")

from agent.myagent import MyAgent  # noqa: E402
```

The import of `agent.myagent` stays below the call: agent code may build an LLM at import time, and it
has to see the registered config when it does. Projects on the NAT framework have no `myagent.py` and
so no import to move.

Remove any `register_config_provider` call left in `agent/config.py`.

### 3. Rename the runtime parameters and environment variables

| Before | After |
|---|---|
| `USE_DATAROBOT_LLM_GATEWAY` | `LLM_USE_DATAROBOT_LLM_GATEWAY` |
| `NIM_DEPLOYMENT_ID` | `LLM_NIM_DEPLOYMENT_ID` |

`LLM_DEPLOYMENT_ID` and `LLM_DEFAULT_MODEL` are unchanged. Rename them in `.env`, in any CI
environment, and anywhere your own infrastructure code sets them.

The LLM component emits the new names from version **11.11.7** onward, so `dr dotenv setup` and
`pulumi up` write them for you once it is up to date. Update the LLM component alongside the agent
component: on an older LLM component the namespaced routing flag is never set, and
`llm_use_datarobot_llm_gateway` falls back to its `true` default, which sends an agent that should
call its own deployment to the LLM Gateway instead.

### 4. Rename the router fields in `workflow.yaml`

Entries under `primary` and `fallbacks` of a `datarobot-llm-router` block are `LLMConfig` objects, and
their field names are namespaced the same way:

```yaml
llms:
  datarobot_llm:
    _type: datarobot-llm-router
    primary:
      llm_use_datarobot_llm_gateway: true
      llm_default_model: azure/gpt-5-mini-2025-08-07
    fallbacks:
      - llm_use_datarobot_llm_gateway: true
        llm_default_model: anthropic/claude-opus-4-20250514
```

YAML has no deprecation fallback: an unrenamed field is ignored and the entry silently reverts to its
default. Check any `datarobot-llm-router` block you have. See
[LLM provider fallback](./llm-fallback.md).

### 5. Search for stale names

```sh
rg 'USE_DATAROBOT_LLM_GATEWAY|NIM_DEPLOYMENT_ID' . | rg -v 'LLM_USE_DATAROBOT_LLM_GATEWAY|LLM_NIM_DEPLOYMENT_ID'
```

## Adding a second LLM

Give the second component its own name, add its fields under that name, and resolve it where you need
it:

```python
# agent/config.py
class Config(DataRobotAppFrameworkBaseSettings):
    llm_deployment_id: str | None = None
    llm_default_model: str = "datarobot/azure/gpt-5-mini-2025-08-07"
    llm_nim_deployment_id: str | None = None
    llm_use_datarobot_llm_gateway: bool = True

    summarizer_deployment_id: str | None = None
    summarizer_default_model: str = "datarobot/anthropic/claude-opus-4-20250514"
    summarizer_nim_deployment_id: str | None = None
    summarizer_use_datarobot_llm_gateway: bool = True
```

```python
from agent.config import Config

summarizer = Config().resolve_llm_config(name="summarizer")
```

The name passed to `register_config_provider` in `agent/__init__.py` is only the default, used by call
sites that do not name an LLM themselves.
