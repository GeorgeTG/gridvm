import pickle
import lzma
import time

from datetime import datetime

from gridvm.logger import get_logger
from .communication import NetworkCommunication, EchoCommunication
from .inter import SimpleScriptInterpreter, InterpreterStatus
from .source import ProgramInfo, generic_load
from .utils import fast_hash
from .scheduler import RuntimeScheduler
from ..ss_exception import StatusChange

class Runtime(object):
    def __init__(self, interface, bind_addres=None, mcast_address=None):
        # Generate unique id for each runtime (even in same pc)
        self.id = fast_hash( datetime.now().isoformat(), length=4)
        self.logger = get_logger('{}:Runtime'.format(self.id))

        self._comms = EchoCommunication(interface)
        #self._comms = NetworkCommunication(self.id, interface)
        self._scheduler = RuntimeScheduler(self.id, self._comms)

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


        # initialise the interpreter with argv
        interpreter.start(thread_info.args)

        self._scheduler.add_thread(interpreter)

    def pack_thread(self, program_id, thread_id):
        """ Pack a thread with it's state and code, into a transferable blob"""
        inter = self._scheduler.pop_thread(program_id, thread_id)
        return ThreadPackage.from_inter(inter).pack()

    def unpack_thread(self, blob):
        self.total_threads += 1
        """ Create a thread from a package """
        package = ThreadPackage.unpack(blob)

        interpreter = SimpleScriptInterpreter(
                thread_id = package.thread_id,
                program_id = package.program_id,
                runtime_id = package.runtime_id,
                code=package.code,
                communication=self._comms)

        # load stack, memory etc
        interpreter.load_state(package.state)
        self._scheduler.add_thread(interpreter)

        # Set thread location to local runtime
        self._comms.update_thread_location( (program_id, thread_id), runtime_id )

    def shutdown(self):
        self._comms.shutdown()

    def on_thread_fail(self, failed_inter):
        del self._scheduler[failed_inter.program_id]

    def run(self):
        changes = self._comms.get_status_requests()
        self._scheduler.update_remote_threads(changes)

        for instruction in self._scheduler.get_next():
            try:
                instruction()
            except StatusChange as sc:
                self._comms.send_status_request(
                        sc.runtime_id,
                        (sc.program_id, sc.thread_id),
                        sc.status)

            except Exception as ex:
                self.logger.error('Thread {} of program {} failed!'.format(
                    inter.thread_id,
                    inter.program_id))
                self.logger.error(str(ex))

                # thread failed
                self.on_thread_fail(inter)

                self.shutdown()


class ThreadPackage(object):
    """ This class represents a thead package.
    Thread packages are used as containers to transfer thread state
    and code to another runtime """
    def __init__(self, runtime_id, program_id, thread_id, code, state):
        self.program_id = program_id
        self.thread_id = thread_id
        self.runtime_id = runtime_id
        self.code = code
        self.state = state

    @classmethod
    def from_inter(cls, inter):
        """ Create a ThreadPackage from a ThreadContex """
        return cls(
                inter.runtime_id,
                inter.program_id,
                inter.thread_id,
                inter.code,
                inter.save_state()
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
