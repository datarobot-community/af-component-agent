# DataRobot Agent Template
The agent template provides a set of utilities for constructing a single or multi-agent flow using platforms such
as CrewAI, LangGraph, LlamaIndex, and others. The template is designed to be flexible and extensible, allowing you 
to create a wide range of agent-based applications.

## Agent Development
The agent is developed by modifying the `custom_model` code. There are several things to consider:
- The agent itself lives within the `my_agent_class` sub-package. If renamed, please adjust the imports in `custom.py`.
- `custom.py` provides the entry point for the agent. It typically does not need modifications, but can be adjusted if the inputs need to be changed.
- Additional packages if needed can be added to `docker_context/requirements-agent.txt`.

A series of `Makefile` commands can be used to help you develop and prototype the agent more quickly:
- `make req` - setup a uv virtual environment locally that is compatible with `docker_context`.
- `make lint` - run linting on the agent code.
- `make test` - run the tests on the agent code.

## Agent CLI
The agent CLI is a command line interface that allows you to interact with and execute the agent locally or remotely
(through either codespaces or a deployment). This allows you to quickly test changes to the agent code without needing 
to deploy the agent to a remote environment. The CLI is built using the `click` library. The CLI utilizes your
environment variables from the root project `.env` file.

```bash
Usage: cli.py [OPTIONS] COMMAND [ARGS]...

  A CLI for interacting with ExecutorInterface.

Options:
  --codespace_id TEXT  Codespace ID for the session.
  --api_token TEXT     API token for authentication.
  --base_url TEXT      Base URL for the API.
  --help               Show this message and exit.

Commands:
  deployment      Query a deployed model using the command line for testing.
  download        Download files from CodeSpaces to local environment.
  execute-local   Execute agent using local code.
  execute-remote  Execute agent using code in CodeSpaces.
  start           Start a CodeSpaces in DataRobot.
  stop            Stop a CodeSpaces in DataRobot.
  upload          Upload files from local environment to CodeSpaces.
```