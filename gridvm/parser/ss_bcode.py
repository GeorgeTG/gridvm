#-----------------------------------------------------------------
# ** ATTENTION **
# This code was automatically generated from the file:
# bcode.decl
#
# Do not modify it directly. Modify the configuration file and
# run the generator again.
# ** ** *** ** **
#
# gridvm: ss_bcode.py
#
# ByteCode classes.
#
#-----------------------------------------------------------------


class Operation(obbject):
    pass

class OpSetv(Operation):
    __opcode__ = 0
    __slots__ = ('var', 'val',  '__weakref__',)

    def __init__(self, var, val):
        self.var = Parameter(var, ParameterType.VAR)
        self.val = Parameter(val, ParameterType.CONST)

    params = ('var', 'val')

class OpMovv(Operation):
    __opcode__ = 1
    __slots__ = ('var', 'var',  '__weakref__',)

    def __init__(self, var, var):
        self.var = Parameter(var, ParameterType.VAR)
        self.var = Parameter(var, ParameterType.VAR)

    params = ('var', 'var')

class OpSeta(Operation):
    __opcode__ = 2
    __slots__ = ('arr', 'val',  '__weakref__',)

    def __init__(self, arr, val):
        self.arr = Parameter(arr, ParameterType.ARRAY)
        self.val = Parameter(val, ParameterType.CONST)

    params = ('arr', 'val')

class OpPushv(Operation):
    __opcode__ = 3
    __slots__ = ('var',  '__weakref__',)

    def __init__(self, var):
        self.var = Parameter(var, ParameterType.VAR)

    params = ('var',)

class OpPusha(Operation):
    __opcode__ = 4
    __slots__ = ('arr',  '__weakref__',)

    def __init__(self, arr):
        self.arr = Parameter(arr, ParameterType.ARRAY)

    params = ('arr',)

class OpAdd(Operation):
    __opcode__ = 5
    __slots__ = ('var1', 'var2', 'var3',  '__weakref__',)

    def __init__(self, var1, var2, var3):
        self.var1 = Parameter(var1, ParameterType.VAR)
        self.var2 = Parameter(var2, ParameterType.STACK)
        self.var3 = Parameter(var3, ParameterType.STACK)

    params = ('var1', 'var2', 'var3')

class OpSub(Operation):
    __opcode__ = 6
    __slots__ = ('var1', 'var2', 'var3',  '__weakref__',)

    def __init__(self, var1, var2, var3):
        self.var1 = Parameter(var1, ParameterType.VAR)
        self.var2 = Parameter(var2, ParameterType.STACK)
        self.var3 = Parameter(var3, ParameterType.STACK)

    params = ('var1', 'var2', 'var3')

class OpMul(Operation):
    __opcode__ = 7
    __slots__ = ('var1', 'var2', 'var3',  '__weakref__',)

    def __init__(self, var1, var2, var3):
        self.var1 = Parameter(var1, ParameterType.VAR)
        self.var2 = Parameter(var2, ParameterType.STACK)
        self.var3 = Parameter(var3, ParameterType.STACK)

    params = ('var1', 'var2', 'var3')

class OpDiv(Operation):
    __opcode__ = 8
    __slots__ = ('var1', 'var2', 'var3',  '__weakref__',)

    def __init__(self, var1, var2, var3):
        self.var1 = Parameter(var1, ParameterType.VAR)
        self.var2 = Parameter(var2, ParameterType.STACK)
        self.var3 = Parameter(var3, ParameterType.STACK)

    params = ('var1', 'var2', 'var3')

class OpMod(Operation):
    __opcode__ = 9
    __slots__ = ('var1', 'var2', 'var3',  '__weakref__',)

    def __init__(self, var1, var2, var3):
        self.var1 = Parameter(var1, ParameterType.VAR)
        self.var2 = Parameter(var2, ParameterType.STACK)
        self.var3 = Parameter(var3, ParameterType.STACK)

    params = ('var1', 'var2', 'var3')

class OpJpm(Operation):
    __opcode__ = 10
    __slots__ = ('label',  '__weakref__',)

    def __init__(self, label):
        self.label = Parameter(label, ParameterType.CONST)

    params = ('label',)

class OpJpmc(Operation):
    __opcode__ = 11
    __slots__ = ('var1', 'label',  '__weakref__',)

    def __init__(self, var1, label):
        self.var1 = Parameter(var1, ParameterType.STACK)
        self.label = Parameter(label, ParameterType.CONST)

    params = ('var1', 'label')

class OpSnd(Operation):
    __opcode__ = 12
    __slots__ = ('var1', 'var2',  '__weakref__',)

    def __init__(self, var1, var2):
        self.var1 = Parameter(var1, ParameterType.STACK)
        self.var2 = Parameter(var2, ParameterType.STACK)

    params = ('var1', 'var2')

class OpRcv(Operation):
    __opcode__ = 13
    __slots__ = ('var1', 'var2',  '__weakref__',)

    def __init__(self, var1, var2):
        self.var1 = Parameter(var1, ParameterType.VAR)
        self.var2 = Parameter(var2, ParameterType.STACK)

    params = ('var1', 'var2')

class OpRet(Operation):
    __opcode__ = 14
    __slots__ = ( '__weakref__',)

    def __init__(self, ):
        pass


class OpPrn(Operation):
    __opcode__ = 15
    __slots__ = ('offset', 'total',  '__weakref__',)

    def __init__(self, offset, total):
        self.offset = Parameter(offset, ParameterType.DATA)
        self.total = Parameter(total, ParameterType.CONST)

    params = ('offset', 'total')

class OpSlp(Operation):
    __opcode__ = 16
    __slots__ = ('var1',  '__weakref__',)

    def __init__(self, var1):
        self.var1 = Parameter(var1, ParameterType.STACK)

    params = ('var1',)


from enum import IntEnum, unique

@unique
class OpCode(IntEnum):
    SETV  = 0
    MOVV  = 1
    SETA  = 2
    PUSHV = 3
    PUSHA = 4
    ADD   = 5
    SUB   = 6
    MUL   = 7
    DIV   = 8
    MOD   = 9
    JPM   = 10
    JPMC  = 11
    SND   = 12
    RCV   = 13
    RET   = 14
    PRN   = 15
    SLP   = 16
