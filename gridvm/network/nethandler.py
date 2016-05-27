import os
import sys
import time
import zmq

from gridvm.logger import get_logger
from gridvm.network.protocol.packet.packet import Packet
from gridvm.network.protocol.packet.factory import make_packet, make_packet
from gridvm.network.protocol.packet.ptype  import PacketType
from gridvm.simplescript.runtime.utils import fast_hash

MULTICAST_IP = '224.0.0.1'
MULTICAST_PORT = 19999

class NetHandler:
    def __init__(self, comms, net_interface):
        self.runtime_id = fast_hash(str(time.time()))
        self.logger = get_logger('{}:NetHandler'.format(self.runtime_id))

        self.comms = comms

        self.packet_storage = { type: [ ] for type in list(PacketType) }
        self.msend_packets = set()  # Self-sent packets to multicast
        self.runtimes = { }         # <runtime_id> -> <ip, port>

        # hack to find own local IP (TODO: user should give its own local IP)
        f = os.popen('ifconfig {} | grep "inet\ addr" | cut -d: -f2 | cut -d" " -f1'
                        .format(net_interface))
        self.ip = f.read().strip()

        ################ SOCKETS #################
        context = self.context = zmq.Context()

        # Multicast PUB socket
        self.mpub_sock = context.socket(zmq.PUB)
        self.mpub_sock.bind('epgm://{}:{}'.format(MULTICAST_IP, MULTICAST_PORT))

        # Multicast SUB socket
        self.msub_sock = context.socket(zmq.SUB)
        self.msub_sock.setsockopt_string(zmq.SUBSCRIBE, '')
        self.msub_sock.connect('epgm://{}:{}'.format(MULTICAST_IP, MULTICAST_PORT))

        # Message PUB socket
        self.req_sock = context.socket(zmq.REQ)

        # Message SUB socket
        self.rep_sock = context.socket(zmq.ROUTER)
        self.port = self.rep_sock.bind_to_random_port('tcp://*')

        # Setup polling mechanism
        self.poller = zmq.Poller()
        self.poller.register(self.msub_sock, zmq.POLLIN)
        self.poller.register(self.rep_sock, zmq.POLLIN)
        #########################################

        # Add myself to runtimes
        self.runtimes[self.runtime_id] = (self.ip, self.port)

    def start(self):
        # Send DISCOVER_REQ packet through multicast
        self.logger.debug('Broadcast DISCOVER...')
        pkt = make_packet(
            PacketType.DISCOVER_REQ,
            ip=self.ip,
            port=self.port,
            runtime_id=self.runtime_id
        )
        self.send_packet(pkt)

        self._terminate = False
        while not self._terminate:

            # FIXME: Bad way - use select instead, for both socket and queue
            to_send = self.comms.get_to_send_requests()
            for (runtime_id, packet) in to_send:
                self.send_packet(packet, addr=self.runtimes[runtime_id])

            try:
                self.logger.debug('Waiting for packets...')
                data = self.recv_packet([
                    PacketType.DISCOVER_REQ,
                    PacketType.DISCOVER_REP,
                    PacketType.SHUTDOWN_REQ,
                    PacketType.SHUTDOWN_ACK,
                    PacketType.PRINT
                ], timeout=2000)
            except KeyboardInterrupt:
                self.shutdown()
                continue

            ##### DEBUGGING #######
            if not data:
                self.print_runtimes()
                continue

            addr, packet = data
            self.logger.debug('Got packet "{}" from {}'.format(
                PacketType(packet.type).name, 'peer' if addr else 'multicast'
            ))
            self.logger.debug(packet)

            ###### DEBUGGING #########
            if packet.type == PacketType.PRINT:
                self.print_runtimes()
                continue

            # TODO: Split into functions
            ip, port, runtime_id = packet['ip'], packet['port'], packet['runtime_id']

            if packet.type == PacketType.DISCOVER_REQ:
                # Save runtime data & listen for later requests
                self.runtimes[runtime_id] = (ip, port)

                # Send runtime info
                self.logger.debug('Sending runtime info @ {}:{}'.format(ip, port))
                pkt = make_packet(
                    PacketType.DISCOVER_REP,
                    ip=self.ip,
                    port=self.port,
                    runtime_id=self.runtime_id
                )
                self.send_packet(pkt)

            elif packet.type == PacketType.DISCOVER_REP:
                # Save runtime data & listen for this runtime requests
                self.runtimes[runtime_id] = (ip, port)
                self.logger.info('Found peer @ {}:{}'.format(ip, port))

            elif packet.type == PacketType.SHUTDOWN_REQ:
                # Remove runtime entry
                if runtime_id not in self.runtimes:
                    self.logger.warning("Peer '{}:{}'[{}] not in my table".format(
                        ip, port, runtime_id
                    ))
                    continue

                del self.runtimes[runtime_id]

                # Send SHUTDOWN_ACK
                self.logger.debug('Sending SHUTDOWN_ACK @ {}:{}'.format(ip, port))
                pkt = make_packet(
                    PacketType.SHUTDOWN_ACK,
                    ip=self.ip,
                    port=self.port,
                    runtime_id=self.runtime_id
                )
                self.send_packet(pkt, addr=(ip, port))
                self.logger.info('Lost peer @ {}:{}'.format(ip, port))

            elif packet.type == PacketType.SHUTDOWN_ACK:
                if runtime_id not in self.runtimes:
                    self.logger.warning("Peer '{}:{}'[{}] not in my table".format(
                        ip, port, runtime_id
                    ))
                    continue

                del self.runtimes[runtime_id]

                # Send ACK to sender
                self.logger.debug('Sending ACK @ {}:{}'.format(ip, port))
                self.send_reply(addr, PacketType.ACK)

                # Check if all runtimes have answered
                if len(self.runtimes) <= 1:
                    self.logger.info('Signaled all other runtimes!')
                    self._terminate = True
                    break

        self.cleanup()

    def shutdown(self):
        self.logger.info('Request shutdown...')
        if len(self.runtimes) == 1:
            self._terminate = True # I am the only one
            return

        # TODO: Send away all threads

        # Broadcast SHUTDOWN_REQ packet
        self.logger.info('Signaling other runtimes...')
        pkt = make_packet(
            PacketType.SHUTDOWN_REQ,
            ip=self.ip,
            port=self.port,
            runtime_id=self.runtime_id
        )
        self.send_packet(pkt)

    def cleanup(self):
        # Closes all sockets
        self.mpub_sock.close()
        self.msub_sock.close()
        self.req_sock.close()
        self.rep_sock.close()
        self.context.term()

        # TODO: Signal runtime to close

    def print_runtimes(self):
        to_print = '\n' + 10 * '=' + ' RUNTIMES ' + 10 * '=' + '\n'
        for i, (runtime_id, (ip, port)) in enumerate(sorted(self.runtimes.items())):
            to_print += '[{}]: {}:{} - {}\n'.format(i, ip, port, runtime_id)
        to_print += 30 * '='
        self.logger.debug(to_print)

    def send_packet(self, packet, addr=None):
        if addr: # REQ socket shall be used
            ip, port = addr
            addr = 'tcp://{}:{}'.format(ip, port)
            self.req_sock.connect(addr)
            self.req_sock.send(packet.to_bytes())

            # Await for ACK
            self.logger.debug('Waiting for ACK/WAIT from {}:{}'.format(ip, port))
            rep_packet = self.req_sock.recv()
            rep_packet = Packet.from_bytes(rep_packet)
            self.logger.debug('Got {}!'.format(PacketType(rep_packet.type).name))
            #print(pkt)

            # Check reply packet
            if rep_packet.type == PacketType.RETRY:
                # TODO: add to send queue again
                # TODO: maybe sleep a tiny time
                pass

            self.req_sock.disconnect(addr)

        else: # Multicast PUB shall be used
            self.mpub_sock.send_pyobj(packet)
            self.msend_packets.add(packet)

    def send_reply(self, addr, rep_type):
        """ Reply to sender (@ addr) with ACK """
        rep_packet = make_packet(rep_type)
        self.rep_sock.send_multipart([
            addr,
            b'',
            rep_packet.to_bytes()
        ])

    def recv_packet(self, packet_types, timeout=None):
        """ Return (addr, packet) where addr is the address of the sender (zmq)
            and packet is the recv Packet instance
        """
        if not isinstance(packet_types, list):
            packet_types = [ packet_types ]

        # Check first if we have already received a valid
        # packet and it has been saved in the storage
        for ptype in packet_types:
            if len(self.packet_storage[ptype]) > 0:
                return self.packet_storage[ptype].pop()

        while True:
            avail_socks = dict( self.poller.poll(timeout=timeout) )

            #print(avail_socks)
            if not avail_socks: # Timeout has occured
                return None

            for sock in avail_socks:
                if sock is self.rep_sock: # ROUTER socket
                    addr, _, packet = sock.recv_multipart()
                    packet = Packet.from_bytes(packet)
                elif sock is self.msub_sock: # SUB socket
                    addr, packet = None, sock.recv_pyobj()
                #print(addr, packet)

                # Check if packet is the same we previously sent over multicast
                if packet in self.msend_packets:
                    self.msend_packets.remove(packet)
                    continue

                # Check if we got the packet we want
                if packet.type in packet_types:
                    return (addr, packet)

                # Store the packet for later use
                self.packet_storage[packet.type].append( (addr, packet) )


if __name__ == '__main__':
    #assert(len(sys.argv) == 3)
    #_, interface, local_ip = sys.argv
    from threading import Thread
    from gridvm.simplescript.runtime.communication import NetworkCommunication

    comm = NetworkCommunication('wlan0')

    thread = Thread(target=comm.nethandler.start)
    thread.start()

    """
    while True:
        cmd = input('>> ')

        if cmd == 'discover':
            ds.discover()
        elif cmd == 'shutdown':
            ds.shutdown()
            break
        elif cmd == 'print':
            ds.print_state()
        else:
            print('Invalid command!')
    """
