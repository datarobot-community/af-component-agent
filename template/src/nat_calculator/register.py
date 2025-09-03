import logging 

from pydantic import Field, BaseModel
from nat_calculator.tools import add, multiply, subtract, divide, power, modulo, sin, cos, tan

from nat.builder.builder import Builder
from nat.builder.function import LambdaFunction
from nat.builder.framework_enum import LLMFrameworkEnum
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.component_ref import FunctionRef
from nat.data_models.component_ref import LLMRef
from nat.data_models.function import FunctionBaseConfig

logger = logging.getLogger(__name__)




# Create a function info
add_function_info = FunctionInfo.from_fn(
    add,
    description=add.__doc__
)

class AddConfig(FunctionBaseConfig, name="add"):
    description: str = Field(default=add.__doc__)


@register_function(config_type=AddConfig)
async def adder(config: AddConfig, builder: Builder):


    # Yield the function info object which will be used to create a function
    yield FunctionInfo.from_fn(
        add,
        description=add.__doc__
    )


class MultiplyConfig(FunctionBaseConfig, name="multiply"):
    description: str = Field(default=multiply.__doc__)


@register_function(config_type=MultiplyConfig)
async def multiplier(config: MultiplyConfig, builder: Builder):

    # Yield the function info object which will be used to create a function
    yield FunctionInfo.from_fn(
        multiply,
        description=multiply.__doc__
    )


class SubtractConfig(FunctionBaseConfig, name="subtract"):
    description: str = Field(default=subtract.__doc__)


@register_function(config_type=SubtractConfig)
async def subtractor(config: SubtractConfig, builder: Builder):

    # Yield the function info object which will be used to create a function
    yield FunctionInfo.from_fn(
        subtract,
        description=subtract.__doc__
    )


class DivideConfig(FunctionBaseConfig, name="divide"):
    description: str = Field(default=divide.__doc__)


@register_function(config_type=DivideConfig)
async def divider(config: DivideConfig, builder: Builder):

    # Yield the function info object which will be used to create a function
    yield FunctionInfo.from_fn(
        divide,
        description=divide.__doc__
    )


class PowerConfig(FunctionBaseConfig, name="power"):
    description: str = Field(default=power.__doc__)


@register_function(config_type=PowerConfig)
async def power_calculator(config: PowerConfig, builder: Builder):

    # Yield the function info object which will be used to create a function
    yield FunctionInfo.from_fn(
        power,
        description=power.__doc__
    )


class ModuloConfig(FunctionBaseConfig, name="modulo"):
    description: str = Field(default=modulo.__doc__)


@register_function(config_type=ModuloConfig)
async def modulo_calculator(config: ModuloConfig, builder: Builder):

    # Yield the function info object which will be used to create a function
    yield FunctionInfo.from_fn(
        modulo,
        description=modulo.__doc__
    )


class SinConfig(FunctionBaseConfig, name="sin"):
    description: str = Field(default=sin.__doc__)


@register_function(config_type=SinConfig)
async def sin_calculator(config: SinConfig, builder: Builder):

    # Yield the function info object which will be used to create a function
    yield FunctionInfo.from_fn(
        sin,
        description=sin.__doc__
    )


class CosConfig(FunctionBaseConfig, name="cos"):
    description: str = Field(default=cos.__doc__)


@register_function(config_type=CosConfig)
async def cos_calculator(config: CosConfig, builder: Builder):

    # Yield the function info object which will be used to create a function
    yield FunctionInfo.from_fn(
        cos,
        description=cos.__doc__
    )


class TanConfig(FunctionBaseConfig, name="tan"):
    description: str = Field(default=tan.__doc__)


@register_function(config_type=TanConfig)
async def tan_calculator(config: TanConfig, builder: Builder):

    # Yield the function info object which will be used to create a function
    yield FunctionInfo.from_fn(
        tan,
        description=tan.__doc__
    )