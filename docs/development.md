# Developer guide

For template architecture (router/partial pattern, NAT vs default MCP wiring), see [DESIGN.md](./DESIGN.md).

## af-component-agent

Run `task test` to run tests and linters locally on all agent frameworks. Run `task test-<agent_framework>`
to test an individual framework. Run `task test-cli` and `task test-cli-json` to test the CLI on the base
agent. These commands are equivalent to the tests that run automatically when a PR opens against the branch.
GitHub Actions runs the tests, and the results appear in the PR. For large changes that may significantly
affect template installation or usage, also open a branch in [recipe-datarobot-agent-templates](https://github.com/datarobot/recipe-datarobot-agent-templates).

> **Important:** After merging a PR, create a release in this repository to bump the version of the component.
> This is required to properly work with the `uvx copier` command and to ensure the changes are reflected in the
> downstream repositories.

## Update dependencies

A rendered project's `uv.lock` is not resolved at render time. It is one of a set of pre-baked locks committed here, selected by `uv.lock.jinja` and copied out.

Those locks live at `template/{{agent_app_name}}/locks/<variant>/uv.lock`. They are real `uv.lock` files containing no Jinja, so `uv`, `tomllib`, cve-sync and any SCA scanner read them directly. The only thing not baked in is the project name, which each file carries as the literal placeholder `af-agent-placeholder`; `uv.lock.jinja` swaps that for the customer's `agent_app_name`, normalised the way uv itself normalises `[project].name`.

### One lock per resolution, not per framework

There are four locks for six template variants:

| variant | lock |
| --- | --- |
| `base` | `locks/base/uv.lock` |
| `nat` | `locks/base/uv.lock` |
| any framework + memory | the framework's own lock |
| `crewai` | `locks/crewai/uv.lock` |
| `langgraph` | `locks/langgraph/uv.lock` |
| `llamaindex` | `locks/llamaindex/uv.lock` |

`nat` renders the same `datarobot-genai` extras as `base` and its entry point is metadata rather than a dependency, so uv resolves both identically. The memory providers add no dependencies at all: `pyproject.toml.jinja` has no `use_agent_memory` conditional, and `mem0ai` already arrives through datarobot-genai.

`nat` and memory previously had locks of their own. Because `uv lock --check` only asks whether a lock satisfies its `pyproject.toml`, and a duplicate always does, those copies drifted unnoticed. Do not add a lock back for a variant until its dependency graph actually differs.

### Regenerating

Do not edit the locks by hand. Regenerate them with the root `Taskfile.yml` tasks: `update-lock-file` and `update-lock-file-all`.

The `update-lock-file` task:

1. Renders the Copier template into `.rendered/agent_<AGENT>/` under the placeholder project name (`render-template` with `APP_NAME=af_agent_placeholder`).
2. Runs `uv lock` in `.rendered/agent_<AGENT>/af_agent_placeholder`.
3. Checks the result holds no Jinja delimiter and does carry the placeholder name, then copies it verbatim to `template/{{agent_app_name}}/locks/<AGENT>/uv.lock`.

`RENDER_DIR` defaults to `.rendered` (see the top of `Taskfile.yml`).

### Regenerate without upgrading (`UPGRADE_LOCK` unset or not `1`)

Use this task after changing `pyproject.toml.jinja` or constraints, to produce a lockfile that matches those pins **without** bumping dependencies to the highest versions the resolver allows.

```bash
task update-lock-file AGENT=base
task update-lock-file AGENT=crewai
# … same pattern for langgraph and llamaindex. There is no nat or memory
# lock to regenerate; both are served by AGENT=base.
```

All agent flavors at once:

```bash
task update-lock-file-all
```

This runs `uv lock --directory $RENDER_DIR/agent_<AGENT>/af_agent_placeholder` (no `-U`).

### Regenerate with upgrades (`UPGRADE_LOCK=1`)

Use this to run `uv lock -U`: refresh the lockfile and **upgrade** dependencies to the highest versions still allowed by `pyproject.toml`.

```bash
UPGRADE_LOCK=1 task update-lock-file AGENT=langgraph
```

For every agent:

```bash
UPGRADE_LOCK=1 task update-lock-file-all
```

## Execution environment image

`DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT` set to a canonical name (one of `CANONICAL_EXECUTION_ENVIRONMENTS` in `base.py.jinja`: `Python 3 GenAI Agents` is the default, `Python 3.11 GenAI Agents` still resolves until that env is removed) or to an environment ID makes a generated agent run on that environment's image in two places: the custom model container behind a deployment, and the kernel of the ephemeral codespace buzok starts for the Playground when the agent has no deployment. The image is `custom-models/base-image:<image build id>` in the cluster's ECR; the tag is an ObjectId adjacent to the environment version ID and changes with every version, so the kernel pod's image tag tells you which build a codespace actually got.

A codespace is two pods in the `notebooks-pods` namespace, both named after the notebook ID: `kernel-<notebook id>-...` runs the environment image and its `start_server.sh`, and `runner-<notebook id>-...` runs nbx-services. The runner's startup probe only passes once the kernel gateway answers on port 8888, so a runner in CrashLoopBackOff with `httpx.ConnectError` in its logs is a symptom of the kernel, not a fault of its own.

What the image has to provide for both uses:

- **`linux/amd64`.** Nodes are amd64. An image built on an Apple Silicon Mac without `--platform linux/amd64` is arm64 and dies on the first line of the start script with `exec format error`. Creating the environment version from a docker context instead of an uploaded image avoids this, since the platform builds it.
- **`/opt/venv`, `/opt/code` and `/tmp/uv-cache` writable by UID 1000.** The custom model container runs as user 1000, and both `run_agent.py` (codespace) and `start_server.sh` (deployment) bootstrap the agent venv there. `python3_genai_agents` creates all three with `a+rwx`; `python313_notebook` does not, which is why it fails with `failed to create directory /opt/venv: Permission denied`.
- **`uv` on `PATH`.** The agent syncs its own `pyproject.toml` and `uv.lock` at start. Nothing from the agent's lock needs to be preinstalled; none of the template locks needs a compiler either, every compiled package ships a manylinux cp313 wheel.
- **`notebook` in the environment's use cases** next to `customModel`, or the Playground's codespace fallback does not find it.

The staging walkthrough for checking all of this on a live codespace is the `test-agent-codespace-staging` skill under `.agents/skills/`.
