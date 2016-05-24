import time
import collections
from pathlib import Path
from enum import IntEnum, unique

from ..codegen.ss_bcode import OpCode, Operation
from ..ss_exception import BlockedOperation

@unique
class InterpreterStatus(IntEnum):
    RUNNING = 0,
    SLEEPING = 1,
    BLOCKED = 2,
    STOPPED = 3,
    FINISHED = 4

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
    def __init__(self, code, communication):
        self._pc = 0
        self._code = code
        self._vars = dict()
        self._arrays = dict()
        self._stack = collections.deque()
        self._comms = communication
        self._status = InterpreterStatus.STOPPED

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

    @property
    def code(self):
        return self._code

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        self._status = value

    def save_state(self):
        return  (self._pc,
                self._vars,
                self._arrays,
                self._stack,
                self._status.value)

    def load_state(self, state):
        (self._pc, self._vars, self._arrays, self._stack, status_code) = state
        self._status = InterpreterStatus(status_code)

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

    def start(self, argv):
        self._arrays[0] = argv
        self._vars[0] = len(argv)
        self._status = InterpreterStatus.RUNNING

    def exec_next(self):
            try:
                instruction = self._code.instructions[self._pc]
                #print(instruction)
            except IndexError:
                print("Program finished without calling RET!")
                return
            try:
                self.__map[instruction.opcode](instruction.arg)
            except BlockedOperation:
                self._status = InterpreterStatus.BLOCKED
                # don't increment PC
                return
            except Exception as ex:
                print('Execution failed!')
                print('Instruction: {}'.format(str(self._code.instructions[self._pc])))
                print('Reason: ', ex.__class__.__name__, " - ", str(ex))

                print('State dump: ')
                self.print_state()

                raise
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
        if msg == None:
            # re-insert address in stack
            self._stack.append(who)

            self.waiting_from = who
            raise BlockedOperation
        self._stack.append(msg)

    def _snd(self, arg=None):
        send_what = self._stack.pop()
        send_to = self._stack.pop()
        self._comms.snd(send_to, send_what)

    def _slp(self, arg):
        self.wake_up_at = time.time() + self._stack.pop()
        self._status = InterpreterStatus.SLEEPING

    def _nop(self, arg):
        pass

    def _rot_two(self, arg):
        pass

    def _ret(self, arg=None):
        self._status = InterpreterStatus.FINISHED
