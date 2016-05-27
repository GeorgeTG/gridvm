from queue import Queue, Empty

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
    def __init__(self, runtime):
        self._runtime = runtime
        self._messages = { }

        #self.net_handler = NetHandler()

    def recv(self, who):
        # Create queue if not exist
        queue = self._messages.setdefault(who, Queue())

        try:
            return queue.get(block=False)
        except Empty:
            return None

    def snd(self, to, what):
        # TODO: find where the thread is
        pass

    def can_recv(self, who):
        pass

    def shutdown(self):
        # TODO: move all foreign threads to other runtimes
        pass
