import pickle
import lzma
import time
import collections
from pathlib import Path

from .parser.ss_parser import SimpleScriptParser
from .codegen.ss_generator import SimpleScriptGenerator
from .codegen.ss_code import SimpleScriptCodeObject
from .codegen.ss_bcode import OpCode, Operation

MAGIC = 0xC0DE10CC

ARITHM_OP_TABLE =  [
        lambda x, y: x + y,
        lambda x, y: x - y,
        lambda x, y: x * y,
        lambda x, y: x / y,
        lambda x, y: x % y
        ]

COMP_OP_TABLE = [
        lambda x, y: x > y,
        lambda x, y: x >= y,
        lambda x, y: x < y,
        lambda x, y: x <= y,
        lambda x, y: x == y
        ]

class SimpleScriptInterpreter(object):
    def __init__(self, communication=None):
        self._pc = 0
        self._code = None
        self._vars = {}
        self._arrays = {}
        self._stack = collections.deque()

        self._running = False

        self._comms = communication or EchoCommunication()


        self.__map = [
                self._load_const,
                self._load_var,
                self._store_var,
                self._load_array,
                self._store_array,
                self._build_var,
                self._build_array,
                self._rot_two,
                self._arithm,
                self._compare_op,
                self._jmp_if_true,
                self._jmp,
                self._snd,
                self._rcv,
                self._slp,
                self._prn,
                self._ret,
                self._nop
                ]


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
            return

        # myprogram.ss -> .myprogram.ssc
        name = source_file.stem
        code_object = source_file.parent / ('.' + name + '.ssc')

        if code_object.is_file() and code_object.stat().st_mtime > source_ts:
            # code object file must exist and be newer than source to be up to date
            self.load_code_object(str(code_object))
        else:
            # outdated or non-existant code object
            print('Building bytecode')
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

    def print_state(self):
        print('stack:')
        print(self._stack)
        print('consts:')
        for i, var in enumerate(self._code.co_consts):
            print(i, var)
        print('vars memory dump: ')
        for index, value in self._vars.items():
            # print var_name, value
            print(self._code.co_vars[index], value)
        print('arrays memory dump: ')
        for index, value in self._arrays.items():
            # print var_name, value
            print(self._code.co_arrays[index], value)


    def run(self, argv):
        if not self._code:
            raise RuntimeError("No code loaded")

        #argv
        self._arrays[0] = argv
        self._vars[0] = len(argv)

        self._running = True
        while self._running:
            try:
                instruction = self._code.instructions[self._pc]
                #print(instruction)
            except IndexError:
                print("Program finished without calling RET!")
                return
            try:
                self.__map[instruction.opcode](instruction.arg)
            except Exception as ex:
                print('Execution failed!')
                print('Reason: ', ex.__class__.__name__, str(ex))

                print('State dump: ')
                self.print_state()
                return

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

    def _build_array(self, arg):
        self._arrays[arg] = {}
        # build only once
        # replace instruction with nop
        self._code.instructions[self._pc] = Operation(OpCode.NOP.value)

    def _store_array(self, arg):
        index = self._stack.pop()
        self._arrays[arg][index] = self._stack.pop()

    def _load_array(self, arg):
        index = self._stack.pop()
        self._stack.append(self._arrays[arg][index])

    def _prn(self, arg):
        vect = []

        for i in range(arg):
            vect.append(self._stack.pop())

        format = self._code.co_consts[self._stack.pop()]
        print(format, ', '.join(str(arg) for arg in reversed(vect)))

    def _arithm(self, arg):
        var2 = self._stack.pop()
        var1 = self._stack.pop()
        self._stack.append(ARITHM_OP_TABLE[arg](var1, var2))

    def _compare_op(self, arg):
        var2 = self._stack.pop()
        var1 = self._stack.pop()
        self._stack.append(COMP_OP_TABLE[arg](var1, var2))

    def _jmp(self, arg):
        new_index = self._code.co_labels[arg]
        self._pc = new_index - 1 # we want the next instruction to be new index

    def _jmp_if_true(self, arg):
        if self._stack.pop():
            # we want the next instruction to be new index
            self._pc = self._code.co_labels[arg] -1

    def _rcv(self, arg=None):
        who = self._stack.pop()
        msg = self._comms.recv(who)
        self._stack.append(msg)

    def _snd(self, arg=None):
        send_what = self._stack.pop()
        send_to = self._stack.pop()
        self._comms.snd(send_to, send_what)

    def _slp(self, arg):
        time.sleep(self._stack.pop())

    def _nop(self, arg):
        pass

    def _rot_two(self, arg):
        pass

    def _ret(self, arg=None):
        self._running = False

class EchoCommunication(object):
    def __init__(self):
        self._messages = {}

    def recv(self, who):
        queue = self._messages.setdefault(who, list())

        try:
            return queue.pop()
        except IndexError:
            return 0


    def snd(self, to, what):
        queue = self._messages.setdefault(to, list())
        queue.insert(0, what)

if __name__ == '__main__':
    import sys
    import cProfile

    inter = SimpleScriptInterpreter()
    inter.load_source(sys.argv[1])

    argv = sys.argv[2:] # remove interpreter name and filepath
    argv.insert(0, 0) # thread name

    # convert to integers
    argv = list((int(arg) for arg in argv))
    inter.run(argv)
    """
    cProfile.run('inter.run(argv)', 'stats')
    import pstats
    p = pstats.Stats('stats')
    p.strip_dirs().sort_stats('time').print_stats()
    """
