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

        self._running = False

    def _just_load(self, source_file):
        with source_file.open('r') as f:
            source = f.read()

        # parse source into tree
        parser = SimpleScriptParser()
        tree = parser.parse(source)

        # generate bytecode
        gen = SimpleScriptGenerator()
        code = gen.generate(tree)

        self._code = code

    def load_source(self, filename):
        source_file = Path(filename).resolve()
        stat = source_file.stat()
        source_ts = stat.st_mtime

        # if the file is small enough skip filesystem stuff
        if stat.st_size < 500:
            self._just_load(source_file)

        # myprogram.ss -> .myprogram.ssc
        name = source_file.stem
        code_object = source_file.parent / ('.' + name + '.ssc')

        if code_object.is_file() and code_object.stat().st_mtime > source_ts:
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

        self._running = True
        while self._running:
            instruction = self._code.instructions[self._pc]
            print(instruction)
            function = '_' + instruction.opcode.name.lower()
            getattr(self, function)(instruction.arg)

            self._pc += 1


    ##### INSTRUCTIONS #####
    def _load_const(self, arg):
        self._stack.append(self._code.co_consts[arg])

    def _load_var(self, arg):
        self._stack.append(self._vars[arg])

    def _build_var(self, arg):
        pass

    def _store_var(self, arg):
        self._vars[arg] = self._stack.pop()

    def _prn(self, arg):
        print(self._stack)
        format = self._code.co_consts[self._stack.pop()]
        vect = []

        for i in range(arg):
            vect.append(self._stack.pop())

        print(format, vect)

    def _ret(self, arg=None):
        self._running = False

if __name__ == '__main__':
    import sys
    inter = SimpleScriptInterpreter()
    inter.load_source(sys.argv[1])

    inter.run([])

    print(inter._vars)
