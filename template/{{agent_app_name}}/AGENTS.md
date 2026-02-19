# Agent Sub-project

LangGraph-based AI agent deployed as a DataRobot custom model.

This directory was generated from the `af-component-agent` component.
Run `copier update` from the project root to pull in upstream changes.

## The only files to modify

- `{{ agent_app_name }}/agent/myagent.py` — agent class, tools, workflow, system prompt
- `{{ agent_app_name }}/agent/config.py` — agent configuration schema
- `{{ agent_app_name }}/tests/test_agent.py` — update after any agent changes

Do not modify files outside of `{{ agent_app_name }}/agent/`.

## MyAgent structure

```python
from datarobot_genai.langgraph.agent import LangGraphAgent

class MyAgent(LangGraphAgent):
    """Your agent description here."""

    def __init__(self, ...):
        self.model = "datarobot/<preferred-model>"  # must be prefixed with datarobot/
```

### `llm()` method — do not modify

This method handles DataRobot LLM Gateway auth and model routing. Keep it exactly
as generated. Changing it will break deployment.

### `workflow` property

Defines the LangGraph execution graph. Add nodes and edges here.

```python
@property
def workflow(self) -> StateGraph[MessagesState]:
    langgraph_workflow = StateGraph[MessagesState, None, MessagesState, MessagesState](MessagesState)
    langgraph_workflow.add_node("agent_node", self.agent_node)
    langgraph_workflow.add_edge(START, "agent_node")
    langgraph_workflow.add_edge("agent_node", END)
    return langgraph_workflow
```

### `agent_node` property

```python
@property
def agent_node(self) -> Any:
    return create_react_agent(
        self.llm(),
        tools=self.tools,
        prompt=make_system_prompt("Your system prompt here."),
    )
```

## Adding tools

Add tool files inside `{{ agent_app_name }}/agent/`. Import and pass them in `agent_node`:

```python
tools = [my_tool_function]
```

If the tool requires a new package, add it to `pyproject.toml`, then:

```shell
dr task run {{ agent_app_name }}:install
```

## Commands

All commands must be run from the **project root**.

```shell
dr task run {{ agent_app_name }}:install   # install/sync dependencies
dr task run {{ agent_app_name }}:test      # run pytest
dr task run {{ agent_app_name }}:lint      # ruff + mypy
```

## Post-deployment validation

```shell
task {{ agent_app_name }}:cli -- execute-deployment \
  --user_prompt "A prompt to validate the agent is working" \
  --deployment_id <deployment_id>
```
