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

The agent template provides a set of utilities for constructing a single or multi-agent workflow using frameworks such as Nvidia NAT, CrewAI, LangGraph, LlamaIndex, and others. It's designed to be flexible and extensible, allowing you to create a wide range of agent-based applications on DataRobot.

This component is part of the [DataRobot App Framework](https://af.datarobot.com), a modular system for building and deploying DataRobot-integrated applications. The repo ships agentic workflow templates for multiple frameworks, a CLI harness for local testing, and Pulumi-based infrastructure for end-to-end deployment. It targets app developers and platform engineers who want to add agentic AI capabilities to their DataRobot projects.

# Table of contents

- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [Component dependencies](#component-dependencies)
- [Authentication and configuration](#authentication-and-configuration)
- [Local development](#local-development)
- [Updating](#updating)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Next steps and cross-links](#next-steps-and-cross-links)
- [Contributing, changelog, support, and legal](#contributing-changelog-support-and-legal)

# Prerequisites

The following tools are required before applying this component.

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) and [`uvx`](https://docs.astral.sh/uv/guides/tools/) installed.
- [`dr`](https://cli.datarobot.com) installed.
- A DataRobot account with API access and a valid API token.

# Quick start

Run the following command in your project directory:

```bash
dr component add https://github.com/datarobot-community/af-component-agent .
```

If you need additional control, you can run this to use copier directly:

```bash
uvx copier copy datarobot-community/af-component-agent .
```

The wizard prompts you for your agent name, framework choice (`base`, `crewai`, `langgraph`, `llamaindex`, or `nat`), and other configuration options. After the wizard completes, your project directory contains the agent template files ready for customization and deployment.

# Component dependencies

## Required

The following components must be applied to the project **before** this component:

| Name | Repository | Repeatable |
|------|-----------|------------|
| `base` | [https://github.com/datarobot-community/af-component-base](https://github.com/datarobot-community/af-component-base) | No |
| `llm` | [https://github.com/datarobot-community/af-component-llm](https://github.com/datarobot-community/af-component-llm) | Yes |
| `mcp` | [https://github.com/datarobot-community/af-component-datarobot-mcp](https://github.com/datarobot-community/af-component-datarobot-mcp) | Yes |

# Authentication and configuration

Set the following environment variables before running or deploying the agent:

```bash
export DATAROBOT_ENDPOINT=https://app.datarobot.com/api/v2
export DATAROBOT_API_TOKEN=YOUR_API_TOKEN
```

You can also place these in a `.env` file at the root of your project instead of exporting them in your shell.

# Local development

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

These targets mirror the checks run in CI when you open a pull request. Results are also visible in the GitHub Actions panel on the PR.

For full details on directory layout, hot paths, and service-by-service workflows, see the [development documentation](docs/development.md).

# Updating

All components should be regularly updated to pick up bug fixes, new features, and compatibility with the latest DataRobot App Framework.

For automatic updates to the latest version, run the following command in your project directory:

```bash
dr component update .datarobot/answers/agent-AGENT_APP_NAME.yml
```

If you need more fine-grained control and prefer using copier directly, you can run this to have more control over the process:

```bash
uvx copier update -a .datarobot/answers/agent-AGENT_APP_NAME.yml -A
```

# Deployment

The component includes an optional end-to-end test that exercises a full lifecycle: **render → build → deploy → test → destroy**.

Set `DATAROBOT_ENDPOINT` and `DATAROBOT_API_TOKEN` as environment variables or in a local `.env` file, then run:

```bash
task test-e2e
```

Notes:

- By default the E2E test runs for all agent frameworks (`base`, `crewai`, `langgraph`, `llamaindex`, `nat`).
- To run a subset, set the `E2E_AGENT_FRAMEWORKS` variable, for example `E2E_AGENT_FRAMEWORKS=base,nat task test-e2e`.
- The test uses a local Pulumi backend and a unique stack name per run, then cleans up after itself.

# Troubleshooting

If the component fails to apply or your agent does not start, check the following common issues first.

- **`uvx` or `dr` command not found**&mdash;ensure both tools are installed and on your `PATH`. Run `uv --version` and `dr --version` to confirm.
- **Authentication errors at startup**&mdash;verify that `DATAROBOT_ENDPOINT` and `DATAROBOT_API_TOKEN` are set correctly and that the token has the required permissions.
- **Framework import errors**&mdash;some frameworks have optional heavy dependencies. Run `task test-AGENT_FRAMEWORK` to isolate the failing framework and check its dependency group in `pyproject.toml`.
- **E2E test failures**&mdash;confirm that your DataRobot account has access to the deployment target and that the Pulumi local backend is writable.

For additional help:

- See the [agent documentation](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/index.html) for your chosen framework.
- [Contact DataRobot support](https://docs.datarobot.com/en/docs/get-started/troubleshooting/general-help.html).
- Open an issue on the [GitHub repository](https://github.com/datarobot-community/af-component-agent).

# Next steps and cross-links

After applying the component and verifying local tests pass, explore these resources to go further.

- Customize your workflow by editing the agent template files in `template/` for your chosen framework (`base`, `crewai`, `langgraph`, `llamaindex`, or `nat`).
- If your changes have significant impact on template installation or user experience, open a branch in [recipe-datarobot-agent-templates](https://github.com/datarobot/recipe-datarobot-agent-templates) to validate end-to-end before merging.
- After merging a pull request, create a new release in this repository to bump the component version&mdash;required for `dr component update` and downstream repos to pick up your changes.
- Browse the [DataRobot App Framework documentation](https://af.datarobot.com) for the full component catalog and architecture reference.

# Contributing, changelog, support, and legal

See [AUTHORS](AUTHORS) and [LICENSE](LICENSE) for authorship and licensing information.

Changelog entries are managed via [RELEASE.yaml](RELEASE.yaml). After merging a pull request, cut a new release to publish the changelog and bump the component version.

To contribute, fork the repository, make your changes on a branch, and open a pull request. Ensure `task test` passes before submitting. See [CONTRIBUTING.md](CONTRIBUTING.md) if present for additional guidelines.

For support, see the [troubleshooting](#troubleshooting) section above or [contact DataRobot](https://docs.datarobot.com/en/docs/get-started/troubleshooting/general-help.html).
