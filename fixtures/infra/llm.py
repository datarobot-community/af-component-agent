# This fixture provides runtime parameters for E2E testing.
# These parameters configure the LLM Gateway and model for all agent frameworks.
# Matches the configuration used in recipe-datarobot-agent-templates.
import pulumi_datarobot

custom_model_runtime_parameters: list[
    pulumi_datarobot.CustomModelRuntimeParameterValueArgs
] = [
    # Enable DataRobot LLM Gateway for all agents (required for nat, helpful for others)
    # Uses "1" to match templates repo convention
    pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
        key="USE_DATAROBOT_LLM_GATEWAY",
        type="string",
        value="1",
    ),
    # Set the default LLM model for agents using LLM Gateway
    pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
        key="LLM_DEFAULT_MODEL",
        type="string",
        value="datarobot/azure/gpt-5-mini-2025-08-07",
    ),
    # Enable DRUM gunicorn/gevent server with a background event loop
    # so that async operations can run on DRUM's shared loop.
    pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
        key="CUSTOM_MODEL_WORKERS",
        type="numeric",
        value="1",
    ),
    pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
        key="DRUM_SERVER_TYPE",
        type="string",
        value="gunicorn",
    ),
    pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
        key="DRUM_GUNICORN_WORKER_CLASS",
        type="string",
        value="gevent",
    ),
    pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
        key="DRUM_WORKER_CONNECTIONS",
        type="numeric",
        value="100",
    ),
]
