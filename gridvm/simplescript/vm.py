import pickle
import lzma
from pathlib import Path

from .parser.ss_parser import SimpleScriptParser
from .codegen.ss_generator import SimpleScriptGenerator
from .codegen.ss_code import SimpleScriptCodeObject
from .codegen.ss_bcode import OpCode

MAGIC = 0xC0DE10CC

class SimpleScriptInterpreter(object):
    def __init__(self):
        self._pc = 0
        self._code = None
        self._vars = {}
        self._arrays = {}
        self._stack = []

    def load_source(self, filename):
        source_file = Path(filename).resolve()
        source_ts = source_file.stat().st_mtime

        # myprogram.ss -> .myprogram.ssc
        name = source_file.stem
        code_object = source_file.parent / ('.' + name + '.ssc')
        code_object_ts = code_object.stat().st_mtime

        if code_object.is_file() and code_object_ts > source_ts:
            # code object file must exist and be newer than source to be up to date
            self.load_code_object(str(code_object))
        else:
            # open the original source code
            with source_file.open('r') as f:
                source = f.read()

            # parse source into tree
            parser = SimpleScriptParser()
            tree = parser.parse(source)

            # generate bytecode
            gen = SimpleScriptGenerator()
            code = gen.generate(tree)

            # save for future use
            code.to_file(str(code_object), compress=True)
            self._code = code

    def load_code_object(self, filename):
        self._code = SimpleScriptCodeObject.from_file(filename, decompress=True)


    def dump_state(self):
        state = (self._pc,
                self._vars,
                self._arrays,
                self._stack)
        return lzma.compress(
            MAGIC.to_bytes(4, byteorder='big') +
            pickle.dumps(state, pickle.HIGHEST_PROTOCOL)
        )

    def load_state(self, state):
        buff = lzma.decompress(state)
        if int.from_bytes(buff[:4], byteorder='big') != MAGIC:
            raise ValueError('Invalid state')
        state = pickle.loads(buff[4:])
        (self._pc, self._vars, self._arrays, self._stack) = state

    def run(self, argv=[]):
        if not self._code:
            raise RuntimeError("No code loaded")

        # TODO: make this run some code :)


if __name__ == '__main__':
    import sys
    inter = SimpleScriptInterpreter()
    inter.load_source(sys.argv[1])
    inter._pc  = 1337
    inter._vars['asdas']= 16
    inter._arrays['safasd']= [1, 3, 3, 7]
    inter._stack.append(1337)
    inter._stack.append(1338)
    state = inter.dump_state()

    inter2 = SimpleScriptInterpreter()
    inter2._code = inter._code
    inter2.load_state(state)
    print(inter2._pc)
    print(inter2._vars)
    print(inter2._arrays)
    print(inter2._stack)
