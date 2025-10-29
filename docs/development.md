# Developer Guide

### af-component-agent

To run tests and linters locally on all agent frameworks you can run `task test`. To test an individual
framework you can run `task test-<agent_framework>`. To test the CLI on the base agent you can run `task test-cli`
and `task test-cli-json`. These are equivalent to the tests when you open a PR against your branch.
Tests will be run through github actions, and you can see the results in the PR. If you are making large changes 
that may have significant impacts to the template installation
and usage, you should additionally open a branch in [recipe-datarobot-agent-templates](https://github.com/datarobot/recipe-datarobot-agent-templates).

> After committing a PR you should create a new release in this repository to bump the version of the component.
> This is required to properly work with the `uvx copier` command and to ensure that the changes are reflected in the
> downstream repositories.

### recipe-datarobot-agent-templates
This repository is used to generate the customer facing recipe repository and provides an alternative way to test the
templates. This can also be used to verify that changes to the template do not produce unexpected results in the
generated code.

To co-develop a PR in the `recipe` and the `template` use the following development flow:
1. Create a new branch in the `af-component-agent` repository.
2. Make your changes to the template files.
3. Open a PR against the `af-component-agent` repository and ensure tests are green.
4. Once all tests are green, merge the PR in the `af-component-agent` repository.
5. Create a new release in the `af-component-agent` repository to bump the version of the component.
6. Start a new PR to `recipe-datarobot-agent-templates`.
7. Run `task development:update-all` to update the templates in the `recipe-datarobot-agent-templates` repository with the latest version of `af-component-agent`.
8. Once everything is green and reviewed, merge the PR in the `recipe-datarobot-agent-templates` repository.

> You can also run `task` in the `recipe-datarobot-agent-templates` repository to see additional developer commands and their descriptions.
> These provide alternative ways to develop and test the templates inside the recipe repository.
