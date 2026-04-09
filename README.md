<p align="center">
  <a href="https://github.com/datarobot-community/af-component-agent">
    <img src="https://af.datarobot.com/img/datarobot_logo.avif" width="600px" alt="DataRobot Logo"/>
  </a>
</p>
<p align="center">
    <span style="font-size: 1.5em; font-weight: bold; display: block;">af-component-agent</span>
</p>

<p align="center">
  <a href="https://datarobot.com">Homepage</a>
  ·
  <a href="https://af.datarobot.com">Documentation</a>
  ·
  <a href="https://docs.datarobot.com/en/docs/get-started/troubleshooting/general-help.html">Support</a>
</p>

<p align="center">
  <a href="https://github.com/datarobot-community/af-component-agent/tags">
    <img src="https://img.shields.io/github/v/tag/datarobot-community/af-component-agent?label=version" alt="Latest Release">
  </a>
  <a href="/LICENSE">
    <img src="https://img.shields.io/github/license/datarobot-community/af-component-agent" alt="License">
  </a>
</p>

The agent component

The agent template provides a set of utilities for constructing a single or multi-agent workflow using
frameworks such as Nvidia NAT, CrewAI, LangGraph, LlamaIndex, and others. The template is designed to
be flexible and extensible, allowing you to create a wide range of agent-based applications.

This component is part of the [DataRobot App Framework](https://af.datarobot.com).

# Table of contents

- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [Component dependencies](#component-dependencies)
- [Authentication and configuration](#authentication-and-configuration)
- [Local development](#local-development)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Next steps and cross-links](#next-steps-and-cross-links)
- [Contributing, changelog, support, and legal](#contributing-changelog-support-and-legal)

# Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) and [`uvx`](https://docs.astral.sh/uv/guides/tools/) installed
- [`dr`](https://cli.datarobot.com) installed
- The [`base`](https://github.com/datarobot-community/af-component-base) component applied to your project before this component

# Quick start

Run the following command in your project directory:

```bash
dr component add https://github.com/datarobot-community/af-component-agent .
```

Alternatively, you can use `uvx` copier:

```bash
uvx copier copy datarobot-community/af-component-agent .
```

To update an existing agent component installation:

```bash
uvx copier update -a .datarobot/answers/agent-<agent_app>.yml -A
```

# Component dependencies

## Required

The following components must be applied to the project **before** this component:

| Name | Repository | Repeatable |
|------|-----------|------------|
| `base` | [https://github.com/datarobot-community/af-component-base](https://github.com/datarobot-community/af-component-base) | No |
| `llm` | [https://github.com/datarobot-community/af-component-llm](https://github.com/datarobot-community/af-component-llm) | Yes |
| `mcp` | [https://github.com/datarobot-community/af-component-fastmcp-server](https://github.com/datarobot-community/af-component-fastmcp-server) | Yes |

# Authentication and configuration

Set the following environment variables before running or deploying the agent:

```bash
export DATAROBOT_ENDPOINT=https://app.datarobot.com/api/v2
export DATAROBOT_API_TOKEN=<your-api-token>
```

These can also be placed in a `.env` file at the root of your project.

# Local development

To run tests and linters locally on all agent frameworks:

```bash
task test
```

To test an individual framework:

```bash
task test-<agent_framework>
```

To test the CLI on the base agent:

```bash
task test-cli
task test-cli-json
```

These are equivalent to the checks run when you open a PR. Tests are also run through GitHub Actions and results are visible in the PR.

For full details, see the [Development Documentation](docs/development.md).

# Deployment

This repo includes an optional end-to-end test that exercises a full lifecycle:
**render → build → deploy → test → destroy**.

**Prerequisites**: set `DATAROBOT_ENDPOINT` and `DATAROBOT_API_TOKEN` either as environment variables or in a local `.env` file.

```bash
task test-e2e
```

Notes:
- By default the E2E test runs for **all agent frameworks** (`base`, `crewai`, `langgraph`, `llamaindex`, `nat`).
- To run a subset, set `E2E_AGENT_FRAMEWORKS`, e.g. `E2E_AGENT_FRAMEWORKS=base,nat`.
- The test uses a local Pulumi backend and a unique stack name per run, then cleans up.

# Troubleshooting

If you encounter issues or have questions:

- Check the [Agent Documentation](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/index.html) for your chosen framework.
- [Contact DataRobot](https://docs.datarobot.com/en/docs/get-started/troubleshooting/general-help.html) for support.
- Open an issue on the [GitHub repository](https://github.com/datarobot-community/af-component-agent).

# Next steps and cross-links

- After applying the agent component, explore the agent templates in `template/` to customize your workflow for your chosen framework (`base`, `crewai`, `langgraph`, `llamaindex`, or `nat`).
- If you are making large changes with significant impact to template installation and usage, open a branch in [recipe-datarobot-agent-templates](https://github.com/datarobot/recipe-datarobot-agent-templates).
- After merging a PR, create a new release in this repository to bump the component version — required for `uvx copier` and downstream repos to pick up the changes.

# Contributing, changelog, support, and legal

See [AUTHORS](AUTHORS) and [LICENSE](LICENSE) for authorship and licensing information.

Changelog entries are managed via [RELEASE.yaml](RELEASE.yaml). After merging a PR, cut a new release to publish the changelog and bump the component version.

For support, refer to the [Troubleshooting](#troubleshooting) section above or [contact DataRobot](https://docs.datarobot.com/en/docs/get-started/troubleshooting/general-help.html).
