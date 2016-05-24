import pickle
import lzma
import time

from .source import ProgramInfo, generic_load
from .inter import SimpleScriptInterpreter, InterpreterStatus

from .utils import get_thread_uid

class Runtime(object):
    def __init__(self):
        self.threads = dict()
#        self.threads_by_program = dict()

        self._comms = EchoCommunication()

    def load_program(self, filename):
        """ Load a program description  from a .mtss file """

        info = ProgramInfo(filename)
        program_thread_info = info.parse()

        for thread_info in program_thread_info:
            self.create_thread(thread_info)

    def create_thread(self, thread_info):
        """ Create a thread from ThreadInfo"""
        code = generic_load(thread_info.source_file)

        interpreter = SimpleScriptInterpreter(code, self._comms)
        interpreter.start(thread_info.args)

        # create a ThreadContext
        context = ThreadContext(thread_info.program_id, thread_info.id, interpreter)

        thread_uid = get_thread_uid(thread_info.program_id, thread_info.id)
        self.threads[thread_uid] = context

    def pack_thread(self, thread_uid):
        """ Pack a thread with it's state and code, into a transferable blob"""
        context = self.thread[thread_uid]
        return ThreadPackage.from_context(context).pack()

    def unpack_thread(self, blob):
        """ Create a thread from a package """
        package = ThreadPackage.unpack(blob)
        interpreter = SimpleScriptInterpreter(code=package.code, comms=self._comms)

        # create a context for this thread
        context = ThreadContext(package.program_id, package.thread_id, interpreter)

        # generate a unique id and store thread
        thread_uid = get_thread_uid(package.program_id, package.thread_id)
        self.threads[thread_uid] = context


    def get_next_round(self):
        """ Generate a run list and yield threads in a round-robbin fashion """
        #FIXME: this is bad
        run_list = []
        total_blocked = 0
        for thread_id, context in self.threads.items():
            status = context.interpreter.status
            if status == InterpreterStatus.RUNNING:
                run_list.append(context)
            elif status == InterpreterStatus.SLEEPING:
                if time.time() >= context.interpreter.wake_up_at:
                    # wkae this one up
                    context.interpreter.status = InterpreterStatus.RUNNING
                    run_list.append(context)
                else:
                    continue
            elif status == InterpreterStatus.BLOCKED:
                if self._comms.can_recv(context.interpreter.waiting_from):
                    # can unblock
                    context.interpreter.status = InterpreterStatus.RUNNING
                    run_list.append(context)
                else:
                    total_blocked += 1
                    continue

        if total_blocked == len(self.threads):
            print("DEADLOCK! ABORTING!")
        return run_list

    def run(self):
        # if we get an empty list, either everyone is blocked, or they are all finished
        list = self.get_next_round()
        while list:
            for context in list:
                context = list.pop()
                try:
                    context.interpreter.exec_next()
                except Exception as ex:
                    print('Thread {} of program {} failed!'.format(
                        context.thread_id,
                        context.program_id))
                    print(str(ex))
                    return

            list = self.get_next_round()

class EchoCommunication(object):
    def __init__(self):
        self._messages = {}

    def recv(self, who):
        queue = self._messages.setdefault(who, list())

        try:
            return queue.pop()
        except IndexError:
            return None

    def snd(self, to, what):
        queue = self._messages.setdefault(to, list())
        queue.insert(0, what)

    def can_recv(self, who):
        queue = self._messages.setdefault(who, list())
        return len(queue) > 0

class ThreadContext(object):
    """ This class represents a thread context.
    Thread contexts are the containers a runtime uses to store
    everything a thread required to run.
    A ThreadContext can be packed into a portable ThreadPackage
    """
    def __init__(self, program_id, thread_id, interpreter):
        self.program_id = program_id
        self.thread_id = thread_id
        self.interpreter  = interpreter

class ThreadPackage(object):
    """ This class represents a thead package.
    Thread packages are used as containers to transfer thread state
    and code to another runtime """
    def __init__(self, program_id, thread_id, code, state):
        self.program_id = program_id
        self.thread_id = thread_id
        self.code = code
        self.state = state

    @classmethod
    def from_context(cls, context):
        """ Create a ThreadPackage from a ThreadContex """
        return cls(
                context.program_id,
                context.thread_id,
                self.interpreter.code,
                self.interpreter.save_state()
                )

    def pack(self):
        """ Pack into transfer-friendly binary blob """
        package = (self.program_id, self.thread_id, self.code, self.state)
        dump = pickle.dumps(package, pickle.HIGHEST_PROTOCOL)
        return lzma.compress(dump)

    @classmethod
    def unpack(cls, blob):
        """ Unpack a binary blob into a ThreadPackage """
        dump = lzma.decompress(blob)
        package = pickle.loads(dump)
        return cls(*package)

if __name__ == '__main__':
    import sys
    runtime = Runtime()
    runtime.load_program(sys.argv[1])
    runtime.run()
