import itertools
from .inter import SimpleScriptInterpreter, InterpreterStatus



class RuntimeScheduler():

    def __init__(self, comms):
        self.total_threads = 0
        self._programs = dict()
        self._blocked_programs = dict()
        self._remote_programs = dict()
        self._comms = comms

    def _get_next_round(self):
        """ Generate a run list and yield threads in a round-robin fashion """
        #FIXME: this is less bad :)

        run_list = [ ]
        while not run_list:
            for inter in itertools.chain(*( child.values() for child in self._programs.values())):
                print(inter.program_id, inter.thread_id, inter.status.name)
            # Keep track of threads status
            total_blocked = 0
            total_sleeping = 0
            total_finished = 0

            for inter in itertools.chain(*( child.values() for child in self._programs.values())):
                status = inter.status

                if status == InterpreterStatus.RUNNING:
                    run_list.append(inter)

                elif (status == InterpreterStatus.SLEEPING and
                        time.time() >= inter.wake_up_at):
                    # wake this one up
                    inter.status = InterpreterStatus.RUNNING
                    run_list.append(inter)

                elif (status == InterpreterStatus.BLOCKED and
                        self._comms.can_receive_message(inter.waiting_from)):
                    # can unblock
                    inter.status = InterpreterStatus.RUNNING
                    run_list.append(inter)

                elif status == InterpreterStatus.BLOCKED:
                    total_blocked += 1

                elif status == InterpreterStatus.SLEEPING:
                    total_sleeping += 1

                elif status == InterpreterStatus.FINISHED:
                    total_finished += 1

            if total_blocked == self.total_threads - total_finished:
                self.logger.error("DEADLOCK! ABORTING!")
                raise RuntimeError

            if total_sleeping == self.total_threads - total_finished:
                self.logger.debug("All threads are sleeping...")
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

        self.total_threads += 1

    def pop_thread(self, program_id, thread_id):
        self.total_threads -= 1
        return self._programs[program_id].pop(thread_id)

    def __getitem__(self, program_id):
        return self._programs[program_id]

    def __delitem__(self, program_id):
        del self._programs[program_id]
