---
name: test-agent-codespace-staging
description: Test an af-component-agent agent in a DataRobot codespace on staging. Use when asked to verify the agentic playground / codespace path of an agent on staging, or to debug an execution environment change (e.g. a new python3_genai_agents build) end to end.
---

# Test agent codespace on staging

## 1. AWS access to the staging cluster

Staging infrastructure is reached through the `stg` AWS SSO profile. The login is
interactive (opens a browser), so the user runs it, not the agent:

```
aws sso login --profile stg
```

Check whether the session is still valid before asking for a login:

```
aws sts get-caller-identity --profile stg
```

An expired session prints "The SSO session associated with this profile has expired".
The user approves the login in the browser; poll `get-caller-identity` until it returns an ARN.

## 2. Kube context and namespace

Codespaces run as pods in the `notebooks-pods` namespace of the `stg` cluster
(note the plural; `notebooks-services` next to it holds the nbx services, not the kernels):

```
kubectx stg
kubens notebooks-pods
```

There is also a `stg-custom` context; it is not the one for codespaces.

## 3. Find the codespace a custom model chat runs in

When a playground chats with a custom model that has no deployment, buzok runs the agent
in an ephemeral codespace. The buzok worker logs (`buzok-worker-app-io-*` pods in the
`buzok` namespace) carry the custom model ID inside `extra.entity_id` and the codespace
as `extra.notebook_id`. With the custom model ID in `CM`:

```
for p in $(kubectl get pods -n buzok --no-headers | awk '$3=="Running" && /worker-app-io/{print $1}'); do
  kubectl logs -n buzok "$p" --since=24h
done | grep -a "$CM" | grep -oE "notebook_id\":\"ObjectId\('[0-9a-f]{24}'\)" | grep -oE '[0-9a-f]{24}' | sort | uniq -c
```

The same lines show the job's progress: the logger is
`worker.job_handlers.agent.chat_completion_custom_model` and the message goes from
"Waiting for codespace session to be ready" onward. A job stuck on that message for
minutes means the codespace pod never came up; move on to the pod in `notebooks-pods`.

## 4. The codespace pods: kernel first

A codespace is two pods in `notebooks-pods`, both named after the notebook ID:
`kernel-<notebook_id>-...` (the execution environment image, runs the agent) and
`runner-<notebook_id>-...` (nbx-services sidecar). Both must be Running and Ready. Look at
the kernel first; the runner's startup probe usually fails only because the kernel did.

```
NB=<notebook_id>
kubectl get pods | grep "$NB"
K=$(kubectl get pods --no-headers | awk -v nb="$NB" '$1 ~ "^kernel-"nb {print $1}')
kubectl get pod "$K" -o jsonpath='{.spec.containers[0].image}{"\n"}'     # env image, tag = that version's image build
kubectl get events --field-selector involvedObject.name="$K" | grep -v FailedScheduling
kubectl logs "$K" --previous --tail=60                                   # last crashed run
```

The image tag is the ID of the env version's image build, an ObjectId adjacent to the version
ID, so it changes with every version. To map it back to an env, read the custom model's
versions: `dr.CustomModelVersion.list(<custom model id>)` gives `base_environment_id` and
`base_environment_version_id` per version. `FailedScheduling` events are noise: the scheduler retries until a
notebooks node has room.

Failure signatures seen so far:

- `exec /etc/system/kernel/start_server.sh: exec format error`: wrong CPU architecture, see
  "Bringing your own execution environment" in `template/docs/agent/deployment-runtimes.md`.
  To confirm, compare the node's `kubernetes.io/arch` label with the image config in ECR:
  `aws ecr batch-get-image --profile stg --region us-east-1 --repository-name custom-models/base-image --image-ids imageTag=<version id>`
  gives the config digest, `aws ecr get-download-url-for-layer` fetches it, and it carries `architecture`.
- Startup probe on `:8888/api/kernelspecs` refused: the kernel gateway never started; the
  reason is in the previous run's logs.
- Runner in CrashLoopBackOff with `httpx.ConnectError: All connection attempts failed` in its
  previous logs: it cannot reach the kernel gateway. Fix the kernel; the runner follows.

A healthy kernel shows `Found kernel python3 in /etc/system/kernel/.venv/share/jupyter/kernels`,
`200 GET /api/kernelspecs`, and a kernel going to `status (idle)`. An IPython extension
traceback near the top (e.g. from `/home/notebooks/.ipython/extensions/`) is not fatal to
the kernel but means that extension is dead; fix it in the env anyway.

## 5. Once the kernel is up: the agent's own logs

The buzok worker then syncs the agent into the codespace and executes it. The worker log
goes "Syncing files with the codespace" → "Executing script in codespace" → "Downloading
agent chat response". Everything from that point is in `/home/notebooks/storage` inside
the kernel pod:

```
kubectl exec "$K" -- bash -c 'cd /home/notebooks/storage && ls -la && tail -50 venv.log && cat output.log && tail -40 *.json.log'
```

- `venv.log`: `run_agent.py` bootstrapping `/opt/venv` with `uv sync --frozen` from the
  agent's own `pyproject.toml` and `uv.lock`. A harmless first line warns that
  `VIRTUAL_ENV=/etc/system/kernel/.venv` is ignored. `Permission denied` on `/opt/venv`
  here means the env image did not make it writable.
- `output.log`: stdout of `run_agent.py`; "Parsing args" alone means it got past argparse.
- `<prompt id>.json.log`: the agent run itself, tracing setup, dragent workflow, and
  "Storing result". Handled exceptions and warnings land here even on success.
- `<prompt id>.json`: the chat completion returned to the playground. On success it has a
  `choices[0].message.content` and `finish_reason: stop`.

If the folder only holds `lost+found`, the sync never happened: the worker is still waiting
on the session, go back to step 4.
