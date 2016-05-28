from queue import Queue, Empty

from gridvm.network.nethandler import NetHandler
from gridvm.network.protocol.packet.ptype import PacketType
from gridvm.network.protocol.packet.packet import Packet
from gridvm.network.protocol.packet.factory import make_packet

class EchoCommunication:
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

class NetworkCommunication:
    def __init__(self, net_interface):
        self._messages = { }    # Messages that have arrived for threads
        self._fwd_table = { }   # Forwarding table <pid, tid> -> <runtime_id>

        self._print_req = Queue()
        self._status_req = Queue()

        self._to_send = Queue() # Packets that should be send over network (runtime_id, packet)
        self.nethandler = NetHandler(self, net_interface)

    def receive_message(self, thread_uid):
        """ Called from Runtime to receive a message destined for a thread

        Parameters:
            -- thread_uid: (program_id, thread_id)
        """

        # Create queue if not exist
        queue = self._messages.setdefault(thread_uid, Queue())

        try:
            return queue.get(block=False)
        except Empty:
            return None

    def can_receive_message(self, thread_uid):
        """ Called from Runtime to check if a message is pending for a thread

        Parameters:
            -- thread_uid: (program_id, thread_id)
        """
        queue = self._messages.setdefault(thread_uid, Queue())
        return not queue.empty()

    def send_message(self, thread_uid, msg):
        """ Called from Runtime to send a message to another thread (same program)

            Parameters:
                -- thread_uid:  (program_id, thread_id)
                -- msg:         message to send
        """
        runtime_id = self._get_runtime_id(thread_uid)

        packet = make_packet(
            PacketType.THREAD_MESSAGE,
            thread_uid=thread_uid,
            payload=msg
        )
        self._to_send.put( (runtime_id, packet) )

    def get_print_requests(self):
        """ Called from Runtime to get a list of print requests for its own threads """
        return self._get_list( self._print_req )

    def send_print_request(self, thread_uid, msg):
        """ Called from Runtime to send a print request to responsible runtime

            Parameters:
                -- thread_uid:  (program_id, thread_id)
                -- msg:         message to print
        """

        # TODO: find a way to get original runtime id
        #runtime_id = self._get_runtime_id(who)

        """
        packet = make_packet(
            PacketType.RUNTIME_PRINT_REQ,
            thread_uid=thread_uid,
            msg=msg
        )
        self._to_send.put( (runtime_id, packet) )
        """
        pass

    def add_print_request(self, packet):
        """ Called from NetHandler to add a print request which has arrived """
        pass

    def get_status_requests(self):
        """ Called from Runtime to get a list of thread status changes of its own threads """
        return self._get_list( self._status_req )

    def send_status_request(self, thread_uid, new_status):
        """ Called from Runtime to notify the thread's responsible runtime, for
            a thread status change """

        # TODO: find a way to get resposible runtime id
        pass

    def add_status_request(self, packet):
        """ Called from NetHandler to add a thread status request which has arrived """
        pass


    def update_thread_location(self, thread_uid, new_location):
        """ Called from NetHandler once a MIGRATION_COMPLETED packet has been received

        Paramters:
            -- thread_uid:       (program_id, thread_id)
            -- new_location:    runtime_id of its new location
        """
        self._fwd_table[thread_uid] = new_location

    def get_to_send_requests(self):
        return self._get_list( self._status_req )

    def shutdown(self):
        # TODO: move all foreign threads to other runtimes
        pass

    def _get_list(self, queue):
        """ Return a list from a ThreadSafe Queue """
        list = [ ]
        while True:
            try:
                list.append( queue.get(block=False) )
            except Empty:
                break

        return list

    def _get_runtime_id(self, thread_uid):
        """ Return the id of the runtime that currently runs this thread """
        if thread_uid not in self._fwd_table:
            # TODO: Broadcast message to discover the location of the thread
            print('ERROR: {} not in fwd table..'.format(thread_uid))
            return None

        return self._fwd_table[thread_uid]
