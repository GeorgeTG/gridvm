import pickle
import lzma
import time
import itertools

from datetime import datetime
from queue import Queue, Empty

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

        self.running = True

        self._programs = dict()
        self._remote_programs = dict()
        self._own_programs = dict()

        self._request_q = Queue()
        self._request_rep = Queue()

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
                runtime_id=self.id,
                program_id=thread_info.program_id,
                thread_id=thread_info.thread_id,
                code=code,
                communication=self._comms
        )

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
        # remove the interpreter from the threads' tree
        inter = self._programs[program_id].pop(thread_id)

        # get all messages for this thread from comms
        messages = self._comms.receive_all_messages( (inter.program_id, inter.thread_id) )
        self.logger.debug('Packed {} pending messages'.format(len(messages)))

        return ThreadPackage.from_inter(inter, messages).pack()

    def unpack_thread(self, blob):
        """ Create a thread from a package """
        #self.total_threads += 1
        package = ThreadPackage.unpack(blob)

        interpreter = SimpleScriptInterpreter(
                thread_id=package.thread_id,
                program_id=package.program_id,
                runtime_id=package.runtime_id,
                code=package.code,
                communication=self._comms
        )

        self.logger.debug('Restored {} pending messages'.format(len(package.pending_msgs)))
        # restore pending messages
        self._comms.restore_messages( (package.program_id, package.thread_id), package.pending_msgs)

        # load stack, memory etc
        interpreter.load_state(package.state)


        # add thread to programs
        program_node = self._programs.setdefault(package.program_id, dict())
        program_node[package.thread_id] = interpreter


    def shutdown(self):
        self.running = False
        self._comms.shutdown()

        # Send all foreign threads away
        for program_id in self._programs:
            if program_id in self._own_programs:
                continue

            for thread_id in self._programs[program_id]:
                self.logger.info('Getting rid of {}:{}..'.format(program_id, thread_id))
                self.request_migration(program_id, thread_id, None)

    def on_thread_fail(self, failed_inter):
        """ Called when a Thread fails """
        self.update_status(failed_inter.thread_uid, failed_inter.runtime_id, InterpreterStatus.CRASHED)

        del self._programs[failed_inter.program_id]

        if failed_inter.program_id in self._own_programs:
            del self._own_programs[failed_inter.program_id]

    def _get_next_round(self):
        """ Generate a run list and yield threads in a round-robin fashion """
        self.check_for_requests()

        run_list = [ ]
        while not run_list and self.running:
            for inter in itertools.chain(*( child.values() for child in self._programs.values())):
                status = inter.status
                if status == InterpreterStatus.RUNNING:
                    run_list.append(inter)
                elif (status == InterpreterStatus.SLEEPING and time.time() >= inter.wake_up_at):
                    self.update_status(inter.thread_uid, inter.runtime_id, InterpreterStatus.RUNNING)
                    run_list.append(inter)

                elif (status == InterpreterStatus.BLOCKED and
                        self._comms.can_receive_message(inter.waiting_from) ):
                    self.update_status(inter.thread_uid, inter.runtime_id, InterpreterStatus.RUNNING)
                    run_list.append(inter)

            if not run_list:
                #self.logger.debug('Sleeping for 100ms ...')
                time.sleep(1)
                self.check_for_requests()

        return run_list

    def run(self):
        # if we get an empty list, either everyone is blocked, or they are all finished
        list = self._get_next_round()
        while list:
            for inter in list:
                inter = list.pop()

                try:
                    #print('running', inter.program_id, inter.thread_id)
                    inter.exec_next()
                except StatusChange as sc:
                    # interpreter changed the status of this thread
                    """
                    self._comms.send_status_request(
                            sc.runtime_id,
                            (sc.program_id, sc.thread_id),
                            sc.status)
                    """
                    self.update_status(inter.thread_uid, sc.runtime_id, sc.status)

                except Exception as ex:
                    self.logger.error('Thread failed')
                    self.logger.error(str(ex))

                    self.on_thread_fail(inter)

                    self.shutdown()
                    raise

            list = self._get_next_round()

        self._comms.nethandler.cleanup()

    def check_for_requests(self):
        # Check for status requests
        for update in self._comms.get_status_requests():
            ( (program_id, thread_id), status ) = update
            self._own_programs[program_id][thread_id] = status

        # Check for print requests
        for thread_uid, msg in self._comms.get_print_requests():
            self.logger.info('[{}:{}]: {}'.format(*thread_uid, msg))

        # Check for migrations sent over the network
        for thread_blob in self._comms.get_migrated_threads():
            self.unpack_thread(thread_blob)

        # Check for requests from shell
        try:
            while True:
                req, arg = self._request_q.get(block=False)
                if req == LocalRequest.MIGRATE:
                    self.request_migration(*arg)
                elif req == LocalRequest.LIST_PROGRAMS:
                    self._request_rep.put( self.get_thread_names() )
        except Empty:
            pass

    def get_local_result(self):
        """ Called from  shell to get a command result, returns (item, message) """
        return self._request_rep.get()

    def get_thread_names(self):
        """ Returns a tuple of (programs_list, threads_of_nth_program """
        programs = list()
        program_threads = list()
        index = 0
        for program, threads in self._programs.items():
            programs.append(program)
            program_threads.append( list(threads.keys()) )

        return (programs, program_threads)

    def sanity_check(self, program_id):
        total_threads = 0
        finished_threads = 0
        blocked_threads = 0
        for status in self._own_programs[program_id].values():
            if status == InterpreterStatus.FINISHED:
                finished_threads += 1
            elif status == InterpreterStatus.BLOCKED: # MAYBE AND CANNOT RECV??
                blocked_threads += 1

            total_threads += 1

        if finished_threads == total_threads:
            self.logger.info('Program {} finished.'.format(program_id))
            del self._programs[program_id]

            if program_id in self._own_programs:
                del self._own_programs[program_id]

        elif blocked_threads == total_threads:
            self.logger.error('Program {} is in a DEADLOCK'.format(program_id))

    def update_status(self, thread_uid, runtime_id, new_status):
        """ Update status, if this is not our thread notify
        the responsible runtime for its thread's status """

        #self.logger.debug('State of {}:{} is now: "{}"'.format(
        #    *thread_uid, InterpreterStatus(new_status).name
        #))

        program_id, thread_id = thread_uid
        if program_id in self._own_programs:
            self._own_programs[program_id][thread_id] = new_status
        else:
            self.logger.debug('Notify runtime: {}'.format(runtime_id))
            self._comms.send_status_request(
                runtime_id,
                thread_uid,
                new_status
            )

        # update inter status
        self._programs[program_id][thread_id].status = new_status

        if new_status == InterpreterStatus.FINISHED:
            # delete finished thread
            self.logger.debug("{}.{} finished".format(program_id, thread_id))
            del self._programs[program_id][thread_id]

            if program_id in self._own_programs:
                del self._own_programs[program_id][thread_id]

        if program_id in self._own_programs:
            self.sanity_check(program_id)

    def add_local_request(self, type, arg=None):
        """ Called from the shell to serve a request """
        self._request_q.put( (type, arg) )

    def request_migration(self, program_id, thread_id, runtime_id):
        """ Called to request a migration, duh """
        self._request_q.put( (LocalRequest.MIGRATE, (program_id, thread_id, runtime_id)) )

    def migrate_thread(self, program_id, thread_id, runtime_id):
        """ Start the migration process for thread_uid to runtime_id """
        self.logger.info('Migrating ({}, {}) to {}'.format(program_id, thread_id, runtime_id))

        thread_package = self.pack_thread(program_id, thread_id)
        success = self._comms.migrate_thread(
            (program_id, thread_id),
            thread_package,
            runtime_id
        )

        if not success:
            self.unpack_thread(thread_package)
            self.logger.warning('Migration failed')
        else:
            self.logger.info('Migration completed!')


