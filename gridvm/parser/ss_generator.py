
from .ss_ast import *
from .ss_bcode import  Operation, OpCode


ARITHM_TABLE = {
        'ADD' : OpCode.ADD,
        'SUB' : OpCode.SUB,
        'MUL' : OpCode.MUL,
        'DIV' : OpCode.DIV,
        'MOD' : OpCode.MOD,
        }

class SSGenerator(object):
    """ Uses the same visitor pattern as ss_ast.NodeVisitor, but modified to
    build the bytecode version of the program simoultanously
    """
    def __init__(self):
        self.vars = dict()
        self.arrays = dict()
        self.consts = list()
        self.label_defs = dict()
        self.label_refs = dict()
        self.instructions = []

    def add_instruction(self, *args):
        self.instructions.append(Operation(*args))

    def fail(self, node, cause):
        print('Error: ' + cause)


    def visit(self, node):
        method = 'visit_' + node.__class__.__name__
        return getattr(self, method)(node)

    def visit_Program(self, node):
        for name, child in node.children():
            self.visit(child)

        return self.instructions

    def visit_Statement(self, node):
        next_index = len(self.instructions)

        self.visit(node.op)

        self.instructions[next_index].line_no = node.coord-1

    def visit_VarAccess(self, node):
        if node.var not in self.vars:
            self.fail('Undefined variable: ' + node.var)
        else:
            self.add_instruction(OpCode.LOAD_VAR, self.vars[node.var])

    def visit_Constant(self, node):
        try:
            index = self.consts.index(node.value)
        except ValueError:
            self.consts.append(node.value)
            index = len(self.consts) - 1
        self.add_instruction(OpCode.LOAD_CONST, index)

    def visit_ArrayAccess(self, node):
        if node.array not in self.arrays:
            self.fail('Undefined array: ' + node.array)

        #visit child to load index
        name, child = node.children()[0]
        self.visit(child)

        self.add_instruction(OpCode.LOAD_ARRAY, self.arrays[node.array])

    def build_var(self, node):
        if node.var not in self.vars:
            # Build if needed
            self.vars[node.var] = len(self.vars)
            self.add_instruction(OpCode.BUILD_VAR, len(self.vars) - 1)

        self.add_instruction(OpCode.STORE_VAR, self.vars[node.var])

    def build_array(self, node):
        if node.array not in self.arrays:
            # Build if needed
            self.arrays[node.array] = len(self.arrays)
            self.add_instruction(OpCode.BUILD_ARRAY, len(self.arrays) - 1)

        #same as access, but do a store instead
        self.visit_ArrayAccess(node)
        self.instructions.pop()
        self.add_instruction(OpCode.STORE_ARRAY, self.arrays[node.array])

    def build(self, node):
        method = 'build_' + node.__class__.__name__[:-6].lower()
        return getattr(self, method)(node)

    def visit_SetOperation(self, node):
        self.visit(node.var2)
        #stack has our value

        self.build(node.var1)

    def visit_ArithmOperation(self, node):
        self.visit(node.var2)
        self.visit(node.var3)

        self.add_instruction(ARITHM_TABLE[node.op])

        self.build(node.var1)



