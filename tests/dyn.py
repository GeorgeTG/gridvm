import hashlib
import base64

import os
import sys
import time
import zmq

from gridvm.logger import get_logger
from gridvm.network.protocol.packet.packet import Packet
from gridvm.network.protocol.packet.factory import make_packet, make_packet
from gridvm.network.protocol.packet.ptype  import PacketType

IP = '224.0.0.1'
PORT = 19999

class DistrSys:
    def __init__(self, net_interface):
        self.runtime_id = fast_hash(str(time.time()))
        self.logger = get_logger('{}:NetHandler'.format(self.runtime_id))

        self.packet_storage = { type: [ ] for type in list(PacketType) }
        self.send_packets = set()
        self.runtimes = set()

        # hack to find own local IP
        f = os.popen('ifconfig {} | grep "inet\ addr" | cut -d: -f2 | cut -d" " -f1'
                        .format(net_interface))
        self.ip = f.read().strip()

        ################ SOCKETS #################
        context = self.context = zmq.Context()

        # Multicast PUB socket
        self.mpub_sock = context.socket(zmq.PUB)
        self.mpub_sock.bind('epgm://{}:{}'.format(IP, PORT))

        # Multicast SUB socket
        self.msub_sock = context.socket(zmq.SUB)
        self.msub_sock.setsockopt_string(zmq.SUBSCRIBE, '')
        self.msub_sock.connect('epgm://{}:{}'.format(IP, PORT))

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
        self.runtimes.add( (self.ip, self.port, self.runtime_id) )

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

        while True:
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
                self.logger.info('Request shutdown...')

                if len(self.runtimes) == 1:
                    break # I am the only one

                # Broadcast SHUTDOWN_REQ packet
                self.logger.info('Signaling other runtimes...')
                pkt = make_packet(
                    PacketType.SHUTDOWN_REQ,
                    ip=self.ip,
                    port=self.port,
                    runtime_id=self.runtime_id
                )
                self.send_packet(pkt)
                continue

            if not data: ##### DEBUGGING
                self.print_runtimes()
                continue

            addr, packet = data
            self.logger.debug('Got packet "{}" from {}'.format(
                PacketType(packet.type).name, 'peer' if addr else 'multicast'
            ))
            self.logger.debug(packet)

            if packet.type == PacketType.PRINT:
                self.print_runtimes()
                continue

            # TODO: Split into functions
            ip, port, runtime_id = packet['ip'], packet['port'], packet['runtime_id']

            if packet.type == PacketType.DISCOVER_REQ:
                # Save runtime data & listen for later requests
                self.runtimes.add( (ip, port, runtime_id) )

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
                self.runtimes.add( (ip, port, packet['runtime_id']) )
                self.logger.info('Found peer @ {}:{}'.format(ip, port))

            elif packet.type == PacketType.SHUTDOWN_REQ:
                # Remove runtime entry
                entry = (ip, port, runtime_id)
                if entry not in self.runtimes:
                    self.logger.warning("Peer {} not in my table".format(
                        runtime_id
                    ))
                    continue

                self.runtimes.remove(entry)

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
                entry = (ip, port, runtime_id)
                if entry not in self.runtimes:
                    self.logger.warning("Runtime {} not in {}'s table".format(
                        runtime_id, self.runtime_id
                    ))
                    continue

                self.runtimes.remove(entry)

                # Send ACK to sender
                self.logger.debug('Sending ACK @ {}:{}'.format(ip, port))
                self.send_ack_reply(addr)

                # Check if all runtimes have answered
                if len(self.runtimes) <= 1:
                    self.logger.info('Signaled all other runtimes!')
                    break

        # Closes all sockets
        self.mpub_sock.close()
        self.msub_sock.close()
        self.req_sock.close()
        self.rep_sock.close()
        self.context.term()

    def shutdown(self):
        pass

    def print_runtimes(self):
        print('======== RUNTIMES =======')
        for i, rt in enumerate(sorted(self.runtimes)):
            print('[{}]: {}:{} - {}'.format(i, *rt))
        print('=========================')

    def send_packet(self, packet, addr=None):
        if addr: # REQ socket shall be used
            ip, port = addr
            addr = 'tcp://{}:{}'.format(ip, port)
            self.req_sock.connect(addr)
            self.req_sock.send(packet.to_bytes())

            # Await for ACK
            self.logger.debug('Waiting for ACK/WAIT from {}:{}'.format(ip, port))
            pkt = self.req_sock.recv()
            pkt = Packet.from_bytes(pkt)
            self.logger.debug('Got {}!'.format(packet.type))
            #print(pkt)

            # Check reply packet
            if pkt.type == PacketType.WAIT:
                # TODO: add to send queue again
                # TODO: maybe sleep a tiny time
                pass

            self.req_sock.disconnect(addr)

        else: # Multicast PUB shall be used
            self.mpub_sock.send_pyobj(packet)
            self.send_packets.add(packet)

    def send_ack_reply(self, addr):
        """ Reply to sender (@ addr) with ACK """
        ack_pkt = make_packet(PacketType.ACK)
        #print(ack_pkt)
        #print(addr)
        self.rep_sock.send_multipart([
            addr,
            b'',
            ack_pkt.to_bytes()
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

                # Check if packet is one of the previously sent
                if packet in self.send_packets:
                    self.send_packets.remove(packet)
                    continue

                # Check if we got the packet we want
                if packet.type in packet_types:
                    return (addr, packet)

                self.packet_storage[packet.type].append( (addr, packet) )

def fast_hash(buff, length=8):
    try:
        buff = buff.encode('utf-8')
    except:
        pass

    h = hashlib.sha256(buff)
    h = h.digest()
    return str(base64.urlsafe_b64encode(h), 'ascii')[:length]

if __name__ == '__main__':
    #assert(len(sys.argv) == 3)

    #_, interface, local_ip = sys.argv

    ds = DistrSys('wlan0')
    ds.start()

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
