---
name: prepare-manual-testbed
description: Render an agent from the current af-component-agent working tree into a deployable test bed for a manual check against a DataRobot cluster (staging, regression, on-prem). Use when a template change needs a real `task deploy` before it becomes a PR, or when the user asks for a test bed.
---

# Prepare a manual test bed

A test bed is a rendered agent under `.rendered/agent_<name>/` with the e2e scaffolding,
dependencies installed, and a `.env` the user fills in. The user runs `task deploy` and
checks the behaviour by hand; see `test-agent-codespace-staging` for the codespace side.

## Why not `task render-template`

`task render-template AGENT=<framework>` wipes `.rendered/agent_<framework>/` except
`.venv`, which deletes the `.env` the user keeps there. It also renders with
`--vcs-ref=HEAD`, so uncommitted template changes are not included. Render by hand
into a fresh directory instead.

## 1. Snapshot the working tree

copier reads a git ref, never the working tree. Make a throwaway commit in a scratch
worktree so uncommitted changes render, without touching the user's checkout:

```
WT=<scratchpad>/wt-testbed
git worktree add --detach "$WT" HEAD
cp <each modified file> "$WT/<same path>"      # from `git status --short`
git -C "$WT" add -A && git -C "$WT" commit -q -m wip
```

Remove it as soon as the render is done: `git worktree remove --force "$WT"; git worktree prune`.

## 2. Render with the e2e scaffolding

Pick a directory name that is not one of the existing `.rendered/agent_*` folders.
The data flags mirror `render-template`; `agent_app_name=agent` matters because the
fixtures hardcode the `agent/` path.

```
R=.rendered/agent_<name>
mkdir -p "$R/.datarobot/answers" && cp fixtures/.datarobot/answers/llm-llm.yml "$R/.datarobot/answers/"
uvx copier copy "$WT" "$R" --defaults \
  --data agent_app_name=agent --data agent_template_framework=<base|langgraph|crewai|llamaindex|nat> \
  --data use_agent_memory=none --vcs-ref=HEAD
cp fixtures/Taskfile.yml "$R/Taskfile.yml"
mkdir -p "$R/infra/infra"
cp fixtures/infra/Taskfile.yml fixtures/infra/Pulumi.yaml fixtures/infra/__main__.py fixtures/infra/pyproject.toml "$R/infra/"
cp fixtures/infra/__init__.py fixtures/infra/llm.py "$R/infra/infra/"
```

`Pulumi.yaml` and `__main__.py` come from `render-template-e2e`, not `render-template`;
without them `pulumi up` has no program. A `MissingFileWarning` about
`.datarobot/answers/base.yml` is normal.

Confirm the change under test made it into the render before going further, for
example `grep <new symbol> "$R/infra/infra/agent_infra/base.py"`.

## 3. Install

```
cd "$R" && task install
```

Installs `agent/.venv` and `infra/.venv` with uv and copies the agent's lock into
`docker_context/`. Several minutes the first time.

## 4. Write `.env`

The fixture Taskfile loads `.env` from the render root. Write it with placeholders
and let the user fill credentials; never copy a token from another render. Keys the
e2e harness writes (`tests/e2e/helpers.py`, `write_testing_env`):

```
DATAROBOT_ENDPOINT=https://<host>/api/v2
DATAROBOT_API_TOKEN=<token>
SESSION_SECRET_KEY=test-secret-key
DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT="[DataRobot] Python 3 GenAI Agents"
PULUMI_STACK=<unique stack name>
PULUMI_CONFIG_PASSPHRASE=123
ENABLE_AGENT_ON_WORKLOAD_API=false
```

Add whatever the scenario needs (a version pin, a custom env id, `ENABLE_AGENT_ON_WORKLOAD_API=true`
for the Workload API path) and put the expected pulumi output for the scenario in a
comment at the top, so the person deploying knows what a pass looks like.

## 5. Hand over

Tell the user the directory, what to fill in, and the commands:

```
cd .rendered/agent_<name>
task build      # custom model only, no deployment: Playground / codespace path
task deploy     # custom model + deployment
task destroy    # when done
```

`.rendered/` is gitignored, so nothing here can leak into a commit.
