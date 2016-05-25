import hashlib
import base64

import os
import sys
import time
import zmq

from gridvm.network.protocol.packet.packet import Packet
from gridvm.network.protocol.packet.factory import make_packet, make_packet
from gridvm.network.protocol.packet.ptype  import PacketType

IP = '224.0.0.1'
PORT = 19999

class DistrSys:
    def __init__(self, net_interface):
        self.runtime_id = fast_hash(str(time.time()))
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
        self.pub_sock = context.socket(zmq.PUB)
        self.port = self.pub_sock.bind_to_random_port('tcp://*')

        # Message SUB socket
        self.sub_sock = context.socket(zmq.SUB)
        self.sub_sock.setsockopt_string(zmq.SUBSCRIBE, self.runtime_id)

        # Setup polling mechanism
        self.poller = zmq.Poller()
        self.poller.register(self.msub_sock, zmq.POLLIN)
        self.poller.register(self.sub_sock, zmq.POLLIN)
        #########################################

        # Add myself to runtimes
        self.runtimes.add( (self.ip, self.port, self.runtime_id) )

    def discover(self):
        # Send DISCOVER_REQ packet through multicast
        print ('Send DISCOVER...')
        pkt = make_packet(
            PacketType.DISCOVER_REQ,
            ip=self.ip,
            port=self.port,
            runtime_id=self.runtime_id
        )
        self.send_packet(pkt)
        print('Done...')

        while True:
            try:
                packet = self.recv_packet([
                    PacketType.DISCOVER_REQ,
                    PacketType.DISCOVER_REP,
                    PacketType.SHUTDOWN_REQ,
                    PacketType.SHUTDOWN_ACK,
                    PacketType.PRINT
                ], timeout=2000)
            except KeyboardInterrupt:
                print('Request shutdown..')

                if len(self.runtimes) == 1:
                    # I am the only one
                    break

                print('Signaling other runtimes...')
                # Broadcast SHUTDOWN_REQ packet
                pkt = make_packet(
                    PacketType.SHUTDOWN_REQ,
                    ip=self.ip,
                    port=self.port,
                    runtime_id=self.runtime_id
                )
                self.send_packet(pkt)
                continue

            if not packet:
                self.print_runtimes()
                continue

            print('Got new message!')
            print(packet)
            ip, port, runtime_id = packet['ip'], packet['port'], packet['runtime_id']

            # TODO: Split into functions
            if packet.type == PacketType.DISCOVER_REQ:
                # Save runtime data & listen for later requests
                self.runtimes.add( (ip, port, runtime_id) )
                self.sub_sock.connect('tcp://{}:{}'.format(ip, port))

                # Send runtime info
                print('Sending runtime info @ {}:{}'.format(ip, port))
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
                self.sub_sock.connect('tcp://{}:{}'.format(ip, port))

                print('Found company @ {}:{}'.format(ip, port))

            elif packet.type == PacketType.SHUTDOWN_REQ:
                # Ignore later requests for this runtime
                self.sub_sock.disconnect('tcp://{}:{}'.format(ip, port))

                # Remove runtime entry
                entry = (ip, port, runtime_id)
                if entry not in self.runtimes:
                    assert("Runtime {} not in {}'s table".format(
                        runtime_id, self.runtime_id
                    ))
                    continue

                self.runtimes.remove(entry)
                print('Lost company @ {}:{}'.format(ip, port))

                # Send SHUTDOWN_ACK
                pkt = make_packet(
                    PacketType.SHUTDOWN_ACK,
                    ip=self.ip,
                    port=self.port,
                    runtime_id=self.runtime_id
                )
                self.send_packet(pkt, runtime_id=runtime_id)

            elif packet.type == PacketType.SHUTDOWN_ACK:
                entry = (ip, port, runtime_id)
                if entry not in self.runtimes:
                    assert("Runtime {} not in {}'s table".format(
                        runtime_id, self.runtime_id
                    ))
                    continue

                self.runtimes.remove(entry)

                if len(self.runtimes) <= 1:
                    print('Signaled all other runtimes!')
                    break

            elif packet.type == PacketType.PRINT:
                self.print_runtimes()

        # Closes all sockets
        self.mpub_sock.close()
        self.msub_sock.close()
        self.pub_sock.close()
        self.sub_sock.close()
        self.context.term()

    def shutdown(self):
        pass

    def print_runtimes(self):
        print('======== RUNTIMES =======')
        for i, rt in enumerate(sorted(self.runtimes)):
            print('[{}]: {}:{} - {}'.format(i, *rt))
        print('=========================')

    def send_packet(self, packet, runtime_id=None):
        if runtime_id: # PUB socket shall be used
            self.pub_sock.send_multipart([
                runtime_id.encode('utf8'),
                packet.to_bytes()
            ])
        else: # Multicast PUB shall be used
            self.mpub_sock.send_pyobj(packet)
            self.send_packets.add(packet)

    def recv_packet(self, packet_types, timeout=None):
        if not isinstance(packet_types, list):
            packet_types = [ packet_types ]

        # Check first if we have already recv that packet
        # and it has been saved in storage
        for ptype in packet_types:
            if len(self.packet_storage[ptype]) > 0:
                return self.packet_storage[ptype].pop()

        while True:
            avail_socks = dict( self.poller.poll(timeout=timeout) )

            #print(avail_socks)
            if not avail_socks: # Timeout has occured
                return None

            for sock in avail_socks:
                if sock == self.msub_sock:
                    packet = sock.recv_pyobj()
                else:
                    _, packet = sock.recv_multipart()
                    packet = Packet.from_bytes(packet)

                # Check if packet is one of the previously sent
                if packet in self.send_packets:
                    self.send_packets.remove(packet)
                    continue

                # Check if we got the packet we want
                if packet.type in packet_types:
                    return packet

                self.packet_storage[packet.type].append(packet)

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
    ds.discover()

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
