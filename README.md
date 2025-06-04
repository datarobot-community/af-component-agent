# af-component-agent

The agent template provides a set of utilities for constructing a single or multi-agent flow using platforms such
as CrewAI, LangGraph, LlamaIndex, and others. The template is designed to be flexible and extensible, allowing you
to create a wide range of agent-based applications.

The Agent Framework is component from [App Framework Studio](https://github.com/datarobot/app-framework-studio)


* Part of https://datarobot.atlassian.net/wiki/spaces/BOPS/pages/6542032899/App+Framework+-+Studio


## Getting Started

To use this template, it expects the base component https://github.com/datarobot/af-component-base has already been 
installed. To do that first, run:

```bash
# Using HTTPS
uvx copier copy https://github.com/datarobot/af-component-base .
# OR using SSH
uvx copier copy git@github.com:datarobot/af-component-base.git .
```

To add the agent component to your project, you can use the `uvx copier` command to copy the template from this repository:

```bash
# Using HTTPS
uvx copier copy https://github.com/datarobot/af-component-agent .
# OR using SSH
uvx copier copy git@github.com/datarobot/af-component-agent .
```

If a template requires multiple agents, it can be used multiple times with a different answer to the 
`agent_app_name` question.

To update an existing agent template, you can use the `uvx copier update` command. This will update the template files

```bash
uvx copier update -a .datarobot/answers/agent-{{ agent_app }}.yml -A
```


## Developer Guide

### af-component-agent

This is a template repo, and as such it is not easy to run tests and linters locally. To run tests and linters, 
you should open a PR against your branch. Tests will be run through github actions, and you can see the results
in the PR. If you are making large changes that may have significant impacts to the template installation
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
4. Create a new branch in the `recipe-datarobot-agent-templates` repository using the same name as the branch in the `af-component-agent` repository.
5. Run `task update-all-branch BRANCH=<your-branch-name>` in the `recipe-datarobot-agent-templates` repository to update the templates.
6. Open a PR against the `recipe-datarobot-agent-templates` repository and ensure tests are green.
7. Once all tests are green, merge the PR in the `af-component-agent` repository.
8. Create a new release in the `af-component-agent` repository to bump the version of the component.
9. Reset the state of `recipe-datarobot-agent-templates` by running `git reset --hard origin/main`.
10. Run `task update-all` to update the templates in the `recipe-datarobot-agent-templates` repository.
11. Force push the branch in the `recipe-datarobot-agent-templates` repository to update the templates and ensure tests are green.
12. Once everything is green and reviewed, merge the PR in the `recipe-datarobot-agent-templates` repository.

> You can also run `task` in the `recipe-datarobot-agent-templates` repository to see additional developer commands and their descriptions.
> These provide alternative ways to develop and test the templates inside the recipe repository.
