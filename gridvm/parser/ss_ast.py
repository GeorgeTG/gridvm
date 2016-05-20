#-----------------------------------------------------------------
# ** ATTENTION **
# This code was automatically generated from the file:
# tree.decl
#
# Do not modify it directly. Modify the configuration file and
# run the generator again.
# ** ** *** ** **
#
# gridvm,: ss_ast.py
#
# AST Node classes.
#
#-----------------------------------------------------------------


import sys


class Node(object):
    __slots__ = ()
    """ Abstract base class for AST nodes.
    """
    def children(self):
        """ A sequence of all children that are Nodes
        """
        pass

    def show(self, buf=sys.stdout, offset=0, attrnames=False, nodenames=False, showcoord=False, _my_node_name=None):
        """ Pretty print the Node and all its attributes and
            children (recursively) to a buffer.

            buf:
                Open IO buffer into which the Node is printed.

            offset:
                Initial offset (amount of leading spaces)

            attrnames:
                True if you want to see the attribute names in
                name=value pairs. False to only see the values.

            nodenames:
                True if you want to see the actual node names
                within their parents.

            showcoord:
                Do you want the coordinates of each Node to be
                displayed.
        """
        lead = ' ' * offset
        if nodenames and _my_node_name is not None:
            buf.write(lead + self.__class__.__name__+ ' <' + _my_node_name + '>: ')
        else:
            buf.write(lead + self.__class__.__name__+ ': ')

        if self.attr_names:
            if attrnames:
                nvlist = [(n, getattr(self,n)) for n in self.attr_names]
                attrstr = ', '.join('%s=%s' % nv for nv in nvlist)
            else:
                vlist = [getattr(self, n) for n in self.attr_names]
                attrstr = ', '.join('%s' % v for v in vlist)
            buf.write(attrstr)

        if showcoord:
            buf.write(' (at %s)' % self.coord)
        buf.write('\n')

        for (child_name, child) in self.children():
            child.show(
                buf,
                offset=offset + 2,
                attrnames=attrnames,
                nodenames=nodenames,
                showcoord=showcoord,
                _my_node_name=child_name)

class NodeVisitor(object):
    """ A base NodeVisitor class for visiting c_ast nodes.
        Subclass it and define your own visit_XXX methods, where
        XXX is the class name you want to visit with these
        methods.

        For example:

        class ConstantVisitor(NodeVisitor):
            def __init__(self):
                self.values = []

            def visit_Constant(self, node):
                self.values.append(node.value)

        Creates a list of values of all the constant nodes
        encountered below the given node. To use it:

        cv = ConstantVisitor()
        cv.visit(node)

        Notes:

        *   generic_visit() will be called for AST nodes for which
            no visit_XXX method was defined.
        *   The children of nodes for which a visit_XXX was
            defined will not be visited - if you need this, call
            generic_visit() on the node.
            You can use:
                NodeVisitor.generic_visit(self, node)
        *   Modeled after Python's own AST visiting facilities
            (the ast module of Python 3.0)
    """
    def visit(self, node):
        """ Visit a node.
        """
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):
        """ Called if no explicit visitor function exists for a
            node. Implements preorder visiting of the node.
        """
        for c_name, c in node.children():
            self.visit(c)

class Program(Node):
    __slots__ = ('ops', 'coord', '__weakref__')
    def __init__(self, ops, coord=None):
        self.ops = ops
        self.coord = coord

    def children(self):
        nodelist = []
        for i, child in enumerate(self.ops or []):
            nodelist.append(("ops[%d]" % i, child))
        return tuple(nodelist)

    attr_names = ()

class Statement(Node):
    __slots__ = ('op', 'label', 'coord', '__weakref__')
    def __init__(self, op, label, coord=None):
        self.op = op
        self.label = label
        self.coord = coord

    def children(self):
        nodelist = []
        if self.op is not None: nodelist.append(("op", self.op))
        if self.label is not None: nodelist.append(("label", self.label))
        return tuple(nodelist)

    attr_names = ()

class VarAccess(Node):
    __slots__ = ('var', 'coord', '__weakref__')
    def __init__(self, var, coord=None):
        self.var = var
        self.coord = coord

    def children(self):
        nodelist = []
        return tuple(nodelist)

    attr_names = ('var', )

class ArrayAccess(Node):
    __slots__ = ('array', 'index', 'coord', '__weakref__')
    def __init__(self, array, index, coord=None):
        self.array = array
        self.index = index
        self.coord = coord

    def children(self):
        nodelist = []
        if self.index is not None: nodelist.append(("index", self.index))
        return tuple(nodelist)

    attr_names = ('array', )

