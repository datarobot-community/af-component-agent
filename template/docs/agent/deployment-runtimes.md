# Deployment runtimes

The agent's Pulumi infrastructure can deploy the agent onto one of two runtimes: **Custom Models** (the default) or the **Workload API**. They differ mainly in how long a deploy takes and what surrounding DataRobot resources you get. This page covers picking one, deploying on the Workload API, tuning it, and switching later.

---

## Choosing a runtime

**Start on Custom Models.** It is the default, it needs no configuration, and it gives you a Playground, a deployment ID, and deployment-based monitoring. Move to the Workload API when serving latency and deploy turnaround matter more than those extras — it provisions only an image artifact plus a workload, so there is less to create and tear down on each change.

Within the Workload API there are two paths. The default one builds the image for you on the platform (**C2W**, Code to Workload) from your agent source; the other runs an image you built and pushed yourself.

| | Custom Models | Workload API + C2W | Workload API + your own image |
|---|---|---|---|
| Docker registry needed | No | No | Yes — reachable by DataRobot |
| Where you can deploy from | A laptop or CI; no local Docker | A laptop or CI; no local Docker | Anywhere you can build and push to a registry DataRobot can pull from |
| Who builds the image | DataRobot | DataRobot, during `dr run deploy` | You, before deploying |
| What a code change costs | Custom model version + deployment update | A full image rebuild | Your own build and push; no platform build |
| Playground / deployment ID | Yes | No | No |

<!-- TODO(verify): concrete per-path deploy durations, and whether the Workload API
     runtime requires a cluster-side feature flag. The only figure traceable to code
     today is the 10–20 min execution-environment build below. -->

- Pick **Custom Models** if you want the Playground, a deployment ID, or deployment monitoring.
- Pick **Workload API + C2W** if you want a leaner serving-only deploy and no Docker tooling of your own.
- Pick **Workload API + your own image** if you already build and publish the agent image in CI.

---

## Deploy on Workload API

Set one variable in `.env` at the app root — everything else has a default:

```sh
ENABLE_AGENT_ON_WORKLOAD_API=true
```

`DATAROBOT_API_TOKEN` and `DATAROBOT_ENDPOINT` must also be set; both are required on this runtime, and the token is deliberately kept out of Pulumi state, so it must be present for `pulumi destroy` too. `ENABLE_AGENT_ON_WORKLOAD_API` accepts `true`, `1`, `yes`, or `enabled` (case-insensitive); any other value, including unset, means Custom Models.

Then deploy:

```sh
dr run deploy
```

With no `WORKLOAD_*` variables set, this takes the C2W path: it uploads the agent source, builds an image on top of a DataRobot execution environment, and starts a workload running `workload/run_server.sh`. The Pulumi stack exports `Agent Workload Endpoint <asset>`, plus `Agent Workload Chat Endpoint <asset>` — the same URL with `/chat/completions` appended. When `workflow.yaml` declares `general.front_end.a2a`, an `<endpoint>/a2a/` endpoint is exported as well. Replicas start serving once the readiness probe polls `/health` successfully — within roughly 70 seconds of container start, and not configurable.

Take the chat endpoint from that stack output and call it like any OpenAI-compatible one:

```sh
CHAT_ENDPOINT=$(pulumi stack output "Agent Workload Chat Endpoint <asset>")

curl -X POST "$CHAT_ENDPOINT" \
  -H "Authorization: Bearer $DATAROBOT_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "{\"topic\": \"Generative AI\"}"}]}'
```

Other components in the app receive `<AGENT_APP_NAME>_WORKLOAD_ID` and `<AGENT_APP_NAME>_ENDPOINT` automatically. Credential-typed runtime parameters resolve at container start from DataRobot credentials, so their values never land in Pulumi state.

---

## Configuration

> [!WARNING]
> `DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT` dominates deploy time. Leaving it unset while a `docker_context/` folder or `docker_context.tar.gz` sits in the agent app builds a **new execution environment on every dependency change — 10–20 minutes**. Pointing it at the built-in Python 3.11 GenAI Agents drop-in avoids that build entirely.

