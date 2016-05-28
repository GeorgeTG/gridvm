import itertools
from .inter import SimpleScriptInterpreter, InterpreterStatus



class RuntimeScheduler():

    def __init__(self, runtime_id, comms):
        self.total_threads = 0

        self._programs = dict()
        self._remote_programs = dict()

        self._own_programs = dict()
        self._my_runtime_id = runtime_id

        self._comms = comms

    def check_for_deadlocks(self, program_id):
        for status in self._own_programs[program_id].values():
            if status != InterpreterStatus.BLOCKED:
                return
        print('omg deadlock')

    def check_if_finished(self, program_id):
        for status in self._own_programs[program_id].values():
            if status != InterpreterStatus.FINISHED:
                return

        del self._own_programs[program_id]

        if program_id in self._programs:
            del self._programs[program_id]


    def update_status(self, inter):
        """ Update status, if this is not our thread notify
        the responsible runtime for its thread's status """
        if program_id in self._own_programs:
            self._own_programs[inter.program_id][inter.thread_id] = status
            if status == InterpreterStatus.BLOCKED:
                self.check_for_deadlocks(inter.program_id)

        # update inter status
        self._programs[inter.program_id][inter.thread_id].status = status


    def _get_next_round(self):
        """ Generate a run list and yield threads in a round-robin fashion """

        run_list = [ ]
        while not run_list:
            for inter in itertools.chain(*( child.values() for child in self._programs.values())):
                status = inter.status
                if status == InterpreterStatus.RUNNING:
                    run_list.append(inter)
                # TODO: change if we want to be notified about all status changes
                elif (status == InterpreterStatus.SLEEPING and time.time() >= inter.wake_up_at):
                    inter.status = InterpreterStatus.RUNNING
                    run_list.append(inter)
                else:
                    self._update_status(inter)

            if not run_list:
                time.sleep(0.1)
        return run_list


    def get_next(self):
        # if we get an empty list, either everyone is blocked, or they are all finished
        list = self._get_next_round()
        while list:
            for inter in list:
                inter = list.pop()

                yield inter.exec_next

            list = self._get_next_round()

    def add_thread(self, inter):
        thread_list = self._programs.setdefault(inter.program_id, dict())
        thread_list[inter.thread_id] = inter

        if inter.runtime_id == self._my_runtime_id:
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

    def pop_thread(self, program_id, thread_id):
        return self._programs[program_id].pop(thread_id)

    def __getitem__(self, program_id):
        return self._programs[program_id]

    def __delitem__(self, program_id):
        del self._programs[program_id]


