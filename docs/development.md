# Developer guide

For template architecture (router/partial pattern, NAT vs default MCP wiring), see [DESIGN.md](./DESIGN.md).

## af-component-agent

Run `task test` to run tests and linters locally on all agent frameworks. Run `task test-<agent_framework>`
to test an individual framework. Run `task test-cli` and `task test-cli-json` to test the CLI on the base
agent. These commands are equivalent to the tests that run automatically when a PR opens against the branch.
GitHub Actions runs the tests, and the results appear in the PR. For large changes that may significantly
affect template installation or usage, also open a branch in [recipe-datarobot-agent-templates](https://github.com/datarobot/recipe-datarobot-agent-templates).

> **Important:** After committing a PR, create a release in this repository to bump the version of the component.
> This is required to properly work with the `uvx copier` command and to ensure the changes are reflected in the
> downstream repositories.

## Update dependencies

Template `uv.lock` output is assembled by `uv.lock.jinja`, which includes the correct partial from `template/{{agent_app_name}}/uvlock_templates/uvlock_<framework>.j2` depending on `agent_template_framework`.

Do not edit those partials by hand. Regenerate them with the root `Taskfile.yml` tasks: `update-lock-file` and `update-lock-file-all`.

The `update-lock-file` task:

1. Renders the Copier template into `.rendered/agent_<AGENT>/` (`render-template`).
2. Runs `uv lock` in `.rendered/agent_<AGENT>/agent`.
3. Copies the resulting `uv.lock` into `template/{{agent_app_name}}/uvlock_templates/uvlock_<AGENT>.j2`.

`RENDER_DIR` defaults to `.rendered` (see the top of `Taskfile.yml`).

### Regenerate without upgrading (`UPGRADE_LOCK` unset or not `1`)

Use this task after changing `pyproject.toml.jinja` or constraints, to produce a lockfile that matches those pins **without** bumping dependencies to the highest versions the resolver allows.

```bash
task update-lock-file AGENT=base
task update-lock-file AGENT=crewai
# … same pattern for langgraph, llamaindex, nat
```

All agent flavors at once:

```bash
task update-lock-file-all
```

This runs `uv lock --directory $RENDER_DIR/agent_<AGENT>/agent` (no `-U`).

### Regenerate with upgrades (`UPGRADE_LOCK=1`)

Use this to run `uv lock -U`: refresh the lockfile and **upgrade** dependencies to the highest versions still allowed by `pyproject.toml`.

```bash
UPGRADE_LOCK=1 task update-lock-file AGENT=langgraph
```

For every agent:

```bash
UPGRADE_LOCK=1 task update-lock-file-all
```
