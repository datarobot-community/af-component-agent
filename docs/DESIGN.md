# Template Design

## Overview

This repository is a [Copier](https://copier.readthedocs.io/) template that generates DataRobot agent applications. It supports five agentic framework flavours
— **base**, **crewai**, **langgraph**, **llamaindex**, and **nat** (NVIDIA NeMo Agent Toolkit). The user selects a framework at generation time
via the `agent_template_framework` Copier variable, and the template renders a ready-to-run Python project under `<agent_app_name>/`.

## Template variables

Defined in `copier.yml`:

| Variable | Purpose |
|---|---|
| `agent_app_name` | Name and root folder of the generated project. Must be a valid Python identifier. |
| `agent_template_framework` | Framework flavour: `base`, `crewai`, `langgraph`, `llamaindex`, or `nat`. |
| `use_low_code_interface` | When `true`, forces `agent_template_framework=nat`. |
| `base_answers_file`, `llm_answers_file`, `mcp_answers_file` | Paths to DataRobot component answer files consumed via `_external_data`. |

The `_exclude` directive in `copier.yml` ensures that `*.j2` partials and `*_templates/` directories are never copied into the rendered output — they exist only as include sources.

## File-system layout

```
template/{{agent_app_name}}/
├── agent/                          # Core agent package
│   ├── __init__.py                 # Exports MyAgent, Config, custompy_adaptor
│   ├── config.py.jinja             # Pydantic settings (always rendered)
│   ├── myagent.py.jinja            # Router — includes the framework-specific partial
│   ├── agent_templates/            # Framework-specific MyAgent + custompy_adaptor
│   │   ├── agent_base.py.j2
│   │   ├── agent_crewai.py.j2
│   │   ├── agent_langgraph.py.j2
│   │   ├── agent_llamaindex.py.j2
│   │   └── agent_nat.py.j2
│   ├── register.py.jinja           # Router — framework-specific DR registration
│   ├── register_templates/
│   │   └── register_<framework>.py.j2
│   ├── workflow.yaml.jinja         # Router — framework-specific workflow config
│   └── workflow_templates/
│       └── workflow_<framework>.yaml.j2
├── custom.py.jinja                 # Router — includes custom_templates/*
├── custom_templates/
│   ├── custom_default.py.j2        # Used by base, crewai, langgraph, llamaindex
│   └── custom_nat.py.j2            # NAT-specific custom.py
├── tests/
│   ├── conftest.py                 # Shared pytest fixtures
│   ├── test_agentic_workflow.py.jinja
│   ├── test_agentic_workflow_templates/
│   │   ├── test_agentic_workflow_default.py.j2
│   │   └── test_agentic_workflow_nat.py.j2
│   ├── test_authorization_context_threading.py.jinja
│   ├── test_authorization_context_templates/
│   │   ├── test_authorization_context_default.py.j2
│   │   └── test_authorization_context_nat.py.j2
│   ├── test_agent.py.jinja
│   ├── test_agent_templates/
│   │   └── test_agent_<framework>.py.j2
│   ├── test_mcp.py.jinja
│   ├── test_mcp_templates/
│   │   └── test_mcp_<framework>.j2
│   ├── test_cli_dragent.py.jinja
│   ├── test_register_dragent.py.jinja
│   └── test_dragent_templates/
│       ├── test_cli_dragent.py.j2
│       └── test_register_dragent.py.j2
├── pyproject.toml.jinja
├── uv.lock.jinja
├── uvlock_templates/
│   └── uvlock_<framework>.j2
├── Taskfile.yml.jinja
├── cli.py.jinja
├── dev.py                          # Local development entry point (static)
├── public/                         # UI assets (static)
└── example-*.json                  # Example payloads (static)
```

## Two-tier Jinja pattern

Every polymorphic source file uses a **router → partial** pattern:

1. **Router** (`.jinja`): a thin file that inspects `agent_template_framework` and `{% include %}` the appropriate partial.
2. **Partial** (`.j2` inside a `*_templates/` directory): the actual code for that framework.

Example — `myagent.py.jinja`:

```jinja
{% if agent_template_framework == "crewai" %}{% include '.../agent_crewai.py.j2' -%}
{% elif agent_template_framework == "nat" %}{% include '.../agent_nat.py.j2' -%}
...
{% else %}{% include '.../agent_base.py.j2' %}{% endif -%}
```

The `_exclude` directive in `copier.yml` strips the routers' `*.j2` extension after rendering and prevents `*_templates/` directories from appearing in the output.

### When "default" vs framework-specific partials exist

Most routers have a binary split:

- **`nat`** gets its own partial (different runtime behaviour — see below).
- Everything else falls through to a `*_default.py.j2` partial.

Some routers (like `myagent.py.jinja` and `test_agent.py.jinja`) have a dedicated partial per framework.

## Runtime architecture

The generated project has a well-defined call chain:

```
custom.py  →  agent/myagent.py (custompy_adaptor)  →  MyAgent
```

### `custom.py` — the DataRobot entry point

Exposes `load_model()` and `chat()`. The `chat()` function:

1. Resolves authorization context from the incoming request.
2. Whitelists incoming HTTP headers (only `x-datarobot-*` headers pass through).
3. Stores both in `completion_create_params["authorization_context"]` and `completion_create_params["forwarded_headers"]`.
4. Calls `custompy_adaptor(completion_create_params)`.
5. Converts the result to a DataRobot chat response (streaming or non-streaming).

There are two variants:
- **`custom_default.py.j2`** — used by base, crewai, langgraph, llamaindex.
- **`custom_nat.py.j2`** — used by NAT. Adds NAT-specific streaming handling and telemetry instrumentation with `instrument(framework="nat")`.

### `custompy_adaptor` — framework-specific glue

Defined in each `agent_templates/agent_<framework>.py.j2`. Receives the enriched `completion_create_params` and wires up the agent.

**Default frameworks** (base, crewai, langgraph, llamaindex):

```
forwarded_headers ─┬─► MCPConfig ─► mcp_tools_context() ─► MCP tools
                   │
                   └─► MyAgent(forwarded_headers=forwarded_headers, tools=mcp_tools)
```

The default pattern passes `forwarded_headers` to both `MCPConfig` and `MyAgent` unchanged, and obtains MCP tools through `mcp_tools_context()`.

**NAT framework**:

```
forwarded_headers ─► MCPConfig ─► server_config["headers"]
                         │                    │
                         └────── merge ◄──────┘
                                  │
                                  └─► MyAgent(forwarded_headers=merged)
```

NAT does **not** use `mcp_tools_context`. Instead, it explicitly reads `MCPConfig.server_config["headers"]` and merges those into `forwarded_headers` before passing the combined dict to `MyAgent`. This means:

- The agent always receives the union of whitelisted incoming headers **and** MCP server config headers.
- When `server_config` is `None` (no MCP configured), the agent receives just the whitelisted headers (which may be an empty dict).

This distinction is the main reason NAT has separate test and custom.py templates.

## Test structure

Tests mirror the router/partial pattern. Each `test_*.py.jinja` router selects the appropriate `test_*_<variant>.py.j2` partial.

| Test file | What it covers |
|---|---|
| `test_agentic_workflow.py` | End-to-end `load_model` / `chat` round-trip |
| `test_authorization_context_threading.py` | Auth context propagation and header forwarding through `custom.py → custompy_adaptor → MyAgent` |
| `test_agent.py` | Framework-specific agent unit tests (e.g. CrewAI crew construction) |
| `test_mcp.py` | MCP tool integration (crewai, langgraph, llamaindex only) |
| `test_cli_dragent.py`, `test_register_dragent.py` | CLI and DR registration tests |

### Key testing differences: NAT vs default

The `test_authorization_context_threading` tests are split because NAT and default frameworks have different mock targets and assertions:

| Aspect | Default frameworks | NAT |
|---|---|---|
| Mock target | `agent.myagent.mcp_tools_context` | `agent.myagent.MCPConfig` |
| Header assertions | Checked on `MCPConfig` object passed to `mcp_tools_context` | Checked on `MyAgent` constructor kwargs (merged headers) |
| Agent receives | Only the whitelisted `forwarded_headers` | Whitelisted headers merged with MCP `server_config` headers |
| No server config | Not applicable (tools context handles it) | Agent receives `{}` (empty dict) |

## Development workflow

See `docs/development.md` for full instructions. The short loop:

1. Edit files under `template/{{agent_app_name}}/`.
2. Run `SKIP_INFRA=1 task test-<framework>` (e.g. `task test-nat`).
3. Fix failures and re-run until green.
4. Commit.

The test task renders the template with `uvx copier copy`, installs dependencies, runs linting + type checking, and executes pytest with coverage.

## Adding a new framework

1. Add a partial in each `*_templates/` directory (agent, custom, test, workflow, register, uvlock).
2. Update the corresponding `.jinja` router to include the new partial.
3. Add the framework to `copier.yml` choices.
4. Add a `task test-<newframework>` entry in `Taskfile.yml`.
5. Run the test loop until green.
