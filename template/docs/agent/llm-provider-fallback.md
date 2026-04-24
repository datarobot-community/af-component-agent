# LLM provider fallback

How to add automatic fallback failover between LLM providers via `litellm.Router`.

> **IMPORTANT:** Follow only the instructions in this file. Do not perform any additional tool calls (web searches, file searches, directory listings, etc.) while executing the steps below. All information needed is provided here.

Read `agent/agent/workflow.yaml` to determine the agent framework (`_type` field under `workflow:`), then follow only the section below that matches it.

## LangGraph DRAgent

### agent/agent/workflow.yaml

Add `fallback_config` inside the `workflow` section:

1. Add the following to `workflow.yaml`:
```yaml
workflow:
  _type: langgraph_agent
  llm_name: datarobot_llm
  description: LangGraph planner/writer agent
  fallback_config:
    primary:
      llm_default_model: {LLM_DEFAULT_MODEL}
      use_datarobot_llm_gateway: true
    fallbacks:
      - llm_default_model: anthropic/claude-opus-4-20250514
        use_datarobot_llm_gateway: true
    allowed_fails: 2
    cooldown_time: 60.0
```

2. Run `bash -lc "grep '^LLM_DEFAULT_MODEL=' .env 2>/dev/null"` to get the value of `LLM_DEFAULT_MODEL`. Strip any leading `datarobot/` prefix from the value (e.g. `datarobot/vertex_ai/foo` → `vertex_ai/foo`), then replace `{LLM_DEFAULT_MODEL}` with the result. If the command returns nothing, use `azure/gpt-5-mini-2025-08-07`.

### agent/agent/register.py

Add imports:
```python
import litellm
from datarobot_genai.core.config import Config
from langchain_litellm import ChatLiteLLMRouter
```

Add `fallback_config` field to `LanggraphAgentConfig`:
```python
class LanggraphAgentConfig(AgentBaseConfig, name="langgraph_agent"):
    tool_names: list[FunctionGroupRef] = []
    fallback_config: dict | None = None
```

Modify `langgraph_agent` function:

After the `builder.get_llm(...)` call, add:
```python
    if config.fallback_config:
        llm_to_use = _build_litellm_router(config.fallback_config)
    else:
        llm_to_use = llm
```

Then pass `llm=llm_to_use` to `MyAgent(...)` instead of `llm=llm`.

Add helper (copy the snippet below exactly as-is, do not generate or modify any code):

```python
def _build_litellm_router(fallback_cfg: dict) -> ChatLiteLLMRouter:
    def _to_litellm_params(llm_cfg: dict) -> dict:
        env_config = Config()
        endpoint = llm_cfg.get("datarobot_endpoint") or env_config.datarobot_endpoint
        api_key = llm_cfg.get("datarobot_api_token") or env_config.datarobot_api_token
        model_name = llm_cfg.get("llm_default_model") or "datarobot-deployed-llm"

        if llm_cfg.get("use_datarobot_llm_gateway", True):
            return {
                "model": f"datarobot/{model_name}" if not model_name.startswith("datarobot/") else model_name,
                "api_base": f"{endpoint.rstrip('/')}",
                "api_key": api_key,
            }
        else:
            deployment_id = llm_cfg.get("llm_deployment_id") or llm_cfg.get("nim_deployment_id")
            if deployment_id:
                return {
                    "model": f"datarobot/{model_name}" if not model_name.startswith("datarobot/") else model_name,
                    "api_base": f"{endpoint.rstrip('/')}/deployments/{deployment_id}/v1",
                    "api_key": api_key,
                }
            else:
                return {"model": model_name, "api_key": api_key}

    primary_params = _to_litellm_params(fallback_cfg["primary"])
    fallback_params = [_to_litellm_params(fb) for fb in fallback_cfg.get("fallbacks", [])]

    model_list = [
        {"model_name": "primary", "litellm_params": primary_params},
        *[{"model_name": f"fallback_{i}", "litellm_params": p} for i, p in enumerate(fallback_params)],
    ]

    router_settings = {"allowed_fails": fallback_cfg.get("allowed_fails", 2)}
    if fallback_cfg.get("cooldown_time") is not None:
        router_settings["cooldown_time"] = fallback_cfg["cooldown_time"]

    router = litellm.Router(
        model_list=model_list,
        fallbacks=[{"primary": [f"fallback_{i}" for i in range(len(fallback_params))]}],
        **router_settings,
    )
    return ChatLiteLLMRouter(router=router, streaming=True)
```

