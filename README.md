# af-component-agent

The agent template provides a set of utilities for constructing a single or multi-agent flow using platforms such
as CrewAI, LangGraph, LlamaIndex, and others. The template is designed to be flexible and extensible, allowing you 
to create a wide range of agent-based applications.

The Agent Framework is component from [App Framework Studio](https://github.com/datarobot/app-framework-studio)


* Part of https://datarobot.atlassian.net/wiki/spaces/BOPS/pages/6542032899/App+Framework+-+Studio


## Instructions

To start for a repo:

`uvx copier copy https://github.com/datarobot/af-component-agent .`

If a template requires multiple agents, it can be used multiple times with a different answer to the `agent_app` question.

To work, it expects the base component https://github.com/datarobot/af-component-base has already been installed. To do that first, run:

`uvx copier copy https://github.com/datarobot/af-component-base .`


To update

`uvx copier update -a .datarobot/answers/agent-{{ agent_app }}.yml -A`

To update all templates that are copied:

`uvx copier update -a .datarobot/answers/* -A`

or just

`uvx copier update -a .datarobot/*`
