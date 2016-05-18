
from string import Template

class ByteCodeSpecGenerator:
    def __init__(self, cfg_filename='bcode.decl'):
        """ Initialize the code generator from a configuration
            file.
        """
        self.cfg_filename = cfg_filename
        self.operations_cfg = [OperationCfg(name, contents)
            for (name, contents) in self.parse_cfgfile(cfg_filename)]

    def generate(self, file=None):
        """ Generates the code into file, an open file buffer.
        """
        src = Template(_PROLOGUE_COMMENT).substitute(
            cfg_filename=self.cfg_filename)

        opcodes = ""
        src += _PROLOGUE_CODE
        for i, op_cfg in enumerate(self.operations_cfg):
            src += op_cfg.generate_source(i) + '\n\n'
            opcodes += "    {} = {}\n".format(op_cfg.name.upper().ljust(5), i)

        src += _TEMPLATE_ENUM + opcodes

        file.write(src)

    def parse_cfgfile(self, filename):
        """ Parse the configuration file and yield pairs of
            (name, contents) for each node.
        """
        with open(filename, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                colon_i = line.find(':')
                lbracket_i = line.find('[')
                rbracket_i = line.find(']')
                if colon_i < 1 or lbracket_i <= colon_i or rbracket_i <= lbracket_i:
                    raise RuntimeError("Invalid line in %s:\n%s\n" % (filename, line))

                name = line[:colon_i]
                val = line[lbracket_i + 1:rbracket_i]
                vallist = [v.strip() for v in val.split(',')] if val else []
                yield name, vallist


class ParameterCfg(object):
    """ Parameter for an operation"""
    def __init__(self, name, type):
        self.name = name
        self.type = type

class OperationCfg(object):
    """ Operation configuration.

    """
    def __init__(self, name, contents):
        self.name = name
        self.params = []

        for entry in contents:
            clean_entry = entry.rstrip('*#$')

            if entry.endswith('**'):
                self.params.append(ParameterCfg(clean_entry, ParameterType.ARRAY))
            elif entry.endswith('*'):
                self.params.append(ParameterCfg(clean_entry, ParameterType.VAR))
            elif entry.endswith('#'):
                self.params.append(ParameterCfg(clean_entry, ParameterType.STACK))
            elif entry.endswith('$'):
                self.params.append(ParameterCfg(clean_entry, ParameterType.DATA))
            else:
                self.params.append(ParameterCfg(clean_entry, ParameterType.CONST))

    def generate_source(self, opcode):
        src = self._gen_init(opcode)
        return src

    def _gen_init(self, opcode):
        src = "class Op%s(Operation):\n" % (self.name[0].upper() + self.name[1:])
        body_src = ""
        slots = ""
        args = []

        for param in self.params:
            args.append(param.name)
            body_src += "        self.{0} = Parameter({0}, ParameterType.{1})\n".format(
                    param.name, param.type.name)
            slots += "'{}', ".format(param.name)

        slots += " '__weakref__',"

        src += "    __opcode__ = {}\n".format(opcode)
        src += "    __slots__ = ({})\n".format(slots)

        params = tuple(args)
        args = ', '.join( (arg for arg in args) )
        src += "\n    def __init__(%s):\n" % ('self, ' + args)
        if body_src:
            src += body_src
            src += "\n    params = %s" % str(params)
        else:
            src += "        pass\n"

        return src



_PROLOGUE_COMMENT = \
r'''#-----------------------------------------------------------------
# ** ATTENTION **
# This code was automatically generated from the file:
# $cfg_filename
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

'''

_PROLOGUE_CODE = \
r'''
class Parameter(object):
    """ Paramter for an operation"""
    def __init__(self, value, type):
        self.value = value
        self.type = type

class Operation(object):
    __slots__ = ()
    def show(self):
        opcode = OpCode(self.__opcode__)
        repr = '[{}]{}:\n'.format(opcode.value, opcode.name)
        for name, type, value in self.iter_params():
            repr += '    {}: {}({})\n'.format(name, type, value)
        print(repr)

    def iter_params(self):
        if self.params:
            for attr in self.params:
                param = getattr(self, attr)
                yield (attr, param.type.name, param.value)

'''

_TEMPLATE_ENUM = \
r'''
from .ss_def import ParameterType

from enum import IntEnum, unique

@unique
class OpCode(IntEnum):
'''

import sys
if __name__ == "__main__":
    from ss_def import ParameterType

    gen = ByteCodeSpecGenerator()
    with open('ss_bcode.py', 'w') as f:
        gen.generate(f)
else:
    from .ss_def import ParameterType
