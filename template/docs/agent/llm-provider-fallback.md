# LLM provider fallback

LLM provider fallback adds automatic failover between LLM providers. If the primary model fails (rate limit, upstream outage, bad model ID, network error), requests are automatically retried against configured fallback models. This uses [litellm.Router](https://docs.litellm.ai/docs/routing) under the hood.

> [!NOTE]
> This guide implements fallback manually using the current `datarobot-genai` package. Once `datarobot-genai >= 0.15.8` is released, you can simplify to a declarative configuration (see [Simplified approach with datarobot-genai 0.15.8+](#simplified-approach-with-datarobot-genai-0158) at the end).

## DRAgent (register.py + workflow.yaml)

When using the DRAgent front server, manually build the `litellm.Router` in `register.py` and pass it to the agent.

### Step 1: Update `workflow.yaml`

Extend your workflow config to include fallback model definitions:

```yaml
general:
  front_end:
    _type: dragent_fastapi
    step_adaptor:
      mode: "off"

llms:
  datarobot_llm:
    _type: datarobot-llm-component

# Add fallback model config as custom data (not yet a NAT LLM provider)
fallback_config:
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

### Step 2: Update `register.py`

Modify the `langgraph_agent` function to build a `litellm.Router` and pass it to `MyAgent`:

```python
import litellm
from nat.builder.builder import Builder
from nat.builder.function import FunctionInfo
from nat.cli.register_workflow import register_per_user_function
from nat.core.config_manager import get_config_manager
from typing import Any, AsyncGenerator

# ... other imports ...

@register_per_user_function(
    config_type=LanggraphAgentConfig,
    input_type=RunAgentInput,
    streaming_output_type=DRAgentEventResponse,
    framework_wrappers=[LLMFrameworkEnum.LANGCHAIN],
)
async def langgraph_agent(config: LanggraphAgentConfig, builder: Builder) -> AsyncGenerator[Any, None]:
    from agent.myagent import MyAgent

    llm = await builder.get_llm(config.llm_name, wrapper_type=LLMFrameworkEnum.LANGCHAIN)
    workflow_tools = await builder.get_tools(config.tool_names, wrapper_type=LLMFrameworkEnum.LANGCHAIN)

    # Load fallback config from workflow.yaml if present
    config_mgr = get_config_manager()
    fallback_cfg = config_mgr.get("fallback_config")
    
    if fallback_cfg:
        # Build litellm router with fallback support
        router = _build_litellm_router(fallback_cfg)
        llm_to_use = router
    else:
        llm_to_use = llm

    async def _response_fn(input_message: RunAgentInput):
        forwarded_headers = extract_datarobot_headers_from_context()
        authorization_context = extract_authorization_from_context()
        mcp_config = MCPConfig(
            forwarded_headers=forwarded_headers,
            authorization_context=authorization_context,
        )
        async with mcp_tools_context(mcp_config) as mcp_tools:
            tools = workflow_tools + mcp_tools
            agent = MyAgent(
                llm=llm_to_use,
                verbose=config.verbose,
                forwarded_headers=forwarded_headers,
                tools=tools,
            )
            async for event, pipeline_interactions, usage_metrics in agent.invoke(input_message):
                yield DRAgentEventResponse(
                    events=[event],
                    usage_metrics=usage_metrics,
                    pipeline_interactions=pipeline_interactions,
                )

    yield FunctionInfo.from_fn(_response_fn, description=config.description)


def _build_litellm_router(fallback_cfg: dict) -> litellm.Router:
    """Build a litellm.Router from fallback config."""
    from datarobot_genai.core.config import Config
    
    def _to_litellm_params(llm_cfg: dict) -> dict:
        """Convert LLM config dict to litellm params."""
        env_config = Config()
        endpoint = (
            llm_cfg.get("datarobot_endpoint") 
            or env_config.datarobot_endpoint
        )
        api_key = (
            llm_cfg.get("datarobot_api_token") 
            or env_config.datarobot_api_token
        )
        model_name = llm_cfg.get("llm_default_model") or "datarobot-deployed-llm"
        
        if llm_cfg.get("use_datarobot_llm_gateway", True):
            return {
                "model": f"datarobot/{model_name}" if not model_name.startswith("datarobot/") else model_name,
                "api_base": f"{endpoint.rstrip('/')}/v1/chat/completions",
                "api_key": api_key,
            }
        else:
            # Deployment or NIM based
            deployment_id = llm_cfg.get("llm_deployment_id") or llm_cfg.get("nim_deployment_id")
            if deployment_id:
                return {
                    "model": f"datarobot/{model_name}" if not model_name.startswith("datarobot/") else model_name,
                    "api_base": f"{endpoint.rstrip('/')}/deployments/{deployment_id}/v1",
                    "api_key": api_key,
                }
            else:
                return {
                    "model": model_name,
                    "api_key": api_key,
                }
    
    primary_params = _to_litellm_params(fallback_cfg["primary"])
    fallback_params = [
        _to_litellm_params(fb) for fb in fallback_cfg.get("fallbacks", [])
    ]
    
    model_list = [
        {"model_name": "primary", "litellm_params": primary_params},
        *[
            {"model_name": f"fallback_{i}", "litellm_params": p}
            for i, p in enumerate(fallback_params)
        ],
    ]
    
    router_settings = {
        "allowed_fails": fallback_cfg.get("allowed_fails", 3),
    }
    if fallback_cfg.get("cooldown_time") is not None:
        router_settings["cooldown_time"] = fallback_cfg["cooldown_time"]
    
    return litellm.Router(
        model_list=model_list,
        fallbacks=[{"primary": [f"fallback_{i}" for i in range(len(fallback_params))]}],
        **router_settings,
    )
```

The `MyAgent` class in `myagent.py` requires no changes — it accepts any `BaseChatModel`, and `litellm.Router` can be used directly as a drop-in replacement for the LLM when passed to the agent constructor (it implements the OpenAI-compatible interface).

## DRUM (myagent.py + custom.py)

When using the DRUM front server, manually build the `litellm.Router` in the `custompy_adaptor` function in `myagent.py`.

### Step 1: Add imports

Add the following imports to `myagent.py`:

```python
import litellm
from datarobot_genai.core.config import Config
```

### Step 2: Create router builder helper

Add a helper function to build the router (place it in `myagent.py` or a separate module):

```python
def _build_litellm_router_for_langgraph(
    primary_model: str,
    fallback_models: list[str],
    use_datarobot_gateway: bool = True,
    allowed_fails: int = 3,
    cooldown_time: float | None = None,
) -> Any:  # litellm.Router
    """Build a litellm.Router with fallback support for LangGraph agents."""
    import litellm
    from langchain_core.language_models import BaseChatModel
    from langchain_core.outputs import ChatResult
    from langchain_core.messages import AIMessage, BaseMessage
    
    env_config = Config()
    
    def _get_api_base(endpoint: str) -> str:
        return f"{endpoint.rstrip('/')}/v1/chat/completions"
    
    endpoint = env_config.datarobot_endpoint
    api_key = env_config.datarobot_api_token
    
    model_list = [
        {
            "model_name": "primary",
            "litellm_params": {
                "model": f"datarobot/{primary_model}" if not primary_model.startswith("datarobot/") else primary_model,
                "api_base": _get_api_base(endpoint),
                "api_key": api_key,
            },
        },
        *[
            {
                "model_name": f"fallback_{i}",
                "litellm_params": {
                    "model": f"datarobot/{model}" if not model.startswith("datarobot/") else model,
                    "api_base": _get_api_base(endpoint),
                    "api_key": api_key,
                },
            }
            for i, model in enumerate(fallback_models)
        ],
    ]
    
    router_settings = {"allowed_fails": allowed_fails}
    if cooldown_time is not None:
        router_settings["cooldown_time"] = cooldown_time
    
    router = litellm.Router(
        model_list=model_list,
        fallbacks=[{"primary": [f"fallback_{i}" for i in range(len(fallback_models))]}],
        **router_settings,
    )
    
    class RouterChatModel(BaseChatModel):
        """Wrapper to make litellm.Router compatible with LangChain."""
        
        @property
        def _llm_type(self) -> str:
            return "datarobot-router"
        
        def _generate(
            self,
            messages: list[BaseMessage],
            stop: list[str] | None = None,
            run_manager: Any = None,
            **kwargs: Any,
        ) -> ChatResult:
            litellm_messages = [
                {"role": "user" if hasattr(msg, "content") else "assistant", "content": str(msg.content)}
                for msg in messages
            ]
            response = router.completion("primary", messages=litellm_messages, **kwargs)
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=response.choices[0].message.content or ""))])
        
        async def _agenerate(
            self,
            messages: list[BaseMessage],
            stop: list[str] | None = None,
            run_manager: Any = None,
            **kwargs: Any,
        ) -> ChatResult:
            litellm_messages = [
                {"role": "user" if hasattr(msg, "content") else "assistant", "content": str(msg.content)}
                for msg in messages
            ]
            response = await router.acompletion("primary", messages=litellm_messages, **kwargs)
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=response.choices[0].message.content or ""))])
    
    return RouterChatModel()
