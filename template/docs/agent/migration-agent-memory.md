# Agent memory moved to af-component-memory (11.12.0)

This guide covers the breaking change that moved agent memory out of the agent component.

## Summary

Memory providers used to be an agent concern. The agent asked which provider you wanted, and its own Pulumi infrastructure created the Mem0 credential or the `MemorySpace`. Both now belong to a separate component, [`af-component-memory`](https://github.com/datarobot-community/af-component-memory).

| | Before | After |
|---|---|---|
| Provider choice | `use_agent_memory: mem0` / `datarobot_memory_service` in the agent's answers | `memory_provider` in af-component-memory's answers |
| Who creates the credential / `MemorySpace` | The agent's `base.py` | af-component-memory's own infra module |
| How the agent knows about memory | The `use_agent_memory` answer | `memory_answers_file` resolves to a real answers file |
| Runtime parameters (`AGENT_MEMORY_*`, `MEM0_API_KEY`) | Built by the agent | Exported by the memory component, forwarded unchanged by the agent |

`use_agent_memory` no longer exists. Whether an agent has memory is decided purely by whether `memory_answers_file` points at a memory component's answers file — the same way the agent picks up the LLM component. Copier drops the stale answer on update.

`workflow.yaml` needs no changes. The `streaming_memory_agent` wrapper was already emitted unconditionally and is a passthrough when no backend is configured.

**This only matters if your project used `use_agent_memory: mem0` or `use_agent_memory: datarobot_memory_service`.** Projects on `none` have nothing to do — the question simply disappears.

## ⚠️ Before you update: the DataRobot Memory Service space is destroyed

**This applies only to projects that used `datarobot_memory_service`.** Read it before running anything.

An Application Framework project is a single Pulumi stack whose `infra/__main__.py` imports every component's infra module. Your memory space is a Pulumi resource in that stack, declared by the agent's `base.py`.

After the update, the agent no longer declares it and the memory component declares a new, differently-named one. Pulumi sees the old resource drop out of the program, so **the next `pulumi up` destroys the existing memory space along with everything stored in it**, then creates an empty replacement.

There is no automatic carry-over. Export anything you need to keep before updating.

If preserving the space matters, raise it against af-component-memory — adopting an existing space needs a change there (a Pulumi `aliases` entry so the space is treated as renamed rather than replaced, or an option to accept an existing `AGENT_MEMORY_SPACE_ID` instead of creating one). Neither exists today.

## Steps

### 1. Add the memory component first

```sh
dr component add af-component-memory
```

Choose the same provider you were using before. This writes `.datarobot/answers/memory-<memory_name>.yml` and renders `infra/infra/<memory_name>.py`.

The instance name depends on the provider, and so does the answers file name:

| Provider | Instance name | Answers file |
|---|---|---|
| DataRobot Memory Service | `memory` | `.datarobot/answers/memory-memory.yml` |
| Mem0 | `mem0_memory` | `.datarobot/answers/memory-mem0_memory.yml` |

Order matters. The agent's infra imports the memory module by the name recorded in that file, so it has to exist before the agent renders.

### 2. Update the agent and point at that answers file

When the update asks for `memory_answers_file`, give it the path from step 1. Non-interactively:

```sh
--data memory_answers_file=.datarobot/answers/memory-mem0_memory.yml
```

The default is `.datarobot/answers/memory-memory.yml`, which is correct for the DataRobot Memory Service and wrong for Mem0.

> **A path that does not resolve means "no memory", not an error.** That is what makes memory optional, but it also means a typo silently disables it. Copier does warn when the path does not resolve:
>
> ```
> MissingFileWarning: File not found; returning empty dict: .datarobot/answers/memory-memory.yml
> ```
>
> It is a warning, not an error, and easy to miss in a long render. After updating, confirm `infra/infra/<agent_app_name>_infra/base.py` contains a `from ..<memory_name> import` line.

### 3. Move your provider settings

Settings move to the memory component and are read per-instance first, with the unprefixed name still honoured as a fallback:

| Before | After (preferred) | Still works |
|---|---|---|
| `MEM0_API_KEY` | `<MEMORY_NAME>_MEM0_API_KEY` | `MEM0_API_KEY` |
| `AGENT_MEMORY_TTL_DAYS` | `<MEMORY_NAME>_AGENT_MEMORY_TTL_DAYS` | `AGENT_MEMORY_TTL_DAYS` |
| `AGENT_MEMORY_LLM_*` | `<MEMORY_NAME>_AGENT_MEMORY_LLM_*` | `AGENT_MEMORY_LLM_*` |

`AGENT_MEMORY_SPACE_ID` is written out by the memory component — do not set it by hand.

## Further reading

| Topic | Description |
|---|---|
| [Agent memory](./agent-memory.md) | The runtime shape of memory, and how the agent finds the backend. |
| [Runtime parameters](./runtime-parameters.md) | How forwarded memory parameters reach the deployment. |
