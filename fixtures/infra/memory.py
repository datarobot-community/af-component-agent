# This fixture stands in for a rendered af-component-memory module.
#
# It mirrors that component's export contract -- the module name varies by
# provider, and what matters is that it defines
# `memory_custom_model_runtime_parameters` -- so the agent's discovery path can
# be exercised without a second component checkout.
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
