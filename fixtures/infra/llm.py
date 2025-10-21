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


# These internal implementation details should never be accessed by tests
# If accessed, they will raise exceptions to validate the mock is working
def _internal_function():
    raise RuntimeError(
        "Internal llm module function accessed. Tests should only use "
        "custom_model_runtime_parameters."
    )


_internal_variable = property(
    lambda self: (_ for _ in ()).throw(
        RuntimeError(
            "Internal llm module variable accessed. Tests should only use "
            "custom_model_runtime_parameters."
        )
    )
)
