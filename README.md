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
  <a href="https://join.slack.com/t/datarobot-community/shared_invite/zt-3uzfp8k50-SUdMqeux25ok9_5wr4okrg">
    <img src="https://img.shields.io/badge/%23applications-a?label=Slack&labelColor=30373D&color=81FBA6" alt="Slack #applications">
  </a>
</p>

The agent component

The agent template provides a set of utilities for constructing a single or multi-agent workflow using frameworks such as NVIDIA NAT, CrewAI, LangGraph, LlamaIndex, and others. It is designed to be flexible and extensible for building a wide range of agent-based applications on DataRobot.

This component is part of the [DataRobot App Framework](https://af.datarobot.com), a modular system for building and deploying DataRobot-integrated applications. The repo ships agentic workflow templates for multiple frameworks, a CLI harness for local testing, and Pulumi-based infrastructure for end-to-end deployment. It targets app developers and platform engineers who want to add agentic AI capabilities to their DataRobot projects.

# Table of contents

- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [Component dependencies](#component-dependencies)
- [Troubleshooting](#troubleshooting)
- [Next steps and cross-links](#next-steps-and-cross-links)
- [Contributing, changelog, support, and legal](#contributing-changelog-support-and-legal)
- [Authentication and configuration](#authentication-and-configuration)
- [Deployment](#deployment)

# Prerequisites

The following tools are required before applying this component.

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) and [`uvx`](https://docs.astral.sh/uv/guides/tools/) installed.
- [`dr`](https://cli.datarobot.com) installed.
- A DataRobot account with API access and a valid API token.

# Quick start

Run the following command in the project directory:

```bash
dr component add https://github.com/datarobot-community/af-component-agent .
```

For additional control, use copier directly:

```bash
uvx copier copy datarobot-community/af-component-agent .
```

The wizard prompts for the agent name, framework choice (`base`, `crewai`, `langgraph`, `llamaindex`, or `nat`), and other configuration options. After the wizard completes, the project directory contains the agent template files ready for customization and deployment.

# Component dependencies

Apply the required components before this one, then use the following workflow to develop locally and keep everything up to date.

## Required

The following components must be applied to the project **before** this component:

| Name | Repository | Repeatable |
|------|-----------|------------|
| `base` | [https://github.com/datarobot-community/af-component-base](https://github.com/datarobot-community/af-component-base) | No |
| `llm` | [https://github.com/datarobot-community/af-component-llm](https://github.com/datarobot-community/af-component-llm) | Yes |

## Local development

The component ships a `Taskfile` with targets for running tests and linters locally.

To run tests and linters across all agent frameworks:

```bash
task test
```

To test an individual framework:

```bash
task test-AGENT_FRAMEWORK
```

To test the CLI on the base agent:

```bash
task test-cli
task test-cli-json
```

These targets mirror the checks CI runs on every pull request. Results are also visible in the GitHub Actions panel on the PR.

For full details on directory layout, hot paths, and service-by-service workflows, see the [development documentation](docs/development.md).

## Update

Update components regularly to pick up bug fixes, feature updates, and compatibility improvements for DataRobot App Framework.

To update automatically, run the following command in the project directory:

```bash
dr component update .datarobot/answers/agent-AGENT_APP_NAME.yml
```

For finer-grained control using copier directly, run:

```bash
uvx copier update -a .datarobot/answers/agent-AGENT_APP_NAME.yml -A
```

# Troubleshooting

If the component fails to apply or the agent does not start, check the following common issues first.

- **`uvx` or `dr` command not found** — ensure both tools are installed and on the `PATH`. Run `uv --version` and `dr --version` to confirm.
- **Authentication errors at startup** — verify that `DATAROBOT_ENDPOINT` and `DATAROBOT_API_TOKEN` are set correctly and that the token has the required permissions.
- **Framework import errors** — some frameworks have optional heavy dependencies. Run `task test-AGENT_FRAMEWORK` to isolate the failing framework and check its dependency group in `pyproject.toml`.
- **E2E test failures** — confirm that the DataRobot account has access to the deployment target and that the Pulumi local backend is writable.

For additional help:

- See the [agent documentation](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/index.html) for the chosen framework.
- [Contact DataRobot support](https://docs.datarobot.com/en/docs/get-started/troubleshooting/general-help.html)
- Open an issue on the [GitHub repository](https://github.com/datarobot-community/af-component-agent).

# Next steps and cross-links

After applying the component and verifying local tests pass, explore these resources to go further.

- Customize the workflow by editing the agent template files in `template/` for the chosen framework (`base`, `crewai`, `langgraph`, `llamaindex`, or `nat`).
- For changes with significant impact on template installation or user experience, open a branch in [recipe-datarobot-agent-templates](https://github.com/datarobot/recipe-datarobot-agent-templates) to validate end-to-end before merging.
- After merging a pull request, create a release in this repository to bump the component version. This is required for `dr component update` and downstream repos to pick up the changes.
- Browse the [DataRobot App Framework documentation](https://af.datarobot.com) for the full component catalog and architecture reference.

# Contributing, changelog, support, and legal

See [AUTHORS](AUTHORS) and [LICENSE](LICENSE) for authorship and licensing information.

Changelog entries are managed via [RELEASE.yaml](RELEASE.yaml). After merging a pull request, cut a release to publish the changelog and bump the component version.

To contribute, fork the repository, make changes on a branch, and open a pull request. Ensure `task test` passes before submitting. For additional guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md).

For support, see [Troubleshooting](#troubleshooting) or [contact DataRobot](https://docs.datarobot.com/en/docs/get-started/troubleshooting/general-help.html).

# Authentication and configuration

Set the following environment variables before running or deploying the agent:

```bash
export DATAROBOT_ENDPOINT=https://app.datarobot.com/api/v2
export DATAROBOT_API_TOKEN=YOUR_API_TOKEN
```

Alternatively, place these in a `.env` file at the project root instead of exporting them in the shell.

# Deployment

The component includes an optional end-to-end test that exercises a full lifecycle: **render → build → deploy → test → destroy**.

Set `DATAROBOT_ENDPOINT` and `DATAROBOT_API_TOKEN` as environment variables or in a local `.env` file, then run:

```bash
task test-e2e
```

Notes:

- By default the E2E test runs for all agent frameworks (`base`, `crewai`, `langgraph`, `llamaindex`, `nat`).
- To run a subset, set the `E2E_AGENT_FRAMEWORKS` variable, for example `E2E_AGENT_FRAMEWORKS=base,nat task test-e2e`.
- The test uses a local Pulumi backend and a unique stack name per run, then cleans up automatically afterward.
