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
