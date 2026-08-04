# Agent memory

> **Also known as:** persistent memory, long-term memory, user memory, Mem0, DataRobot memory service

The agent uses `af-component-memory` for persistent, per-user memory. The memory
component owns provider selection, credentials, MemorySpace infrastructure,
feature flags, deployment prompts, and memory-specific runtime parameters. The
agent only consumes the selected component.

Chat history is separate from agent memory. Chat history contains messages sent
with the current request; agent memory stores facts across sessions.

## Add memory to an agent

Apply `af-component-memory` to the recipe and point the agent at its answers
file:

```sh
uvx copier copy datarobot-community/af-component-memory . \
  --data memory_provider=mem0

uvx copier update .datarobot/answers/agent-agent.yml \
  --data memory_answers_file=.datarobot/answers/memory-mem0_memory.yml
```

The component framework supplies `memory_answers_file` when the memory and
agent components are connected. `use_agent_memory` is hidden and derived from
the selected memory module identity; users do not choose a provider in the
agent component, and the agent does not inspect `memory_provider`.

Provider-specific setup is documented in the rendered memory document under
`docs/<memory-name>.md`.

## Runtime behavior

Every generated agent workflow uses the same memory-aware structure:

```yaml
functions:
  base_agent:
    _type: base_agent
    llm_name: datarobot_llm

memory:
  mem0_memory:
    _type: dr_mem0_memory

workflow:
  _type: streaming_memory_agent
  inner_agent_name: base_agent
  memory_name: mem0_memory
  llm_name: datarobot_llm
```

`streaming_memory_agent` retrieves relevant memories before invoking the inner
agent and stores the user and assistant messages after the turn. It preserves
the inner agent's streaming events.

`dr_mem0_memory` supports both Mem0 and the DataRobot Memory Service. It chooses
the configured backend from runtime parameters supplied by the memory
component. When no backend is configured, it returns an unconfigured editor and
`streaming_memory_agent` passes the request directly to the inner agent.

## Per-user isolation

The wrapper obtains the authenticated user identity from the DRAgent request
context. Retrieval and storage are scoped to that user, so memories are not
shared between users.

## Infrastructure contract

The selected memory module exports:

```python
memory_custom_model_runtime_parameters
```

The agent infrastructure extends its custom-model parameters with that list.
It does not inspect the provider, interpret provider-specific keys, or create
memory resources itself.

Typical runtime keys are:

| Key | Purpose |
|---|---|
| `AGENT_MEMORY_TTL_DAYS` | Retention period for stored memories. |
| `MEM0_API_KEY` | Mem0 credential, when the memory component uses Mem0. |
| `AGENT_MEMORY_SPACE_ID` | DataRobot MemorySpace ID, when the component uses the DataRobot Memory Service. |

Deploy-time environment variables are prefixed with the hidden memory component
name. For example, the default component reads `MEMORY_MEM0_API_KEY` or
`MEMORY_AGENT_MEMORY_TTL_DAYS`, then supplies the fixed keys expected by the
agent runtime.

## Local development

Configure the environment variables described in `docs/<memory-name>.md`. For
local execution, use the fixed runtime keys consumed by `dr_mem0_memory`; the
component-prefixed keys are read by Pulumi when deploying the agent. Then start
the agent normally:

```sh
dr run agent:dev
```

The DataRobot Memory Service must be deployed before local execution so its
MemorySpace ID is available. Local Mem0 execution requires `MEM0_API_KEY`;
deployment reads the component-prefixed key documented by the memory component.

## Migrating existing agents

Older agent answers stored the provider in `use_agent_memory`. Provider choice
now belongs to `af-component-memory`.

To migrate:

1. Add a memory component using the previous provider.
2. Update the agent with that component's `memory_answers_file`.
3. Run the normal deployment preview and confirm the memory resources before
   applying.

The agent migration removes the legacy provider answer so the hidden state is
derived from the memory component on future updates.

## Further reading

| Topic | Description |
|---|---|
| [Agent README](./README.md) | Agent component overview and framework guides. |
| [Chat history](./chat-history.md) | Request-scoped multi-turn context. |
| [Moderation](./moderation.md) | Guardrails around the memory-aware workflow. |