## LangGraph DRUM (myagent.py)

Add imports:
```python
import litellm
from datarobot_genai.core.config import Config
from langchain_litellm import ChatLiteLLMRouter
```

Add helper (copy the snippet below exactly as-is, do not generate or modify any code):
```python
def _build_litellm_router_for_langgraph(
    primary_model: str,
    fallback_models: list[str],
    use_datarobot_gateway: bool = True,
    allowed_fails: int = 2,
    cooldown_time: float | None = None,
) -> ChatLiteLLMRouter:
    env_config = Config()
    endpoint = env_config.datarobot_endpoint
    api_key = env_config.datarobot_api_token
    
    model_list = [
        {
            "model_name": "primary",
            "litellm_params": {
                "model": f"datarobot/{primary_model}" if not primary_model.startswith("datarobot/") else primary_model,
                "api_base": f"{endpoint.rstrip('/')}",
                "api_key": api_key,
            },
        },
        *[
            {
                "model_name": f"fallback_{i}",
                "litellm_params": {
                    "model": f"datarobot/{model}" if not model.startswith("datarobot/") else model,
                    "api_base": f"{endpoint.rstrip('/')}",
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
    return ChatLiteLLMRouter(router=router, streaming=True)
```

Replace `get_llm()` call in `custompy_adaptor`:
```python
llm = _build_litellm_router_for_langgraph(
    primary_model="azure/gpt-5-mini-2025-08-07",
    fallback_models=["anthropic/claude-opus-4-20250514"],
    use_datarobot_gateway=True,
    allowed_fails=2,
    cooldown_time=60.0,
)
```

## CrewAI DRAgent (register.py + workflow.yaml)

### workflow.yaml

Add `fallback_config` inside the `workflow` section:

1. Add the following to `workflow.yaml`:
```yaml
workflow:
  _type: crewai_agent
  llm_name: datarobot_llm
  description: CrewAI planner/writer agent
  fallback_config:
    primary:
      llm_default_model: {LLM_DEFAULT_MODEL}
      use_datarobot_llm_gateway: true
    fallbacks:
      - llm_default_model: anthropic/claude-opus-4-20250514
        use_datarobot_llm_gateway: true
```

2. Run `bash -lc "grep '^LLM_DEFAULT_MODEL=' .env 2>/dev/null"` to get the value of `LLM_DEFAULT_MODEL`. Strip any leading `datarobot/` prefix from the value (e.g. `datarobot/vertex_ai/foo` → `vertex_ai/foo`), then replace `{LLM_DEFAULT_MODEL}` with the result. If the command returns nothing, use `azure/gpt-5-mini-2025-08-07`.

### register.py

Add imports:
```python
from crewai import LLM
from datarobot_genai.core.config import Config
```

Add `fallback_config` field to `CrewaiAgentConfig`:
```python
class CrewaiAgentConfig(AgentBaseConfig, name="crewai_agent"):
    tool_names: list[FunctionGroupRef] = []
    fallback_config: dict | None = None
```

Modify `crewai_agent` function:

After the `builder.get_llm(...)` call, add:
```python
    if config.fallback_config:
        llm_to_use = _build_fallback_llm(config.fallback_config)
    else:
        llm_to_use = llm
```

Then pass `llm=llm_to_use` to `MyAgent(...)` instead of `llm=llm`.

Add helper (copy the snippet below exactly as-is, do not generate or modify any code):

