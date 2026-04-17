# NAT agent

The NAT (NVIDIA NeMo Agent Toolkit) agent uses a fully declarative YAML-based configuration to define agents, tools, and workflows without writing Python agent logic.

## `myagent.py`

Unlike the other frameworks, NAT agents are defined entirely in `workflow.yaml`. The `myagent.py` file contains only a minimal `MyAgent` class that loads the YAML:

```python
from datarobot_genai.nat.agent import NatAgent

class MyAgent(NatAgent):
    def __init__(self, *args, workflow_path=Path(__file__).parent / "workflow.yaml", **kwargs):
        super().__init__(*args, workflow_path=workflow_path, **kwargs)
```

The `workflow.yaml` defines everything:

**Functions** (sub-agents)&mdash;defined as `chat_completion` types with system prompts:

```yaml
functions:
  planner:
    _type: chat_completion
    llm_name: datarobot_llm
    system_prompt: |
      You are a content planner...
  writer:
    _type: chat_completion
    llm_name: datarobot_llm
    system_prompt: |
      You are a content writer...
```

**Workflow**&mdash;a `per_user_tool_calling_agent` that orchestrates which functions to call:

```yaml
workflow:
  _type: per_user_tool_calling_agent
  llm_name: datarobot_llm
  tool_names:
    - planner
    - writer
    - mcp_tools
  system_prompt: |
    You are a blog content orchestrator. For every user request:
    1. Call planner to get a content plan.
    2. Call writer with the content plan as input.
    Return only the final blog post.
```

**LLMs**&mdash;configured directly in YAML rather than in Python:

```yaml
llms:
  datarobot_llm:
    _type: datarobot-llm-component
```

You can define multiple LLMs and assign them to different functions.

## Tool integration

NAT manages all tools declaratively in `workflow.yaml`. Unlike other frameworks, you don't pass tools through Python code&mdash;everything is wired via YAML configuration.

### MCP tools

MCP tools are configured as a `function_group` and referenced in `tool_names` in the workflow:

```yaml
function_groups:
  mcp_tools:
    _type: datarobot_mcp_client

workflow:
  _type: per_user_tool_calling_agent
  tool_names:
    - mcp_tools
```

The MCP tools context in `myagent.py` is a no-op because NAT manages tools entirely in YAML.

### A2A remote agent tools

Remote agents are also configured as function groups:

```yaml
function_groups:
  remote_agent:
    _type: authenticated_a2a_client
    url: "https://app.datarobot.com/api/v2/deployments/DEPLOYMENT_ID/directAccess/a2a/"
    auth_provider: datarobot_auth
```

### Custom local tools

To add a custom tool to a NAT agent, define a plain Python function and register it using `nat_tool()` from `datarobot_genai.nat.tool` in `register.py`. Then reference it by name in `workflow.yaml`.

**Step 1**&mdash;Define the tool function (e.g. in `agent/agent/tools.py`):

```python
from typing import Annotated

def generate_objectid(
    type: Annotated[str, "The type of object to generate an ID for. Should be only 'deployment'."],
) -> str:
    """Generate a unique object ID for a deployment."""
    if type != "deployment":
        raise ValueError("Invalid type")
    return "69cbb73789723b6936c6c9e1"
```

Use `Annotated` type hints to provide parameter descriptions&mdash;NAT uses these to generate the tool schema for the LLM.

**Step 2**&mdash;Register the tool in `register.py`:

```python
from datarobot_genai.nat.tool import nat_tool
from agent.tools import generate_objectid

nat_tool(generate_objectid, "generate_objectid")
```

The second argument is the name of the tool as it will appear in `workflow.yaml`.

**Step 3**&mdash;Add the tool to `workflow.yaml`:

```yaml
functions:
  generate_objectid:
    _type: generate_objectid
    description: A tool that generates an object ID for a deployment.

workflow:
  _type: per_user_tool_calling_agent
  llm_name: datarobot_llm
  tool_names:
    - planner
    - writer
    - mcp_tools
    - generate_objectid
```

