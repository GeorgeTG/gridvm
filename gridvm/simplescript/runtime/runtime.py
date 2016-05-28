import pickle
import lzma
import time
import itertools

from datetime import datetime

from gridvm.logger import get_logger
from .communication import NetworkCommunication, EchoCommunication
from .inter import SimpleScriptInterpreter, InterpreterStatus
from .source import ProgramInfo, generic_load
from .utils import fast_hash


def chain(*iterables):
    # chain('ABC', 'DEF') --> A B C D E F
    for it in iterables:
        for element in it:
            yield element

class Runtime(object):
    def __init__(self, interface, bind_addres=None, mcast_address=None):
        # Generate unique id for each runtime (even in same pc)
        self.id = fast_hash( datetime.now().isoformat(), length=4)
        self.logger = get_logger('{}:Runtime'.format(self.id))

        self.threads = dict()
#        self.programs = dict()
#        self.blocked_programs = dict()

        self._comms = EchoCommunication(interface)

    def load_program(self, filename):
        """ Load a program description  from a .mtss file """

        self.logger.debug('Loading program "{}"...'.format(filename))
        info = ProgramInfo(filename)
        program_thread_info = info.parse()

        for thread_info in program_thread_info:
            self.logger.debug('Creating thread [{}]:{}...'.format(
                thread_info.program_id,
                thread_info.thread_id
            ))
            self.create_thread(thread_info)

        self.logger.info('Program loaded successfully!')

    def create_thread(self, thread_info):
        """ Create a thread from ThreadInfo"""
        code = generic_load(thread_info.source_file)

        interpreter = SimpleScriptInterpreter(
                runtime_id = self.id,
                program_id = thread_info.program_id,
                thread_id = thread_info.thread_id,
                code = code,
                communication = self._comms)

        # initiallise the interpreter with argv
        interpreter.start(thread_info.args)

        thread_list = self.threads.setdefault(interpreter.program_id, list())
        thread_list.append(interpreter)

    def pack_thread(self, program_id, thread_id):
        """ Pack a thread with it's state and code, into a transferable blob"""
        inter = self.thread[thread_uid]
        return ThreadPackage.from_inter(inter).pack()

    def unpack_thread(self, blob):
        """ Create a thread from a package """
        package = ThreadPackage.unpack(blob)

        interpreter = SimpleScriptInterpreter(
                thread_id = package.thread_id,
                program_id = package.program_id,
                runtime_id = package.runtime_id,
                code=package.code,
                comms=self._comms)


        # generate a unique id and store thread
        thread_uid = (package.program_id, package.thread_id)

        self.threads[thread_uid] = interpreter


    def get_next_round(self):
        """ Generate a run list and yield threads in a round-robin fashion """
        #FIXME: this is less bad :)

        run_list = [ ]
        while not run_list:
#            for inter in itertools.chain(*self.threads.values()):
#                print(inter.program_id, inter.thread_id, inter.status.name)
            # Keep track of threads status
            total_blocked = 0
            total_sleeping = 0
            total_finished = 0

            for inter in itertools.chain(*self.threads.values()):
                status = inter.status

                if status == InterpreterStatus.RUNNING:
                    run_list.append(inter)

                elif (status == InterpreterStatus.SLEEPING and
                        time.time() >= inter.wake_up_at):
                    # wake this one up
                    inter.status = InterpreterStatus.RUNNING
                    run_list.append(inter)

                elif (status == InterpreterStatus.BLOCKED and
                        self._comms.can_recv(inter.waiting_from)):
                    # can unblock
                    inter.status = InterpreterStatus.RUNNING
                    run_list.append(inter)

                elif status == InterpreterStatus.BLOCKED:
                    total_blocked += 1

                elif status == InterpreterStatus.SLEEPING:
                    total_sleeping += 1

                elif status == InterpreterStatus.FINISHED:
                    total_finished += 1

            total_threads = sum( (len(values) for values in self.threads.values()))
            if total_blocked == total_threads - total_finished:
                self.logger.error("DEADLOCK! ABORTING!")
                self.shutdown()
                break

            if total_sleeping == total_threads - total_finished:
                self.logger.debug("All threads are sleeping...")
                time.sleep(0.1)

        return run_list

    def run(self):
        # if we get an empty list, either everyone is blocked, or they are all finished
        list = self.get_next_round()
        while list:
            for inter in list:
                inter = list.pop()
                try:
                    inter.exec_next()
                except Exception as ex:
                    self.logger.error('Thread {} of program {} failed!'.format(
                        inter.thread_id,
                        inter.program_id))
                    self.logger.error(str(ex))

                    # thread failed
                    self.on_thread_fail(inter)
                    break

                    self.shutdown()

            list = self.get_next_round()

    def shutdown(self):
        self._comms.shutdown()

    def on_thread_fail(self, failed_inter):
        del self.threads[failed_inter.program_id]


class ThreadPackage(object):
    """ This class represents a thead package.
    Thread packages are used as containers to transfer thread state
    and code to another runtime """
    def __init__(self, runtime_id, program_id, thread_id, code, state):
        self.program_id = program_id
        self.thread_id = thread_id
        self.runtime_id
        self.code = code
        self.state = state

    @classmethod
    def from_inter(cls, inter):
        """ Create a ThreadPackage from a ThreadContex """
        return cls(
                inter.runtime_id,
                inter.program_id,
                inter.thread_id,
                self.interpreter.code,
                self.interpreter.save_state()
                )

    def pack(self):
        """ Pack into network-friendly transferable binary blob """
        package = (self.runtime_id, self.program_id, self.thread_id, self.code, self.state)
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
    runtime = Runtime('eno1')

    if len(sys.argv) == 1:
        print('No program has been given..')

    else:
        for i in range(len(sys.argv) - 1):
            runtime.load_program(sys.argv[i+1])
        runtime.run()