class Constant(Node):
    __slots__ = ('value', 'coord', '__weakref__')
    def __init__(self, value, coord=None):
        self.value = value
        self.coord = coord

    def children(self):
        nodelist = []
        return tuple(nodelist)

    attr_names = ('value', )

class LabelDef(Node):
    __slots__ = ('name', 'coord', '__weakref__')
    def __init__(self, name, coord=None):
        self.name = name
        self.coord = coord

    def children(self):
        nodelist = []
        return tuple(nodelist)

    attr_names = ('name', )

class LabelRef(Node):
    __slots__ = ('name', 'coord', '__weakref__')
    def __init__(self, name, coord=None):
        self.name = name
        self.coord = coord

    def children(self):
        nodelist = []
        return tuple(nodelist)

    attr_names = ('name', )

class Str(Node):
    __slots__ = ('data', 'coord', '__weakref__')
    def __init__(self, data, coord=None):
        self.data = data
        self.coord = coord

    def children(self):
        nodelist = []
        return tuple(nodelist)

    attr_names = ('data', )

class BranchOperation(Node):
    __slots__ = ('op', 'var1', 'var2', 'label', 'is_direct', 'coord', '__weakref__')
    def __init__(self, op, var1, var2, label, is_direct, coord=None):
        self.op = op
        self.var1 = var1
        self.var2 = var2
        self.label = label
        self.is_direct = is_direct
        self.coord = coord

    def children(self):
        nodelist = []
        if self.var1 is not None: nodelist.append(("var1", self.var1))
        if self.var2 is not None: nodelist.append(("var2", self.var2))
        if self.label is not None: nodelist.append(("label", self.label))
        return tuple(nodelist)

    attr_names = ('op', 'is_direct', )

class ArithmOperation(Node):
    __slots__ = ('op', 'var1', 'var2', 'var3', 'coord', '__weakref__')
    def __init__(self, op, var1, var2, var3, coord=None):
        self.op = op
        self.var1 = var1
        self.var2 = var2
        self.var3 = var3
        self.coord = coord

    def children(self):
        nodelist = []
        if self.var1 is not None: nodelist.append(("var1", self.var1))
        if self.var2 is not None: nodelist.append(("var2", self.var2))
        if self.var3 is not None: nodelist.append(("var3", self.var3))
        return tuple(nodelist)

    attr_names = ('op', )

class SetOperation(Node):
    __slots__ = ('op', 'var1', 'var2', 'coord', '__weakref__')
    def __init__(self, op, var1, var2, coord=None):
        self.op = op
        self.var1 = var1
        self.var2 = var2
        self.coord = coord

    def children(self):
        nodelist = []
        if self.var1 is not None: nodelist.append(("var1", self.var1))
        if self.var2 is not None: nodelist.append(("var2", self.var2))
        return tuple(nodelist)

    attr_names = ('op', )

class NetOperation(Node):
    __slots__ = ('op', 'var1', 'var2', 'coord', '__weakref__')
    def __init__(self, op, var1, var2, coord=None):
        self.op = op
        self.var1 = var1
        self.var2 = var2
        self.coord = coord

    def children(self):
        nodelist = []
        if self.var1 is not None: nodelist.append(("var1", self.var1))
        if self.var2 is not None: nodelist.append(("var2", self.var2))
        return tuple(nodelist)

    attr_names = ('op', )

class SleepOperation(Node):
    __slots__ = ('var1', 'coord', '__weakref__')
    def __init__(self, var1, coord=None):
        self.var1 = var1
        self.coord = coord

    def children(self):
        nodelist = []
        if self.var1 is not None: nodelist.append(("var1", self.var1))
        return tuple(nodelist)

    attr_names = ()

class Ret(Node):
    __slots__ = ('coord', '__weakref__')
    def __init__(self, coord=None):
        self.coord = coord

    def children(self):
        return ()

    attr_names = ()

class PrintOperation(Node):
    __slots__ = ('formatter', 'vect', 'coord', '__weakref__')
    def __init__(self, formatter, vect, coord=None):
        self.formatter = formatter
        self.vect = vect
        self.coord = coord

    def children(self):
        nodelist = []
        for i, child in enumerate(self.vect or []):
            nodelist.append(("vect[%d]" % i, child))
        return tuple(nodelist)

    attr_names = ('formatter', )

