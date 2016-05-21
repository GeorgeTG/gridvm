import struct

from enum import IntEnum, unique


OPERATION_FMT = 'BH'

class Operation(object):
    __slots__ = ('opcode', 'arg', 'line_no', '__weakref__')

    def __init__(self, opcode, arg=None, line_no=None):
        self.arg = arg
        self.line_no = line_no
        self.opcode = opcode

    def __str__(self):
        repr = ''
        if self.line_no:
            repr += '\n{}:'.format(self.line_no).ljust(6)
        else:
            repr += ' ' * 5

        repr += '[{:2d}]{}'.format(self.opcode.value, self.opcode.name).ljust(18)

        if self.arg is not None:
            repr += str(self.arg)

        return repr

    def to_bytes(self):
        arg = self.arg if self.arg else 0
        return struct.pack(OPERATION_FMT, self.opcode.value, arg)

    @classmethod
    def from_bytes(cls, buff):
        opcode, arg = struct.unpack(OPERATION_FMT)
        opcode = OpCode(opcode)

        return cls(opcode, arg)

@unique
class OpCode(IntEnum):
    LOAD_CONST   = 0
    LOAD_VAR     = 1
    STORE_VAR    = 2
    LOAD_ARRAY   = 3
    STORE_ARRAY  = 4
    BUILD_VAR    = 5
    BUILD_ARRAY  = 6
    ROT_TWO      = 7
    ADD          = 8
    SUB          = 9
    MUL          = 10
    DIV          = 11
    MOD          = 12
    COMPARE_OP   = 13
    JMP_IF_TRUE  = 14
    JMP          = 15
    SND         = 16
    RCV          = 17
    SLP          = 18
    PRN          = 19
    RET          = 20

