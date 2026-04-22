# LLM provider fallback

Automatic failover between LLM providers using `litellm.Router`.

> [!NOTE]
> Manual implementation. Once `datarobot-genai >= 0.15.8` is released, see [Simplified approach](#simplified-approach-with-datarobot-genai-0158).

## DRAgent (register.py + workflow.yaml)

### workflow.yaml

Add `fallback_config` inside the `workflow` section:

```yaml
workflow:
  _type: langgraph_agent
  llm_name: datarobot_llm
  description: LangGraph planner/writer agent
  fallback_config:
    primary:
      llm_default_model: azure/gpt-5-mini-2025-08-07
      use_datarobot_llm_gateway: true
    fallbacks:
      - llm_default_model: anthropic/claude-opus-4-20250514
        use_datarobot_llm_gateway: true
    allowed_fails: 3
    cooldown_time: 60.0
```

### register.py

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

```python
async def langgraph_agent(config: LanggraphAgentConfig, builder: Builder) -> AsyncGenerator[Any, None]:
    from agent.myagent import MyAgent

    llm = await builder.get_llm(config.llm_name, wrapper_type=LLMFrameworkEnum.LANGCHAIN)
    workflow_tools = await builder.get_tools(config.tool_names, wrapper_type=LLMFrameworkEnum.LANGCHAIN)

    if config.fallback_config:
        llm_to_use = _build_litellm_router(config.fallback_config)
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


def _build_litellm_router(fallback_cfg: dict) -> ChatLiteLLMRouter:
    def _to_litellm_params(llm_cfg: dict) -> dict:
        env_config = Config()
        endpoint = llm_cfg.get("datarobot_endpoint") or env_config.datarobot_endpoint
        api_key = llm_cfg.get("datarobot_api_token") or env_config.datarobot_api_token
        model_name = llm_cfg.get("llm_default_model") or "datarobot-deployed-llm"
        
        if llm_cfg.get("use_datarobot_llm_gateway", True):
            return {
                "model": f"datarobot/{model_name}" if not model_name.startswith("datarobot/") else model_name,
                "api_base": f"{endpoint.rstrip('/')}/v1/chat/completions",
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
    
    router_settings = {"allowed_fails": fallback_cfg.get("allowed_fails", 3)}
    if fallback_cfg.get("cooldown_time") is not None:
        router_settings["cooldown_time"] = fallback_cfg["cooldown_time"]
    
    router = litellm.Router(
        model_list=model_list,
        fallbacks=[{"primary": [f"fallback_{i}" for i in range(len(fallback_params))]}],
        **router_settings,
    )
    return ChatLiteLLMRouter(router=router)
```

## DRUM (myagent.py)

Add imports:
```python
import litellm
from datarobot_genai.core.config import Config
from langchain_litellm import ChatLiteLLMRouter
```

Add helper:
```python
def _build_litellm_router_for_langgraph(
    primary_model: str,
    fallback_models: list[str],
    use_datarobot_gateway: bool = True,
    allowed_fails: int = 3,
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
                "api_base": f"{endpoint.rstrip('/')}/v1/chat/completions",
                "api_key": api_key,
            },
        },
        *[
            {
                "model_name": f"fallback_{i}",
                "litellm_params": {
                    "model": f"datarobot/{model}" if not model.startswith("datarobot/") else model,
                    "api_base": f"{endpoint.rstrip('/')}/v1/chat/completions",
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
    return ChatLiteLLMRouter(router=router)
```

Replace `get_llm()` call in `custompy_adaptor`:
```python
llm = _build_litellm_router_for_langgraph(
    primary_model="azure/gpt-5-mini-2025-08-07",
    fallback_models=["anthropic/claude-opus-4-20250514"],
    use_datarobot_gateway=True,
    allowed_fails=3,
    cooldown_time=60.0,
)
```

## Config fields

| Field | Type | Description |
|---|---|---|
| `llm_default_model` | str | Model identifier (e.g., `azure/gpt-5-mini-2025-08-07`) |
| `use_datarobot_llm_gateway` | bool | Route through DataRobot LLM gateway |
| `llm_deployment_id` | str | DataRobot LLM deployment ID |
| `nim_deployment_id` | str | DataRobot NIM deployment ID |
| `allowed_fails` | int | Failures before cooldown (default: 3) |
| `cooldown_time` | float | Seconds in cooldown before retry |

## Simplified approach with datarobot-genai 0.15.8+

### DRAgent

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

No `register.py` changes needed.

### DRUM

```python
from datarobot_genai.core.config import LLMConfig
from datarobot_genai.langgraph.llm import get_router_llm

primary = LLMConfig(llm_default_model="azure/gpt-5-mini-2025-08-07", use_datarobot_llm_gateway=True)
fallbacks = [LLMConfig(llm_default_model="anthropic/claude-opus-4-20250514", use_datarobot_llm_gateway=True)]

llm = get_router_llm(primary, fallbacks, {"allowed_fails": 3, "cooldown_time": 60.0})
```