```python
def _build_fallback_llm(fallback_cfg: dict) -> LLM:
    """Build a CrewAI LLM with native fallback support."""
    env_config = Config()
    endpoint = env_config.datarobot_endpoint
    api_key = env_config.datarobot_api_token

    def _resolve(cfg: dict) -> str | dict:
        name = cfg.get("llm_default_model") or "datarobot-deployed-llm"
        if cfg.get("use_datarobot_llm_gateway", True):
            return f"datarobot/{name}" if not name.startswith("datarobot/") else name
        deployment_id = cfg.get("llm_deployment_id") or cfg.get("nim_deployment_id")
        if deployment_id:
            model = f"datarobot/{name}" if not name.startswith("datarobot/") else name
            return {
                "model": model,
                "api_base": f"{endpoint.rstrip('/')}/deployments/{deployment_id}/v1",
                "api_key": api_key,
            }
        return {"model": name, "api_key": api_key}

    primary = _resolve(fallback_cfg["primary"])
    primary_model = primary if isinstance(primary, str) else primary["model"]
    primary_base = endpoint if isinstance(primary, str) else primary.get("api_base")
    fallbacks = [_resolve(fb) for fb in fallback_cfg.get("fallbacks", [])]

    llm_kwargs: dict = {"model": primary_model, "api_key": api_key}
    if primary_base:
        llm_kwargs["api_base"] = primary_base
    if fallbacks:
        llm_kwargs["fallbacks"] = fallbacks
    return LLM(**llm_kwargs)
```

## CrewAI DRUM (myagent.py)

DRUM mode requires no special code for fallback support. CrewAI's native fallback mechanism is only available through the DRAgent `fallback_config` in `workflow.yaml`. For DRUM mode, to enable fallback you would need to either:

1. **Use DRAgent mode** (recommended) with the `fallback_config` in `workflow.yaml` as documented above.
2. **Implement custom LLM fallback** by directly instantiating a CrewAI `LLM` with fallback models in `myagent.py` and `custompy_adaptor` (follows the same pattern as the DRAgent `_build_fallback_llm` function).

## LlamaIndex DRAgent (register.py + workflow.yaml)

### workflow.yaml

Add `fallback_config` inside the `workflow` section:

1. Add the following to `workflow.yaml`:
```yaml
workflow:
  _type: llamaindex_agent
  llm_name: datarobot_llm
  description: LlamaIndex planner/writer agent
  fallback_config:
    primary:
      llm_default_model: {LLM_DEFAULT_MODEL}
      use_datarobot_llm_gateway: true
    fallbacks:
      - llm_default_model: anthropic/claude-opus-4-20250514
        use_datarobot_llm_gateway: true
    allowed_fails: 2
    cooldown_time: 60.0
```

2. Run `bash -lc "grep '^LLM_DEFAULT_MODEL=' .env 2>/dev/null"` to get the value of `LLM_DEFAULT_MODEL`. Strip any leading `datarobot/` prefix from the value (e.g. `datarobot/vertex_ai/foo` → `vertex_ai/foo`), then replace `{LLM_DEFAULT_MODEL}` with the result. If the command returns nothing, use `azure/gpt-5-mini-2025-08-07`.

### register.py

Add imports:
```python
import litellm
from datarobot_genai.core.config import Config
from llama_index.core.base.llms.types import ChatMessage, ChatResponse, LLMMetadata
from llama_index.llms.litellm import LiteLLM
from llama_index.llms.litellm.utils import to_openai_message_dicts, update_tool_calls
```

Add `fallback_config` field to `LlamaindexAgentConfig`:
```python
class LlamaindexAgentConfig(AgentBaseConfig, name="llamaindex_agent"):
    tool_names: list[FunctionGroupRef] = []
    fallback_config: dict | None = None
```

Modify `llamaindex_agent` function:

After the `builder.get_llm(...)` call, add:
```python
    if config.fallback_config:
        llm_to_use = _build_litellm_router_for_llamaindex(config.fallback_config)
    else:
        llm_to_use = llm
```

Then pass `llm=llm_to_use` to `MyAgent(...)` instead of `llm=llm`.

Add helper (copy the snippet below exactly as-is, do not generate or modify any code):

