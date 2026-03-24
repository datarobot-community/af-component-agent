# Developer Guide

## af-component-agent

To run tests and linters locally on all agent frameworks you can run `task test`. To test an individual
framework you can run `task test-<agent_framework>`. To test the CLI on the base agent you can run `task test-cli`
and `task test-cli-json`. These are equivalent to the tests when you open a PR against your branch.
Tests will be run through github actions, and you can see the results in the PR. If you are making large changes
that may have significant impacts to the template installation
and usage, you should additionally open a branch in [recipe-datarobot-agent-templates](https://github.com/datarobot/recipe-datarobot-agent-templates).

> After committing a PR you should create a new release in this repository to bump the version of the component.
> This is required to properly work with the `uvx copier` command and to ensure that the changes are reflected in the
> downstream repositories.

## Updating dependencies

Template `uv.lock` output is assembled by `uv.lock.jinja`, which includes the correct partial from `template/{{agent_app_name}}/uvlock_templates/uvlock_<framework>.j2` depending on `agent_template_framework`.

Do not edit those partials by hand. Regenerate them with the root `Taskfile.yml` tasks below.

The `update-lock-file` task:

1. Renders the Copier template into `.rendered/agent_<AGENT>/` (`render-template`).
2. Runs `uv lock` in `.rendered/agent_<AGENT>/agent`.
3. Copies the resulting `uv.lock` into `template/{{agent_app_name}}/uvlock_templates/uvlock_<AGENT>.j2`.

`RENDER_DIR` defaults to `.rendered` (see the top of `Taskfile.yml`).

### Regenerate without upgrading (`UPGRADE_LOCK` unset or not `1`)

Use this when you changed `pyproject.toml.jinja` or constraints and want a lockfile that matches those pins **without** bumping dependencies to the newest versions the resolver allows.

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

Use this when you want `uv lock -U`: refresh the lockfile and **upgrade** dependencies to the latest versions still allowed by `pyproject.toml`.

```bash
UPGRADE_LOCK=1 task update-lock-file AGENT=langgraph
```

For every agent:

```bash
UPGRADE_LOCK=1 task update-lock-file-all
```
