from queue import Queue, Empty
from threading import Thread, Semaphore

from gridvm.network.nethandler import NetHandler
from gridvm.network.protocol.packet import PacketType
from gridvm.network.protocol.packet import Packet
from gridvm.network.protocol.packet import make_packet


class EchoCommunication:
    def __init__(self, *args, **kwargs):
        self._messages = {}

    def receive_message(self, who):
        queue = self._messages.setdefault(who, list())

        try:
            return queue.pop()
        except IndexError:
            return None

    def send_message(self, to, what):
        queue = self._messages.setdefault(to, list())
        queue.insert(0, what)

    def update_thread_location(*args, **kwargs):
        pass

    def can_receive_message(self, who):
        queue = self._messages.setdefault(who, list())
        return len(queue) > 0

    def shutdown(self):
        pass

class NetworkCommunication:
    def __init__(self, runtime_id, net_interface):
        self.runtime_id = runtime_id
        self._messages = { }    # Messages that have arrived for threads
        self._sent_messages = [ ] # Messages that have been sent over the network
        self._fwd_table = { }   # Forwarding table <pid, tid> -> <runtime_id>

        self._print_req = Queue()
        self._status_req = Queue()
        self._to_send = Queue() # Packets that should be send over network (runtime_id, packet)

        self._migration_req = Queue()
        self._sem = Semaphore(value=0)
        self._migrate_sucess = False


        self.nethandler = NetHandler(self, runtime_id, net_interface)

        # Start NetHandler
        self.nethandler_thread = Thread(target=self.nethandler.start)
        self.nethandler_thread.start()

    def receive_message(self, sender, recv):
        """ Called from Runtime to receive a message destined for a thread

        Parameters:
            -- thread_uid: (program_id, thread_id)
        """

        # Create queue if not exist
        queue = self._messages.setdefault( (recv, sender), Queue())

        try:
            return queue.get(block=False)
        except Empty:
            return None


    def receive_all_messages(self, thread_uid):
        """ Called from Runtime to receive all pending messages destined for a thread

        Parameters:
            -- thread_uid: (program_id, thread_id)
        Returns:
            -- List of messages, or an empty list if no messages in buffer
        """
        messages = { }

        for (recv, sender) in self._messages:
            if recv == thread_uid:
                messages[(recv, sender)] = [ ]

                while True:
                    msg = self.receive_message(sender, recv)
                    if msg == None:
                        break
                    messages[(recv, sender)].append(msg)

                if not messages[(recv, sender)]:
                    del messages[(recv, sender)]

        return messages


    def can_receive_message(self, sender, recv):
        """ Called from Runtime to check if a message is pending for a thread

        Parameters:
            -- thread_uid: (program_id, thread_id)
        """
        queue = self._messages.setdefault( (recv, sender), Queue())
        if not queue.empty():
            return True

        # Check if a message was sent over the network
        if (recv, sender) in self._sent_messages:
            print('Found sent message')
            self._sent_messages.remove( (recv, sender) )
            return True

        return False

    def send_message(self, recv, sender, msg):
        """ Called from Runtime to send a message to another thread (same program)

            Parameters:
                -- thread_uid:  (program_id, thread_id)
                -- msg:         message to send
        """
        runtime_id = self._get_runtime_id(recv)

        if runtime_id == self.runtime_id:
            # Simply add to local message queue
            queue = self._messages.setdefault((recv, sender), Queue())
            queue.put(msg)
        else:
            packet = make_packet(
                PacketType.THREAD_MESSAGE,
                recv=recv,
                sender=sender,
                msg=msg
            )
            self._to_send.put( (runtime_id, packet) )

            # Add to sent_messages
            print('Add {}:{}'.format(recv, sender))
            self._sent_messages.append( (recv, sender) )

    def add_thread_message(self, packet):
        """ Called from NetHandler to add a new thread message which has arrived """
        sender, recv, msg = packet['sender'], packet['recv'], packet['msg']

        # Add the message to the queue
        queue = self._messages.setdefault( (recv, sender), Queue())
        queue.put(msg)

    def restore_messages(self, thread_uid, messages):
        """ Called from runtime to restore pending messages """
        for (recv, sender) in messages:
            queue = self._messages.setdefault( (recv, sender), Queue())
            for msg in messages[(recv, sender)]:
                queue.put(msg)


    def get_print_requests(self):
        """ Called from Runtime to get a list of print requests for its own threads

        Returns a list of (thread_uid, msg) tuples
        """
        return self._get_list( self._print_req )

    def send_print_request(self, orig_runtime_id, thread_uid, msg):
        """ Called from Runtime to send a print request to responsible runtime

            Parameters:
                -- orig_runtime_id: runtime_id of the original runtime
                -- thread_uid:      (program_id, thread_id)
                -- msg:             message to print
        """

        if orig_runtime_id == self.runtime_id:
            self._print_req.put( (thread_uid, msg) )
        else:
            packet = make_packet(
                PacketType.RUNTIME_PRINT_REQ,
                thread_uid=thread_uid,
                msg=msg
            )
            self._to_send.put( (orig_runtime_id, packet) )

    def add_print_request(self, packet):
        """ Called from NetHandler to add a print request which has arrived """
        thread_uid, msg = packet['thread_uid'], packet['msg']
        self._print_req.put( (thread_uid, msg))



    def get_status_requests(self):
        """ Called from Runtime to get a list of thread status changes of its own threads

        Returns a list of (thread_uid, status) tuples
        """
        return self._get_list( self._status_req )

    def send_status_request(self, orig_runtime_id, thread_uid, new_status, waiting_from=None):
        """ Called from Runtime to notify the thread's responsible
            runtime, for a thread status change

            Parameters:
                -- orig_runtime_id: runtime_id of the original runtime
                -- thread_uid:      (program_id, thread_id)
                -- msg:             message to print
        """

        if orig_runtime_id == self.runtime_id:
            self._status_req.put( (thread_uid, (new_status, waiting_from)) )
        else:
            packet = make_packet(
                PacketType.RUNTIME_STATUS_REQ,
                thread_uid=thread_uid,
                status=new_status,
                waiting_from=waiting_from
            )
            self._to_send.put( (orig_runtime_id, packet) )

    def add_status_request(self, packet):
        """ Called from NetHandler to add a thread status request which has arrived """
        thread_uid, status, waiting_from = packet['thread_uid'], packet['status'], packet['waiting_from']
        self._status_req.put( (thread_uid, (status, waiting_from)) )



    def get_migrated_threads(self):
        """ Called from Runtime to get a list of newly migrated threads """
        return self._get_list( self._migration_req )

    def migrate_thread(self, thread_uid, thread_package, new_location):
        """ Called from Runtime to migrate the thread

        Parameters:
            -- thread_package:  the thread package we want to migrate
            -- new_location:    runtime_id of the target runtime
        """
        if new_location == self.runtime_id:
            return

        # Send packet
        packet = make_packet(
            PacketType.MIGRATE_THREAD,
            thread_uid=thread_uid,
            payload=thread_package
        )
        self._to_send.put( (new_location, packet) )

        # Wait for ACK
        self._sem.acquire()

        # Update thread location
        if self._migrate_sucess:
            self.update_thread_location(thread_uid, new_location)
            return True

        return False

    def migrate_thread_completed(self, result):
        """ Called from NetHandler to signal runtime that the migration is over """
        self._migrate_sucess = result

        # Unblock runtime
        self._sem.release()

    def add_thread_migration(self, packet):
        """ Called from NetHandler once a MIGRATE_THREAD packet has arrived """
        thread_uid, thread_blob = packet['thread_uid'], packet.payload
        self._migration_req.put(thread_blob)

        self.update_thread_location(thread_uid, self.runtime_id)


    def update_thread_location(self, thread_uid, new_location):
        """ Called from NetHandler once a MIGRATION_COMPLETED packet has been received
                or from Runtime to update its own threads location

        Parameters:
            -- thread_uid:       (program_id, thread_id)
            -- new_location:    runtime_id of its new location
        """
        self._fwd_table[thread_uid] = new_location

    def get_to_send_requests(self):
        """ Called from NetHandler """
        return self._get_list( self._to_send )

    def get_runtimes(self):
        return self.nethandler.runtimes

    def shutdown(self):
        self.nethandler.shutdown()

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
            packet = make_packet(
                PacketType.DISCOVER_THREAD_REQ,
                thread_uid=thread_uid
            )
            self._to_send.put( (None, packet) )

            # Wait for DISCOVER_THREAD_REP
            self._sem.acquire()

        return self._fwd_table[thread_uid]
