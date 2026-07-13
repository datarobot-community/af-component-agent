# Skill: DataRobot local agentic evaluation (NAT/DRAgent)

**When to use this skill:** Use this skill when a user asks how to evaluate their agent locally, how to write quality-gate tests for their agent, how to detect hallucinations, or how to configure `moderation.yaml` for LLM-as-a-judge metrics (Faithfulness, Task Adherence, Agent Goal Accuracy) in a **NAT/DRAgent** project.

**Context window cost:** ~1100 tokens.

## Prerequisites

Before generating any code, confirm the following with the user:

1. Dependencies are installed — `datarobot-moderations[all]` is already included in `pyproject.toml`. Run `dr task run agent:install` if needed.
2. The user has a DataRobot LLM deployment to act as the **judge model**. Ask for its 24-character hex deployment ID.
3. `DATAROBOT_ENDPOINT` and `DATAROBOT_API_TOKEN` are set as environment variables. `dr start` creates the project-root `.env` file where the user configures these values.
4. `TARGET_NAME` must be added to `.env` (or exported manually) — the moderations library reads this key from the deployment's JSON response to extract the generated text.
5. This project uses DRAgent/NAT entrypoints (no DRUM `custompy_adaptor` path).

## Step-by-step implementation guide

When a user asks to set up local evaluation, generate the following files. Complete, copy-paste-ready versions are in the `examples/` folder alongside this skill.

### 1. Generate `moderation.yaml`

Copy `examples/moderation.yaml` to `agent/moderation.yaml`. Replace every `<YOUR_JUDGE_LLM_DEPLOYMENT_ID>` placeholder with a real 24-character DataRobot deployment ID, then remove the guards the user doesn't need.

Choose guards based on the user's use case:

- **Goal accuracy** (`agent_goal_accuracy`) — general agentic tasks; default recommendation.
- **Faithfulness** (`faithfulness`) — RAG agents that retrieve context before responding. Requires `copy_citations: true` so the library passes retrieved context to the judge.
- **Task adherence** (`task_adherence`) — instruction-following agents where prompt compliance matters.

Key fields to explain to the user:

```yaml
timeout_sec: 60          # cold-start deployments can take up to 90 s; set to 120 if timeouts occur
timeout_action: block    # use "score" to treat timeouts as pass during development

guards:
  - name: Agent Goal Accuracy
    type: ootb
    ootb_type: agent_goal_accuracy
    stage: response
    is_agentic: true              # required for agent_goal_accuracy
    llm_type: datarobot
    deployment_id: "<YOUR_JUDGE_LLM_DEPLOYMENT_ID>"   # 24 hex chars
    intervention:
      action: block
      message: "Agent failed to achieve the user's goal."
      conditions:
        - comparator: lessThan
          comparand: 0.7          # fail if accuracy < 70%
```

### 2. Generate the Pytest evaluation test (NAT path)

Copy `examples/test_agent_eval.py` to `agent/tests/test_agent_eval.py`.

The test file should:

1. Run the local workflow through DRAgent/NAT using `task agent:cli -- execute ...`.
2. Parse the response text from CLI output.
3. Pass that text into `ModerationPipeline.evaluate_response(...)`.

This replaces the old DRUM-only `custompy_adaptor` flow.

### 3. Register the `eval` marker

Add the marker to `[tool.pytest.ini_options]` in `pyproject.toml` to avoid `PytestUnknownMarkWarning`:

```toml
[tool.pytest.ini_options]
markers = [
    "eval: marks tests as live evaluation tests requiring DataRobot credentials",
]
```

## Common user questions

### "How do I run only the evaluation tests?"

```sh
cd agent && uv run pytest tests/ -m eval -v
```

### "How do I skip evaluation tests in CI when I don't have credentials?"

```sh
cd agent && uv run pytest tests/ -m "not eval"
```

### "The judge keeps timing out."

Increase `timeout_sec` in `moderation.yaml` to `120` or more, or set `timeout_action: score` to treat timeouts as passing during development.

## Key facts to communicate to the user

- `result.blocked` is `True` when at least one guard threshold is breached. Use `assert not result.blocked` to fail a test on bad responses.
- The `deployment_id` in `moderation.yaml` is the **judge LLM** that evaluates the agent output — not the agent's own LLM deployment. It must be exactly 24 hex characters.
- `faithfulness` requires `copy_citations: true` in YAML and `retrieved_contexts` in `evaluate_response()`.
- `TARGET_NAME` tells the moderations library which field in the deployment response contains generated text (for example `resultText`).
- `datarobot-moderations[all]` is already in `pyproject.toml` — do not add a duplicate dependency.
- For NAT/DRAgent projects, evaluate responses through `task agent:cli -- execute` (or equivalent NAT runtime path), not through `custompy_adaptor`.
- See [`docs/agent/evaluation.md`](../../docs/agent/evaluation.md) for full configuration options, troubleshooting, and best practices.