The `_type` in the `functions` section must match the name passed to `nat_tool()`. The tool then becomes available alongside other functions and MCP tools.

You can also define sub-agents as tools using `_type: chat_completion` with a `system_prompt`&mdash;these are built-in function types in NAT that act as callable tools for the orchestrator agent.

For more on NAT tool types, see the [NVIDIA NeMo Agent Toolkit documentation](https://docs.nvidia.com/nemo/agent-toolkit/index.html).

## Prompt modification

NAT agents define all prompts declaratively in `workflow.yaml`. You configure two levels: **function system prompts** (sub-agent behavior) and the **workflow system prompt** (orchestrator behavior).

### Function system prompts

Each function in the `functions` section has a `system_prompt` field that defines the behavior of that sub-agent:

```yaml
functions:
  planner:
    _type: chat_completion
    llm_name: datarobot_llm
    system_prompt: |
      You are a content planner. You are working with a content writer colleague.
      You're working on planning a blog article about the topic.
      You collect information that helps the audience learn something and make
      informed decisions. Your work is the basis for the Content Writer.
      1. Prioritize the latest trends, key players, and noteworthy news on the topic.
      2. Identify the target audience, considering their interests and pain points.
      3. Develop a detailed content outline including an introduction, key points,
         and a call to action.
      4. Include SEO keywords and relevant data or sources.
    description: A tool that plans the content for the requested topic.
```

- `system_prompt`&mdash;the full system prompt for this function. Use YAML multiline syntax (`|`) for readability.
- `description`&mdash;a short description visible to the orchestrator agent when deciding which tool to call.
- `llm_name`&mdash;which LLM this function uses (references the `llms` section). Different functions can use different LLMs.

### Workflow system prompt

The `workflow` section has its own `system_prompt` that controls the orchestrator&mdash;the top-level agent that decides which functions to call:

```yaml
workflow:
  _type: per_user_tool_calling_agent
  llm_name: datarobot_llm
  tool_names:
    - planner
    - writer
    - mcp_tools
  system_prompt: |
    You are a blog content orchestrator. For every user request, follow these steps:
    1. Call planner to get a content plan.
    2. Call writer with the content plan as input to produce the final blog post.
    Feel free to call the MCP tools as needed.
    Return only the final blog post output from the writer.
  verbose: true
```

This prompt should clearly describe the execution order and what each tool/function does. The orchestrator uses this to decide the sequence of calls.

### How to modify

- **Update function prompts**&mdash;edit the `system_prompt` field in any `functions` entry.
- **Change the orchestration logic**&mdash;modify the `workflow.system_prompt` to change how the orchestrator sequences function calls.
- **Assign different LLMs**&mdash;set `llm_name` per function to use different models for different tasks (e.g. a fast model for planning, a capable model for writing).
- **Add new functions**&mdash;create a new entry in `functions` with `_type: chat_completion`, a `system_prompt`, and a `description`. Then add it to `workflow.tool_names`.
- **Change function descriptions**&mdash;update `description` to influence when the orchestrator calls a function.

### Tips

- The `workflow.system_prompt` is the most impactful prompt&mdash;it controls the overall agent behavior and execution flow.
- Use numbered steps in the workflow prompt to enforce a specific execution order.
- Use `description` on functions to help the orchestrator understand when to call each function.
- Different functions can use different LLMs&mdash;use a faster model for simple tasks and a more capable model for complex ones.
- Test prompt changes by editing `workflow.yaml` and running `task agent:cli -- execute --user_prompt "..."`. No code changes needed.

For more on NAT prompt configuration, see the [NVIDIA NeMo Agent Toolkit documentation](https://docs.nvidia.com/nemo/agent-toolkit/index.html).

## When to use

- You want to define agents without writing Python code.
- You need to iterate quickly on agent prompts and tool configurations via YAML.
- You want to use NAT-native features like built-in tool types, authentication providers, and multi-LLM configurations.

## Streaming

All streaming levels (chunk, step, event) require custom implementation.
