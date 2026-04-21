# LLM provider fallback

LLM provider fallback adds automatic failover between LLM providers. If the primary model fails (rate limit, upstream outage, bad model ID, network error), requests are automatically retried against configured fallback models. This uses [litellm.Router](https://docs.litellm.ai/docs/routing) under the hood.

> [!NOTE]
> Requires `datarobot-genai >= 0.15.8`.

## DRAgent (workflow.yaml)

When using the DRAgent front server, fallback is configured entirely in `workflow.yaml`. Replace the standard `datarobot-llm-component` LLM block with `datarobot-llm-router`:

**Before:**

```yaml
llms:
  datarobot_llm:
    _type: datarobot-llm-component
```

**After:**

```yaml
llms:
  datarobot_llm:
    _type: datarobot-llm-router
    primary:
      llm_default_model: azure/gpt-5-mini-2025-08-07
      use_datarobot_llm_gateway: true
    fallbacks:
      - llm_default_model: anthropic/claude-opus-4-20250514
        use_datarobot_llm_gateway: true
    allowed_fails: 3
    cooldown_time: 60.0
```

No changes to `register.py` or `myagent.py` are required — NAT resolves the router-backed LLM and injects it into the agent automatically.

### Full workflow.yaml example

```yaml
general:
  front_end:
    _type: dragent_fastapi
    step_adaptor:
      mode: "off"
    a2a:
      server:
        name: "Blog Content Writer"
        description: "An AI content writing agent that researches and writes well-structured blog posts."
      skills:
        - id: write_blog
          name: "Write Blog Post"
          description: "Researches and writes a blog post on the given topic."

llms:
  datarobot_llm:
    _type: datarobot-llm-router
    primary:
      llm_default_model: azure/gpt-5-mini-2025-08-07
      use_datarobot_llm_gateway: true
    fallbacks:
      - llm_default_model: anthropic/claude-opus-4-20250514
        use_datarobot_llm_gateway: true
    allowed_fails: 3
    cooldown_time: 60.0

workflow:
  _type: langgraph_agent
  llm_name: datarobot_llm
  description: LangGraph planner/writer agent

authentication:
  datarobot_auth:
    _type: datarobot_api_key
```

## DRUM (myagent.py)

When using the DRUM front server, you modify `myagent.py` to build the router LLM in the `custompy_adaptor` function.

### Step 1: Add imports

Add the following imports to `myagent.py`:

```python
from datarobot_genai.core.config import LLMConfig
from datarobot_genai.langgraph.llm import get_router_llm
```

### Step 2: Update `custompy_adaptor`

Replace the `get_llm()` call with `get_router_llm()`. Define `LLMConfig` instances for the primary model and one or more fallbacks:

**Before:**

```python
async def custompy_adaptor(
    completion_create_params: CompletionCreateParams,
) -> InvokeReturn | tuple[str, Optional["MultiTurnSample"], UsageMetrics]:
    forwarded_headers = completion_create_params.get("forwarded_headers", {})
    authorization_context = completion_create_params.get("authorization_context", {})
    mcp_config = MCPConfig(
        forwarded_headers=forwarded_headers,
        authorization_context=authorization_context,
    )
    mcp_tools_factory = lambda: mcp_tools_context(mcp_config)
    model_name = completion_create_params.get("model")
    agent = MyAgent(
        llm=get_llm(
            model_name=model_name if model_name not in _PLACEHOLDER_MODELS else None
        ),
        verbose=completion_create_params.get("verbose", True),
        timeout=completion_create_params.get("timeout", 90),
        forwarded_headers=forwarded_headers,
    )
    return await agent_chat_completion_wrapper(
        agent, completion_create_params, mcp_tools_factory
    )
```

**After:**

```python
async def custompy_adaptor(
    completion_create_params: CompletionCreateParams,
) -> InvokeReturn | tuple[str, Optional["MultiTurnSample"], UsageMetrics]:
    forwarded_headers = completion_create_params.get("forwarded_headers", {})
    authorization_context = completion_create_params.get("authorization_context", {})
    mcp_config = MCPConfig(
        forwarded_headers=forwarded_headers,
        authorization_context=authorization_context,
    )
    mcp_tools_factory = lambda: mcp_tools_context(mcp_config)

    primary = LLMConfig(
        llm_default_model="azure/gpt-5-mini-2025-08-07",
        use_datarobot_llm_gateway=True,
    )
    fallbacks = [
        LLMConfig(
            llm_default_model="anthropic/claude-opus-4-20250514",
            use_datarobot_llm_gateway=True,
        ),
    ]
    router_settings = {"allowed_fails": 3, "cooldown_time": 60.0}

    agent = MyAgent(
        llm=get_router_llm(primary, fallbacks, router_settings),
        verbose=completion_create_params.get("verbose", True),
        timeout=completion_create_params.get("timeout", 90),
        forwarded_headers=forwarded_headers,
    )
    return await agent_chat_completion_wrapper(
        agent, completion_create_params, mcp_tools_factory
    )
```

The `get_router_llm` function returns a LangChain `BaseChatModel` that wraps a `litellm.Router` — it is a drop-in replacement for `get_llm()` and works with all existing agent code including streaming and tool calls.

### Step 3: Clean up unused import

Remove `get_llm` from the imports if it is no longer used:

```python
# Remove this line:
from datarobot_genai.langgraph.llm import get_llm
```

## LLM config options

Each `primary` and `fallbacks` entry accepts the following fields:

| Field | Type | Default | Description |
|---|---|---|---|
| `llm_default_model` | `str` | `None` | Model identifier (e.g. `azure/gpt-5-mini-2025-08-07`, `anthropic/claude-opus-4-20250514`). |
| `use_datarobot_llm_gateway` | `bool` | `true` | Route calls through the DataRobot LLM gateway. |
| `llm_deployment_id` | `str` | `None` | DataRobot LLM deployment ID (when not using the gateway). |
| `nim_deployment_id` | `str` | `None` | DataRobot NIM deployment ID. |
| `datarobot_endpoint` | `str` | From env | DataRobot API endpoint. Falls back to `DATAROBOT_ENDPOINT` env var. |
| `datarobot_api_token` | `str` | From env | DataRobot API token. Falls back to `DATAROBOT_API_TOKEN` env var. |

## Router settings

| Setting | Type | Default | Description |
|---|---|---|---|
| `allowed_fails` | `int` | `3` | Number of consecutive failures before a model enters cooldown. |
| `cooldown_time` | `float` | `None` | Seconds a failed model stays in cooldown before being retried. |

## How it works

The router creates a `litellm.Router` with a `primary` model and one or more named fallbacks (`fallback_0`, `fallback_1`, …). All requests are sent to `primary` first. If the primary fails (HTTP 429, 500, connection error, etc.), the router automatically retries with each fallback in order.

For LangGraph, the router is wrapped in a `RouterChatModel` — a LangChain `BaseChatModel` subclass that translates between LangChain message types and litellm's OpenAI-compatible format. This means:

- **Streaming** works out of the box — `_stream` and `_astream` are implemented.
- **Tool calling** works out of the box — tool call deltas are merged and converted to LangChain `ToolCall` objects.
- **All existing agent code** (graph factory, nodes, edges) requires no changes.

### Common configurations

**Same provider, different models** — failover from a newer model to a stable one:

```yaml
primary:
  llm_default_model: azure/gpt-5-mini-2025-08-07
  use_datarobot_llm_gateway: true
fallbacks:
  - llm_default_model: azure/gpt-4o-2024-11-20
    use_datarobot_llm_gateway: true
```

**Cross-provider** — failover from Azure to Anthropic:

```yaml
primary:
  llm_default_model: azure/gpt-5-mini-2025-08-07
  use_datarobot_llm_gateway: true
fallbacks:
  - llm_default_model: anthropic/claude-opus-4-20250514
    use_datarobot_llm_gateway: true
```

**Multiple fallbacks** — cascading failover chain:

```yaml
primary:
  llm_default_model: azure/gpt-5-mini-2025-08-07
  use_datarobot_llm_gateway: true
fallbacks:
  - llm_default_model: anthropic/claude-opus-4-20250514
    use_datarobot_llm_gateway: true
  - llm_default_model: azure/gpt-4o-2024-11-20
    use_datarobot_llm_gateway: true
allowed_fails: 1
cooldown_time: 30.0
```

**Deployment-based fallback** — failover between DataRobot LLM deployments:

```yaml
primary:
  llm_deployment_id: 6789abcdef0123456789abcd
  use_datarobot_llm_gateway: false
fallbacks:
  - llm_deployment_id: abcdef0123456789abcdef01
    use_datarobot_llm_gateway: false
```
