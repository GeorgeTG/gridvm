from enum import IntEnum, unique


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

        opcode = OpCode(self.opcode)
        repr += '[{:2d}]{}'.format(opcode.value, opcode.name).ljust(18)

        if self.arg is not None:
            repr += str(self.arg)

        return repr

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
    ARITHM       = 8
    COMPARE_OP   = 9
    JMP_IF_TRUE  = 10
    JMP          = 11
    SND          = 12
    RCV          = 13
    SLP          = 14
    PRN          = 15
    RET          = 16
    NOP          = 17
