import logging 

from pydantic import Field
from nat_components.tools import plan, write, edit
from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

logger = logging.getLogger(__name__)


class PlanConfig(FunctionBaseConfig, name="plan"):
    description: str = Field(default=plan.__doc__)


@register_function(config_type=PlanConfig)
async def planner(config: PlanConfig, builder: Builder):


    # Yield the function info object which will be used to create a function
    yield FunctionInfo.from_fn(
        plan,
        description=plan.__doc__
    )


class WriteConfig(FunctionBaseConfig, name="write"):
    description: str = Field(default=write.__doc__)


@register_function(config_type=WriteConfig)
async def writer(config: WriteConfig, builder: Builder):

    # Yield the function info object which will be used to create a function
    yield FunctionInfo.from_fn(
        write,
        description=write.__doc__
    )


class EditConfig(FunctionBaseConfig, name="edit"):
    description: str = Field(default=edit.__doc__)


@register_function(config_type=EditConfig)
async def editor(config: EditConfig, builder: Builder):

    # Yield the function info object which will be used to create a function
    yield FunctionInfo.from_fn(
        edit,
        description=edit.__doc__
    )