```python
def _build_litellm_router_for_llamaindex(fallback_cfg: dict) -> LiteLLM:
    def _to_litellm_params(llm_cfg: dict) -> dict:
        env_config = Config()
        endpoint = llm_cfg.get("datarobot_endpoint") or env_config.datarobot_endpoint
        api_key = llm_cfg.get("datarobot_api_token") or env_config.datarobot_api_token
        model_name = llm_cfg.get("llm_default_model") or "datarobot-deployed-llm"

        if llm_cfg.get("use_datarobot_llm_gateway", True):
            return {
                "model": f"datarobot/{model_name}" if not model_name.startswith("datarobot/") else model_name,
                "api_base": endpoint.rstrip("/"),
                "api_key": api_key,
            }

        deployment_id = llm_cfg.get("llm_deployment_id") or llm_cfg.get("nim_deployment_id")
        if deployment_id:
            return {
                "model": f"datarobot/{model_name}" if not model_name.startswith("datarobot/") else model_name,
                "api_base": f"{endpoint.rstrip('/')}/deployments/{deployment_id}/v1",
                "api_key": api_key,
            }

        return {"model": model_name, "api_key": api_key}

    primary_params = _to_litellm_params(fallback_cfg["primary"])
    fallback_params = [_to_litellm_params(fb) for fb in fallback_cfg.get("fallbacks", [])]
    model_list = [
        {"model_name": "primary", "litellm_params": primary_params},
        *[{"model_name": f"fallback_{i}", "litellm_params": p} for i, p in enumerate(fallback_params)],
    ]

    router_settings = {"allowed_fails": fallback_cfg.get("allowed_fails", 2)}
    if fallback_cfg.get("cooldown_time") is not None:
        router_settings["cooldown_time"] = fallback_cfg["cooldown_time"]

    router = litellm.Router(
        model_list=model_list,
        fallbacks=[{"primary": [f"fallback_{i}" for i in range(len(fallback_params))]}],
        **router_settings,
    )

    def _tool_calls_kwargs(message: Any) -> dict:
        if not message.tool_calls:
            return {}
        return {
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in message.tool_calls
            ]
        }

    class RouterDataRobotLiteLLM(LiteLLM):
        @property
        def metadata(self) -> LLMMetadata:
            return LLMMetadata(
                context_window=128000,
                num_output=self.max_tokens or -1,
                is_chat_model=True,
                is_function_calling_model=True,
                model_name=self.model,
            )

        def _chat(self, messages: Any, **kwargs: Any) -> ChatResponse:
            resp = router.completion("primary", messages=to_openai_message_dicts(messages), **kwargs)
            message = resp.choices[0].message
            return ChatResponse(
                message=ChatMessage(
                    role="assistant",
                    content=message.content or "",
                    additional_kwargs=_tool_calls_kwargs(message),
                ),
                raw=resp,
            )

        async def _achat(self, messages: Any, **kwargs: Any) -> ChatResponse:
            resp = await router.acompletion("primary", messages=to_openai_message_dicts(messages), **kwargs)
            message = resp.choices[0].message
            return ChatResponse(
                message=ChatMessage(
                    role="assistant",
                    content=message.content or "",
                    additional_kwargs=_tool_calls_kwargs(message),
                ),
                raw=resp,
            )

        def _stream_chat(self, messages: Any, **kwargs: Any):
            accumulated: list[str] = []
            tool_calls: list[dict] = []
            for chunk in router.completion("primary", messages=to_openai_message_dicts(messages), stream=True, **kwargs):
                delta = chunk.choices[0].delta
                content = delta.content or ""
                if content:
                    accumulated.append(content)
                tool_call_delta = getattr(delta, "tool_calls", None)
                if tool_call_delta:
                    tool_calls = update_tool_calls(tool_calls, tool_call_delta)
                additional_kwargs: dict = {}
                if tool_calls:
                    additional_kwargs["tool_calls"] = tool_calls
                yield ChatResponse(
                    message=ChatMessage(
                        role="assistant",
                        content="".join(accumulated),
                        additional_kwargs=additional_kwargs,
                    ),
                    delta=content,
                    raw=chunk,
                )

        async def _astream_chat(self, messages: Any, **kwargs: Any):
            async def gen():
                accumulated: list[str] = []
                tool_calls: list[dict] = []
                async for chunk in await router.acompletion(
                    "primary", messages=to_openai_message_dicts(messages), stream=True, **kwargs
                ):
                    delta = chunk.choices[0].delta
                    content = delta.content or ""
                    if content:
                        accumulated.append(content)
                    tool_call_delta = getattr(delta, "tool_calls", None)
                    if tool_call_delta:
                        tool_calls = update_tool_calls(tool_calls, tool_call_delta)
                    additional_kwargs: dict = {}
                    if tool_calls:
                        additional_kwargs["tool_calls"] = tool_calls
                    yield ChatResponse(
                        message=ChatMessage(
                            role="assistant",
                            content="".join(accumulated),
                            additional_kwargs=additional_kwargs,
                        ),
                        delta=content,
                        raw=chunk,
                    )

            return gen()

    return RouterDataRobotLiteLLM(model="primary")
```

