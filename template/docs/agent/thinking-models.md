# Thinking models

> **Also known as:** extended thinking, reasoning models, reasoning, chain-of-thought, thinking budget, Claude extended thinking

The agent component can enable **extended thinking** (a.k.a. reasoning) on thinking-capable models, so the model produces internal reasoning before its final answer. Thinking is **off by default** and opt-in via two settings. It requires `datarobot-genai>=0.15.95` and a thinking-capable model routed through the DataRobot LLM Gateway (for example `datarobot/anthropic/claude-sonnet-4-20250514`).

When enabled, `datarobot-genai` adds a `thinking` block to the LLM request, and — for supported frameworks (see [Framework support](#framework-support)) — the model's reasoning is streamed to the client as AG-UI `ReasoningMessageChunkEvent`s alongside the normal text answer.

## Configuration

| Variable | Type | Default | Description |
|---|---|---|---|
| `ENABLE_THINKING` | `bool` | `false` | Turn on extended thinking. Truthy values: `1`, `true`, `yes`, `on` (case-insensitive). |
| `THINKING_BUDGET_TOKENS` | `int` | `1024` | Maximum tokens the model may spend on thinking. Must be `>= 1`. Only applies when `ENABLE_THINKING` is on. |

`datarobot-genai`'s `Config` reads these automatically (environment variables, `.env`, file secrets, DataRobot runtime parameters, or Pulumi outputs), so no code changes are needed.

### Local

Set them in your `.env` (or shell) before running the agent:

```bash
ENABLE_THINKING=true
THINKING_BUDGET_TOKENS=1024
```

### Deployed

The infra (`infra/infra/<app>.py`) surfaces both as **custom-model runtime parameters** when you set the env vars at deploy time:

```bash
ENABLE_THINKING=true THINKING_BUDGET_TOKENS=1024 pulumi up
```

They are only declared when set, so deployments that use non-thinking models are unaffected.

## Framework support

| Framework | Surfaces reasoning (AG-UI events) | Notes |
|---|---|---|
| LangGraph | Yes | Requests thinking and streams the model's reasoning. Recommended. |
| LlamaIndex | Yes | Requests thinking and streams the model's reasoning. Auto-pins `temperature=1` when thinking is active (Anthropic requirement). |
| CrewAI | No | Sends the thinking request but does **not** surface the model's reasoning as AG-UI events, and does **not** pin temperature (see caveat). CrewAI's own "reasoning" events are its planning feature, unrelated to model thinking. |
| NAT | No | Does not surface the model's reasoning, and strips any per-LLM `thinking` block set in `workflow.yaml`. |

## Anthropic temperature caveat

With thinking enabled, the DataRobot LLM Gateway requires Anthropic models to use `temperature` **unset or `== 1`** — any other value is rejected.

- **LangGraph** is safe: its LiteLLM client sends no temperature by default.
- **LlamaIndex** auto-pins `temperature=1` when thinking is active (only if you have not set one).
- **CrewAI** does **not** auto-pin. If you enable thinking on CrewAI with an Anthropic model, leave `temperature` unset or set it to `1`, or the gateway will reject the request.

## Model requirements

Use a thinking/reasoning-capable model. `THINKING_BUDGET_TOKENS` is honored only by providers that support extended thinking; non-thinking models ignore it.