| Variable | Default | Effect |
|---|---|---|
| `DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT` | unset | Unset + a `docker_context/` or `docker_context.tar.gz` in the agent app → builds a new execution environment (10–20 min). A value containing `Python 3.11 GenAI Agents` → the built-in drop-in, no build. Any other value → treated as an existing execution-environment ID. C2W only. |
| `DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID` | unset | Pins the version when referencing an existing execution environment. |
| `WORKLOAD_CPU` | `1` | Cores per container (float). |
| `WORKLOAD_MEMORY` | `1610612736` (1536 MiB) | Memory per container, in **integer bytes**. 2 GiB is `2147483648`; `2Gi` raises an error. |
| `WORKLOAD_REPLICA_COUNT` | `1` | Number of replicas. |
| `WORKLOAD_IMPORTANCE` | `high` | Workload scheduling priority. |
| `WORKLOAD_CONTAINER_PORT` | `8080` | Container port, and the port the readiness probe polls. |
| `WORKLOAD_ENTRYPOINT` | C2W: `["sh", "workload/run_server.sh"]` | Container entrypoint, as a JSON array or a comma-separated list. |
| `WORKLOAD_BUILD_TIMEOUT_S` | `9000` | How long to wait for the image build, in seconds. C2W only. |
| `WORKLOAD_AGENT_IMAGE_URI` | unset | Set to run a pre-built image instead of building one. |

---

## Using your own image

Set `WORKLOAD_AGENT_IMAGE_URI` to an image DataRobot can pull. The image must listen on `WORKLOAD_CONTAINER_PORT` (default `8080`) and serve `/health`, or replicas never become ready.

Leave `WORKLOAD_ENTRYPOINT` unset to keep the image's own entrypoint — unlike C2W, nothing is substituted for you. No execution environment is created in this scenario, so `DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT` and `WORKLOAD_BUILD_TIMEOUT_S` have no effect.

---

## What changes trigger a rebuild

Workload artifacts are **replace-on-change**: there is no in-place update, so any tracked change creates a new artifact and discards the old one. The rule of thumb:

- **New image build** — agent source, dependencies, container port, entrypoint, or any environment variable passed to the container.
- **Workload update only, no rebuild** — CPU, memory, replica count, and importance.

What counts as "agent source" is decided by the `.wapiignore` file at the agent app root — the same archived bytes are both uploaded and hashed, so editing an ignored file changes nothing. Read that file for the default exclusions.

---

## What Workload API does not provide

This runtime is serving-only. Compared with Custom Models, these are not created:

- **No Playground / `LlmBlueprint`** — no in-UI experimentation against this agent. Deferred, not permanent.
- **No `CustomModelDeployment`, so no deployment ID** — `task agent:cli -- execute-deployment --deployment_id …` does not apply here. Test the workload by POSTing to its chat endpoint instead, as shown in the [quick start](#deploy-on-workload-api).
- **No prediction environment** — nothing to attach deployment-level policies to.
- **No deployment-based monitoring** — accuracy, drift, and custom metrics all hang off a deployment, which does not exist here.

`ENABLE_AGENT_HA_MODE` and `AGENT_DEPLOY` affect Custom Models only; Workload API sizing is set entirely by the `WORKLOAD_*` variables above.

---

## Switching runtimes

Switching is a supported, one-variable change in both directions — flip `ENABLE_AGENT_ON_WORKLOAD_API` and redeploy with `dr run deploy`. Pulumi reconciles the existing stack by creating the new runtime's resources and deleting the old runtime's, in place; you do not need a fresh stack.

Two things to plan for either way:

- **The serving endpoint changes.** Anything holding the old URL — external callers, saved configs, other environments — has to be re-pointed. In-app components pick up the new value automatically through their runtime parameters.
- **Custom Models → Workload API drops the deployment ID**, along with the Playground and deployment monitoring. Anything keyed on that ID stops resolving. Switching back creates a *new* deployment with a new ID; the old one is not restored.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| First deploy is unexpectedly slow | An execution environment is being built. Set `DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT` to a value containing `Python 3.11 GenAI Agents` to use the drop-in instead. |
| Deploy fails waiting on the image build | The build exceeded `WORKLOAD_BUILD_TIMEOUT_S` (default `9000`). Raise it, or trim dependencies in `pyproject.toml`. |
| Replicas never become ready | The container is not answering `/health` on `WORKLOAD_CONTAINER_PORT`. With your own image, confirm it serves that path on that port; with C2W, check the workload logs for a startup error. |
| `ValueError` on `WORKLOAD_MEMORY` | The value must be integer bytes, not a Kubernetes quantity. Use `2147483648`, not `2Gi`. |
| `pulumi destroy` fails with a missing token | `DATAROBOT_API_TOKEN` is never stored in Pulumi state, so it must be set in the environment for destroy as well as deploy. |