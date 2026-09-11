# This fixture stands in for a rendered af-component-memory module.
#
# Paired with fixtures/.datarobot/answers/memory-memory.yml: that answers file
# is what tells the agent render this module is called `memory`, and this file
# is what makes the resulting `from ..memory import ...` resolve. Changing the
# name in one requires changing it in the other.
#
# It mirrors the component's export contract -- `custom_model_runtime_parameters`
# is what the agent imports, and the `memory_`-prefixed name is the component's
# own internal one, exported here too so the fixture stays faithful.
#
# Import-safe by design, like llm.py: it builds parameter values only and
# creates no Pulumi resources. The real component creates its own credential /
# MemorySpace; the agent only ever forwards the resulting values.
import pulumi_datarobot

memory_custom_model_runtime_parameters: list[
    pulumi_datarobot.CustomModelRuntimeParameterValueArgs
] = [
    pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
        key="AGENT_MEMORY_TTL_DAYS",
        type="string",
        value="30",
    ),
    # A credential the memory component already created. The agent must pass the
    # id through untouched, never re-create it.
    pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
        key="MEM0_API_KEY",
        type="credential",
        value="fixture-mem0-credential-id",
    ),
]

custom_model_runtime_parameters = memory_custom_model_runtime_parameters
