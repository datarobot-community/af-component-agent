from pydantic import BaseModel
import math

Numeric = float | int

class NatCalculatorInputs(BaseModel):
    x: Numeric
    y: Numeric

async def multiply(inputs: NatCalculatorInputs) -> Numeric:
    """Multiplys the input x * Y requires both input to be 
    float or int"""
    return inputs.x * inputs.y

async def add(inputs: NatCalculatorInputs) -> Numeric:
    """Adds the input x + Y requires both input to be 
    float or int"""
    return inputs.x + inputs.y

async def subtract(inputs: NatCalculatorInputs) -> Numeric:
    """subtracks the input x  Y requires both input to be 
    float or int"""
    return inputs.x - inputs.y

async def divide(inputs: NatCalculatorInputs) -> Numeric:
    """divides the input x/Y requires both input to be 
    float or int"""
    return inputs.x / inputs.y

async def power(inputs: NatCalculatorInputs) -> Numeric:
    """Calculates x raised to the power of y (x^y) requires both input to be 
    float or int"""
    return inputs.x ** inputs.y

async def modulo(inputs: NatCalculatorInputs) -> Numeric:
    """Calculates the remainder of x divided by y (x % y) requires both input to be 
    float or int"""
    return inputs.x % inputs.y

async def sin(inputs: NatCalculatorInputs) -> Numeric:
    """Calculates the sine of x (in radians)
    Uses only the x input, y is ignored"""
    return math.sin(inputs.x)

async def cos(inputs: NatCalculatorInputs) -> Numeric:
    """Calculates the cosine of x (in radians)
    Uses only the x input, y is ignored"""
    return math.cos(inputs.x)

async def tan(inputs: NatCalculatorInputs) -> Numeric:
    """Calculates the tangent of x (in radians)
    Uses only the x input, y is ignored"""
    return math.tan(inputs.x)

