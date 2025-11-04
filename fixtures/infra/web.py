# This fixture is unused in tests because it is mocked, but is needed for mypy typing purposes.
import pulumi_datarobot

custom_model_credential_runtime_parameters: list[
    pulumi_datarobot.CustomModelRuntimeParameterValueArgs
] = []