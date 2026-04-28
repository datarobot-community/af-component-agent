# LLM provider fallback

The agent component supports configuring primary and fallback LLM providers so that if the primary provider is unavailable or returns an error, the agent automatically retries using a fallback provider. This is powered by [litellm.Router](https://docs.litellm.ai/docs/routing) and requires `datarobot-genai>=0.15.20`.

There are two integration paths depending on your front server:

| Path | Front server | How to configure |
|---|---|---|
| [DRAgent (workflow.yaml)](#dragent-workflowyaml) | DRAgent | Replace `_type: datarobot-llm-component` with `_type: datarobot-llm-router` |
| [DRUM (myagent.py)](#drum-myagentpy) | DRUM | Replace `get_llm()` with `get_router_llm()` |

---

## DRAgent (workflow.yaml)

In `workflow.yaml`, replace the `datarobot-llm-component` block with `datarobot-llm-router` and define a `primary` and one or more `fallbacks`:

```yaml
llms:
  datarobot_llm:
    _type: datarobot-llm-router
    primary:
      use_datarobot_llm_gateway: true
      llm_default_model: azure/gpt-4o-2024-11-20
    fallbacks:
      - use_datarobot_llm_gateway: true
        llm_default_model: anthropic/claude-opus-4-20250514
    num_retries: 3

workflow:
  _type: langgraph_agent  # or crewai_agent / llamaindex_agent / per_user_tool_calling_agent
  llm_name: datarobot_llm
```

The `workflow` block remains unchanged — only the `llms` block needs to be updated.

### LLMConfig fields

Each entry under `primary` and `fallbacks` is an `LLMConfig` with these fields:

| Field | Type | Description |
|---|---|---|
| `use_datarobot_llm_gateway` | `bool` | `true` = route through DataRobot LLM Gateway (default). `false` = use a deployment or external provider. |
| `llm_default_model` | `str` | Model string (e.g. `azure/gpt-4o-2024-11-20`, `anthropic/claude-opus-4-20250514`). |
| `llm_deployment_id` | `str \| None` | DataRobot deployment ID when routing to a deployed LLM (overrides env). |
| `nim_deployment_id` | `str \| None` | DataRobot deployment ID for NIM-based routing. |
| `datarobot_endpoint` | `str \| None` | Per-entry DataRobot endpoint URL override. |
| `datarobot_api_token` | `str \| None` | Per-entry API token override. |

### Router-level fields

| Field | Type | Default | Description |
|---|---|---|---|
| `num_retries` | `int` | `3` | Number of retries per model before moving to the next fallback. |

---

## DRUM (myagent.py)

When using the DRUM front server, replace `get_llm()` with `get_router_llm()` in `custompy_adaptor`:

```python
from datarobot_genai.core.config import LLMConfig
from datarobot_genai.langgraph.llm import get_router_llm  # or crewai / llama_index

primary = LLMConfig(
    use_datarobot_llm_gateway=True,
    llm_default_model="azure/gpt-4o-2024-11-20",
)
fallbacks = [
    LLMConfig(
        use_datarobot_llm_gateway=True,
        llm_default_model="anthropic/claude-opus-4-20250514",
    )
]

# In custompy_adaptor:
agent = MyAgent(
    llm=get_router_llm(primary, fallbacks, {"num_retries": 3}),
    ...
)
```

Import paths per framework:

| Framework | Import |
|---|---|
| LangGraph | `from datarobot_genai.langgraph.llm import get_router_llm` |
| CrewAI | `from datarobot_genai.crewai.llm import get_router_llm` |
| LlamaIndex | `from datarobot_genai.llama_index.llm import get_router_llm` |

---

## How fallback works

When the primary model fails (network error, rate limit, model error), `litellm.Router` retries up to `num_retries` times, then moves to the next fallback in order. Each `LLMConfig` entry is independently translated to a litellm model entry, so primary and fallbacks can point to entirely different providers and models.
