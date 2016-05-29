import time
import collections
from pathlib import Path
from enum import IntEnum, unique

from ..codegen.ss_bcode import OpCode, Operation
from ..ss_exception import StatusChange

@unique
class InterpreterStatus(IntEnum):
    RUNNING = 0,
    SLEEPING = 1,
    BLOCKED = 2,
    STOPPED = 3,
    FINISHED = 4,
    CRASHED = 5

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
    def __init__(self, runtime_id, program_id, thread_id, code, communication):
        self._pc = 0
        self.code = code
        self._vars = dict()
        self._arrays = dict()
        self._stack = collections.deque()
        self._comms = communication
        self._status = InterpreterStatus.STOPPED
        self.program_id = program_id
        self.thread_id = thread_id
        self.runtime_id = runtime_id
        self.thread_uid = (program_id, thread_id)
        self.wake_up_at = 0.0

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
        for i, var in enumerate(self.code.co_consts):
            print(i, var)
        print('vars memory dump: ')
        for index, value in self._vars.items():
            # print var_name, value
            print(self.code.co_vars[index], value)
        print('arrays memory dump: ')
        for index, value in self._arrays.items():
            # print var_name, value
            print(self.code.co_arrays[index], value)

    def start(self, argv):
        self._arrays[0] = argv
        self._vars[0] = len(argv)
        self._status = InterpreterStatus.RUNNING

    def exec_next(self):
            try:
                instruction = self.code.instructions[self._pc]
                #print(instruction)
            except IndexError:
                raise RuntimeError("Program finished without calling RET!")

            try:
                self.__map[instruction.opcode](instruction.arg)
            except StatusChange:
                if self._status != InterpreterStatus.BLOCKED:
                    self._pc += 1
                raise # propagate
            except Exception as ex:
                error_msg =  'Execution failed!\n'
                error_msg += 'Instruction: {}\n'.format(str(self.code.instructions[self._pc]))
                error_msg += 'Reason: {} - {}\n'.format(ex.__class__.__name__, str(ex))

                print('State dump: ')
                self.print_state()

                raise RuntimeError(error_msg)

            self._pc += 1

    ##### INSTRUCTIONS #####
    def _load_const(self, arg):
        self._stack.append(self.code.co_consts[arg])

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
        self.code.instructions[self._pc] = Operation(OpCode.NOP.value)

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

        format = self.code.co_consts[self._stack.pop()]
        to_print = format +  ', '.join(str(arg) for arg in reversed(vect))

        self._comms.send_print_request(
            self.runtime_id,
            (self.program_id, self.thread_id),
            to_print
        )

    def _arithm(self, arg):
        var2 = self._stack.pop()
        var1 = self._stack.pop()
        self._stack.append(ARITHM_OP_TABLE[arg](var1, var2))

    def _compare_op(self, arg):
        var2 = self._stack.pop()
        var1 = self._stack.pop()
        self._stack.append(COMP_OP_TABLE[arg](var1, var2))

    def _jmp(self, arg):
        new_index = self.code.co_labels[arg]
        self._pc = new_index - 1 # we want the next instruction to be new index

    def _jmp_if_true(self, arg):
        if self._stack.pop():
            # we want the next instruction to be new index
            self._pc = self.code.co_labels[arg] -1

    def _rcv(self, arg=None):
        who = self._stack.pop()
        msg = self._comms.receive_message( (self.program_id, who) )
        if msg == None:
            # re-insert address in stack
            self._stack.append(who)

            # save who we are waiting from and propagate
            self.waiting_from = (self.program_id, who)
            self._status = InterpreterStatus.BLOCKED
            raise StatusChange(self.runtime_id, self.program_id, self.thread_id, self._status)
        self._stack.append(msg)

    def _snd(self, arg=None):
        send_what = self._stack.pop()
        send_to = self._stack.pop()
        self._comms.send_message( (self.program_id, send_to) , send_what)

    def _slp(self, arg):
        self.wake_up_at = time.time() + self._stack.pop()
        self._status = InterpreterStatus.SLEEPING
        raise StatusChange(self.runtime_id, self.program_id, self.thread_id, self._status)

    def _nop(self, arg):
        pass

    def _rot_two(self, arg):
        pass

    def _ret(self, arg=None):
        self._status = InterpreterStatus.FINISHED
        raise StatusChange(self.runtime_id, self.program_id, self.thread_id, self._status)
