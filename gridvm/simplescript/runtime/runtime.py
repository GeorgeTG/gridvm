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
from ..ss_exception import StatusChange

class Runtime(object):
    def __init__(self, interface, bind_addres=None, mcast_address=None):
        # Generate unique id for each runtime (even in same pc)
        self.id = fast_hash( datetime.now().isoformat(), length=4)
        self.logger = get_logger('{}:Runtime'.format(self.id))

        self._programs = dict()
        self._remote_programs = dict()
        self._own_programs = dict()

        #self._comms = EchoCommunication(interface)
        self._comms = NetworkCommunication(self.id, interface)

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

        # add to programs
        program_node = self._programs.setdefault(thread_info.program_id, dict())
        program_node[thread_info.thread_id] = interpreter

        # add to own programs(status only)
        program_node = self._own_programs.setdefault(thread_info.program_id, dict())
        program_node[thread_info.thread_id] = interpreter.status

        # let comms know we have a new thread
        self._comms.update_thread_location(
                (thread_info.program_id, thread_info.thread_id),
                self.id )

    def pack_thread(self, program_id, thread_id):
        """ Pack a thread with it's state and code, into a transferable blob"""
        inter = self._programs[program_id].pop(thread_id)
        return ThreadPackage.from_inter(inter).pack()

    def unpack_thread(self, blob):
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

        # add thread to programs
        program_node = self._own_programs.setdefault(package.program_id, dict())
        program_node[pacakge.thread_id] = interpreter

        # let comms know we have a new thread
        self._comms.update_thread_location(
                (package.program_id, package.thread_id),
                package.runtime_id )

    def shutdown(self):
        self._comms.shutdown()

    def on_thread_fail(self, failed_inter):
        """ Called when a Thread fails """
        failed_inter.status = InterpreterStatus.CRASHED
        self.update_status(failed_inter)

        del self._programs[failed_inter.program_id]

        if failed_inter.program_id in self._own_programs:
            del self._own_programsp[failed_inter.program_id]

    def _get_next_round(self):
        """ Generate a run list and yield threads in a round-robin fashion """

        run_list = [ ]
        while not run_list:
            for inter in itertools.chain(*( child.values() for child in self._programs.values())):
                status = inter.status
                if status == InterpreterStatus.RUNNING:
                    run_list.append(inter)
                elif (status == InterpreterStatus.SLEEPING and time.time() >= inter.wake_up_at):
                    inter.status = InterpreterStatus.RUNNING
                    self.update_status(inter)
                    run_list.append(inter)

                elif (status == InterpreterStatus.BLOCKED and
                        self._comms.can_receive_message(inter.waiting_from) ):
                    inter.status = InterpreterStatus.RUNNING
                    self.update_status(inter)
                    run_list.append(inter)

            if not run_list:
                time.sleep(0.1)
        return run_list


    def run(self):
        changes = self._comms.get_status_requests()
        self.update_remote_threads(changes)


        # if we get an empty list, either everyone is blocked, or they are all finished
        list = self._get_next_round()
        while list:
            for inter in list:
                inter = list.pop()

                try:
                    print('running', inter.program_id, inter.thread_id)
                    inter.exec_next()
                except StatusChange as sc:
                    # interpreter changed the status of this thread
                    self._comms.send_status_request(
                            sc.runtime_id,
                            (sc.program_id, sc.thread_id),
                            sc.status)

                    self.update_status(inter)

                except Exception as ex:
                    self.logger.error('Thread failed')
                    self.logger.error(str(ex))

                    self.on_thread_fail(inter)

                    self.shutdown()
                    raise

            list = self._get_next_round()



    def sanity_check(self, program_id):
        total_threads = 0
        finished_threads = 0
        blocked_threads = 0
        for status in self._own_programs[program_id].values():
            if status == InterpreterStatus.FINISHED:
                finished_threads += 1
            elif status == InterpreterStatus.BLOCKED:
                blocked_threads += 1

            total_threads += 1

        if finished_threads == total_threads:
            self.logger.info('Program {} finished.'.format(program_id))
            del self._programs[program_id]

            if program_id in self._own_programs:
                del self._own_programs[program_id]

        elif blocked_threads == total_threads:
            self.logger.error('Program {} is in a DEADLOCK'.format(program_id))

    def update_status(self, inter):
        """ Update status, if this is not our thread notify
        the responsible runtime for its thread's status """
        if inter.program_id in self._own_programs:
            self._own_programs[inter.program_id][inter.thread_id] = inter.status
            if inter.status == InterpreterStatus.BLOCKED:
                self.sanity_check(inter.program_id)
            elif inter.status == InterpreterStatus.FINISHED:
                # delete finished thread
                self.logger.debug("{}.{} finished".format(inter.program_id, inter.thread_id))
                del self._programs[inter.program_id][inter.thread_id]
                if inter.program_id in self._own_programs:
                    del self._own_programs[inter.program_id][inter.thread_id]
                self.sanity_check(inter.program_id)

        # update inter status
        #self._programs[inter.program_id][inter.thread_id].status = inter.status

    def add_thread(self, inter):
        thread_list = self._programs.setdefault(inter.program_id, dict())
        thread_list[inter.thread_id] = inter

        if inter.runtime_id == self.id:
            program_node = self._own_programs.setdefault(inter.program_id, dict())
            program_node[inter.thread_id] = inter.status

    def update_remote_threads(self, statuses):
        """ Check for status changes for OUR threads from remote runtimes """
        for update in statuses:
            ( (program_id, thread_id), status ) = update
            self._own_programs[program_id][thread_id] = status
            if status == InterpreterStatus.BLOCKED:
                self.check_for_deadlocks(program_id)
            elif status == InterpreterStatus.FINISHED:
                self.check_if_finished(program_id)


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