class ThreadPackage(object):
    """ This class represents a thead package.
    Thread packages are used as containers to transfer thread state
    and code to another runtime """
    def __init__(self, runtime_id, program_id, thread_id, code, state, messages=[]):
        self.program_id = program_id
        self.thread_id = thread_id
        self.runtime_id = runtime_id
        self.code = code
        self.state = state
        self.pending_msgs = messages

    @classmethod
    def from_inter(cls, inter, messages):
        """ Create a ThreadPackage from a ThreadContex """
        return cls(
                inter.runtime_id,
                inter.program_id,
                inter.thread_id,
                inter.code,
                inter.save_state(),
                messages
                )

    def pack(self):
        """ Pack into network-friendly transferable binary blob """
        package = (self.runtime_id, self.program_id,
                self.thread_id, self.code, self.state, self.pending_msgs)
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
    from threading import Thread

    if len(sys.argv) == 1:
        print('No program has been given..')
        sys.exit(1)

    runtime = Runtime('eno1')
    for i in range(len(sys.argv) - 1):
        runtime.load_program(sys.argv[i+1])

    # Create thread for runtime
    runtime_thread = Thread(target=runtime.run)
    runtime_thread.start()

    try:
            program_id = input()
            thread_id = int(input())
            runtime_id = input()

            runtime.request_migration( program_id, thread_id, runtime_id )
    except KeyboardInterrupt:
        runtime.shutdown()


from enum import IntEnum, unique
@unique
class LocalRequest(IntEnum):
    LIST_RUNTIMES = 0
    LIST_PROGRAMS = 1
    MIGRATE = 2
    AUTO_BALANCE = 3
    SHUTDOWN = 4

