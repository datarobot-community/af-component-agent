import os

import pulumi_datarobot

custom_model_runtime_parameters: list[
    pulumi_datarobot.CustomModelRuntimeParameterValueArgs
] = []

# Add LLM deployment ID as a runtime parameter if set
if os.environ.get("LLM_DEPLOYMENT_ID"):
    custom_model_runtime_parameters.append(
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="LLM_DEPLOYMENT_ID",
            type="string",
            value=os.environ["LLM_DEPLOYMENT_ID"],
        )
    )
