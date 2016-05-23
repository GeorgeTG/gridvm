from .ss_bcode import  Operation, OpCode
from .ss_code import SimpleScriptCodeObject

from ..parser.ss_ast import *
from ..ss_exception import GeneratorException

ARITHM_TABLE = {
        'ADD' : 0,
        'SUB' : 1,
        'MUL' : 2,
        'DIV' : 3,
        'MOD' : 4,
        }

BRANCH_CMP_OPS = {
        'GT': 0, # >
        'GE': 1, # >=
        'LT': 2, # <
        'LE': 3, # <=
        'EQ': 4  # ==
        }

def invert_map(map):
    return { v:k for k,v in map.items() }

def list_from_mapping(map):
    inv = invert_map(map)
    return list( (inv[index] for index in range(len(inv))) )


class SimpleScriptGenerator(object):
    """ Uses the same visitor pattern as ss_ast.NodeVisitor, but modified to
    build the bytecode version of the program simoultanously
    """
    def __init__(self):
        self.vars = { '$argc' : 0 }
        self.arrays = { '$argv' : 0 }
        self.consts = list()

        self.label_defs = dict()
        self.label_refs = list()

        self.next_line = 0
        self.instructions = []

    def add_instruction(self, *args):
        self.instructions.append(Operation(*args))

    def fail(self, cause):
        raise GeneratorException(self.next_line, cause)

    def _fix_labels(self):
        labels = []
        for index in self.label_refs:
            instruction = self.instructions[index]
            try:
                label_index = self.label_defs[instruction.arg]

                try:
                    # more than one refs exist
                    index = labels.index(label_index)
                except ValueError:
                    # add index to jump table
                    labels.append(label_index)
                    index = len(labels) - 1

                # replace the arg, with the table's index
                instruction.arg = index
            except KeyError:
                # No such label
                self.fail('Label "{}" not defined'.format(instruction.arg))

        self.labels_table = labels

    def generate(self, tree):
        if not isinstance(tree, Program):
            raise ValueError('Bad tree')
        self.visit(tree)

        self._fix_labels()

        return SimpleScriptCodeObject(
                instructions=self.instructions,
                consts=self.consts,
                vars=list_from_mapping(self.vars),
                arrays=list_from_mapping(self.arrays),
                labels=self.labels_table,
                label_names=invert_map(self.label_defs))

    def visit(self, node):
        method = 'visit_' + node.__class__.__name__
        return getattr(self, method)(node)

    def visit_Program(self, node):
        for name, child in node.children():
            self.visit(child)


    def visit_Statement(self, node):
        next_index = len(self.instructions)
        if node.label:
            self.label_defs[node.label.name] = next_index

        self.visit(node.op)

        self.instructions[next_index].line_no = node.coord-1
        self.next_line = node.coord - 1

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

        self.add_instruction(OpCode.ARITHM, ARITHM_TABLE[node.op])

        self.build(node.var1)

    def visit_BranchOperation(self, node):
        if node.op != 'BRA':
            self.visit(node.var1)
            self.visit(node.var2)

            self.add_instruction(OpCode.COMPARE_OP, BRANCH_CMP_OPS[node.op[1:]])
            self.add_instruction(OpCode.JMP_IF_TRUE, node.label.name)
        else:
            # jump always
            self.add_instruction(OpCode.JMP, node.label.name)

        # fix labels later
        self.label_refs.append(len(self.instructions) - 1)

    def visit_NetOperation(self, node):
        # WARN: thread id is var1
        if node.op == 'SND':
            self.visit(node.var1)
            self.visit(node.var2)
            self.add_instruction(OpCode.SND)
        else:
            self.visit(node.var1)
            self.add_instruction(OpCode.RCV)
            self.build(node.var2)

    def visit_SleepOperation(self, node):
        self.visit(node.var1)
        self.add_instruction(OpCode.SLP)

    def visit_PrintOperation(self, node):
        try:
            # avoid duplicate strings in consts
            value = self.consts.index(node.formatter)
        except ValueError:
            self.consts.append(node.formatter)
            value = len(self.consts) - 1

        try:
            index = self.consts.index(value)
        except ValueError:
            self.consts.append(value)
            index = len(self.consts) - 1

        self.add_instruction(OpCode.LOAD_CONST, index)

        vector = node.vect or [] # can be None
        for name, child in node.children():
            self.visit(child)

        self.add_instruction(OpCode.PRN, len(vector))

    def visit_Ret(self, node):
        self.add_instruction(OpCode.RET)