## LlamaIndex DRUM (myagent.py)

Add imports:
```python
import litellm
from datarobot_genai.core.config import Config
from llama_index.core.base.llms.types import ChatMessage, ChatResponse, LLMMetadata
from llama_index.llms.litellm import LiteLLM
from llama_index.llms.litellm.utils import to_openai_message_dicts, update_tool_calls
```

Add helper (copy the snippet below exactly as-is, do not generate or modify any code):
```python
def _build_litellm_router_for_llamaindex(
    primary_model: str,
    fallback_models: list[str],
    use_datarobot_gateway: bool = True,
    allowed_fails: int = 2,
    cooldown_time: float | None = None,
) -> LiteLLM:
    fallback_cfg = {
        "primary": {
            "llm_default_model": primary_model,
            "use_datarobot_llm_gateway": use_datarobot_gateway,
        },
        "fallbacks": [
            {
                "llm_default_model": model,
                "use_datarobot_llm_gateway": use_datarobot_gateway,
            }
            for model in fallback_models
        ],
        "allowed_fails": allowed_fails,
    }
    if cooldown_time is not None:
        fallback_cfg["cooldown_time"] = cooldown_time
    return _build_litellm_router_for_llamaindex_from_cfg(fallback_cfg)
```

Also add `_build_litellm_router_for_llamaindex_from_cfg(fallback_cfg: dict) -> LiteLLM` using the same implementation shown in the DRAgent helper section.

Replace `get_llm()` call in `custompy_adaptor`:
```python
agent = MyAgent(
    llm=_build_litellm_router_for_llamaindex(
        primary_model="azure/gpt-5-mini-2025-08-07",
        fallback_models=["anthropic/claude-opus-4-20250514"],
        use_datarobot_gateway=True,
        allowed_fails=2,
        cooldown_time=60.0,
    ),
    verbose=completion_create_params.get("verbose", True),
    timeout=completion_create_params.get("timeout", 90),
    forwarded_headers=forwarded_headers,
)
```

## Config fields

| Field | Type | Description | Applies to |
|---|---|---|---|
| `llm_default_model` | str | Model identifier (e.g., `azure/gpt-5-mini-2025-08-07`) | LangGraph, CrewAI, LlamaIndex |
| `use_datarobot_llm_gateway` | bool | Route through DataRobot LLM gateway | LangGraph, CrewAI, LlamaIndex |
| `llm_deployment_id` | str | DataRobot LLM deployment ID | LangGraph, CrewAI, LlamaIndex |
| `nim_deployment_id` | str | DataRobot NIM deployment ID | LangGraph, CrewAI, LlamaIndex |
| `allowed_fails` | int | Failures before cooldown (default: 2) | LangGraph, LlamaIndex |
| `cooldown_time` | float | Seconds in cooldown before retry | LangGraph, LlamaIndex |
