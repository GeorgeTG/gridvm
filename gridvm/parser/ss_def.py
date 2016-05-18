
from enum import IntEnum, unique
@unique
class ParameterType(IntEnum):
    CONST = 0
    VAR = 1
    ARRAY = 2
    STACK = 3
    DATA = 4

