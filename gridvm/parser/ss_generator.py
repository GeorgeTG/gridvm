
from .ss_ast import NodeVisitor
from .ss_bcode import *


class CGenerator(object):
    """ Uses the same visitor pattern as c_ast.NodeVisitor, but modified to
    return a value from each visit method, using string accumulation in
    generic_visit.
    """
    def __init__(self):
        self.vars = dict()
        self.arrays = dict()
        self.label_defs = dict()
        self.label_refs = dict()
        :

    def visit(self, node):
        method = 'visit_' + node.__class__.__name__
        return getattr(self, method, self.generic_visit)(node)

    def generic_visit(self, node):
        #~ print('generic:', type(node))
        if node is None:
            return ''
        else:
            return ''.join(self.visit(c) for c_name, c in node.children())