```

### Step 3: Update `custompy_adaptor`

Modify the `custompy_adaptor` function to build and use the router:

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

    # Build router with fallback support
    llm = _build_litellm_router_for_langgraph(
        primary_model="azure/gpt-5-mini-2025-08-07",
        fallback_models=["anthropic/claude-opus-4-20250514"],
        use_datarobot_gateway=True,
        allowed_fails=3,
        cooldown_time=60.0,
    )

    agent = MyAgent(
        llm=llm,
        verbose=completion_create_params.get("verbose", True),
        timeout=completion_create_params.get("timeout", 90),
        forwarded_headers=forwarded_headers,
    )
    return await agent_chat_completion_wrapper(
        agent, completion_create_params, mcp_tools_factory
    )
```

The `RouterChatModel` wrapper translates between LangChain message types and litellm's OpenAI-compatible interface, making it a drop-in replacement for `get_llm()`.

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

## Simplified approach with datarobot-genai 0.15.8+

Once [datarobot-genai PR #297](https://github.com/datarobot-oss/datarobot-genai/pull/297) is merged and `datarobot-genai >= 0.15.8` is released, you can significantly simplify both paths:

### DRAgent simplification

Replace the manual `fallback_config` + router builder in `register.py` with a single YAML change:

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

NAT automatically resolves `datarobot-llm-router` and injects it into your agent — no `register.py` changes needed.

### DRUM simplification

Replace the `_build_litellm_router_for_langgraph` helper with simple imports:

```python
from datarobot_genai.core.config import LLMConfig
from datarobot_genai.langgraph.llm import get_router_llm

async def custompy_adaptor(completion_create_params: CompletionCreateParams) -> InvokeReturn:
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
    
    agent = MyAgent(
        llm=get_router_llm(primary, fallbacks, {"allowed_fails": 3, "cooldown_time": 60.0}),
        # ... rest of agent setup
    )
    return await agent_chat_completion_wrapper(agent, completion_create_params, mcp_tools_factory)
```

Once this version is available, you can remove the `RouterChatModel` class and `_build_litellm_router_for_langgraph` helper entirely.
