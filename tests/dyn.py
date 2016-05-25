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

        # PUB socket
        self.pub_sock = context.socket(zmq.PUB)
        self.pub_sock.bind('epgm://{}:{}'.format(IP, PORT))

        # SUB socket
        self.sub_sock = context.socket(zmq.SUB)
        self.sub_sock.setsockopt_string(zmq.SUBSCRIBE, '')
        self.sub_sock.connect('epgm://{}:{}'.format(IP, PORT))

        # REQ socket
        #self.req_sock = context.socket(zmq.REQ)

        # REP socket
        self.rep_sock = context.socket(zmq.REP)
        self.port = self.rep_sock.bind_to_random_port('tcp://*')

        # Setup polling mechanism
        self.poller = zmq.Poller()
        self.poller.register(self.sub_sock, zmq.POLLIN)
        #self.poller.register(self.rep_sock, zmq.POLLIN)

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
                    PacketType.PRINT
                ], timeout=2000)
            except KeyboardInterrupt:
                print('Request shutdown..')
                self.shutdown()
                return

            if not packet:
                self.print_runtimes()
                continue

            print('Got new message!')
            if packet.type == PacketType.DISCOVER_REQ:
                # Save runtime data
                ip, port = packet['ip'], packet['port']
                self.runtimes.add( (ip, port, packet['runtime_id']) )

                print('Sending runtime info @ {}:{}'.format(ip, port))

                # Send runtime info
                pkt = make_packet(
                    PacketType.DISCOVER_REP,
                    ip=self.ip,
                    port=self.port,
                    runtime_id=self.runtime_id
                )
                self.send_packet(pkt)

            elif packet.type == PacketType.DISCOVER_REP:
                # Save runtime data
                ip, port = packet['ip'], packet['port']
                self.runtimes.add( (ip, port, packet['runtime_id']) )

                print('Found company @ {}:{}'.format(ip, port))

            elif packet.type == PacketType.SHUTDOWN_REQ:
                ip, port = packet['ip'], packet['port']
                entry = (ip, port, packet['runtime_id'])

                # Remove runtime entry
                if entry in self.runtimes:
                    self.runtimes.remove(entry)
                    print('Lost company @ {}:{}'.format(ip, port))

                pkt = make_packet(
                    PacketType.SHUTDOWN_ACK,
                    ip=self.ip,
                    port=self.port,
                    runtime_id=self.runtime_id
                )
                self.send_packet(pkt)

            elif packet.type == PacketType.PRINT:
                self.print_runtimes()

    def shutdown(self):
        print('Signaling other runtimes...')

        # Broadcast SHUTDOWN_REQ packet
        pkt = make_packet(
            PacketType.SHUTDOWN_REQ,
            ip=self.ip,
            port=self.port,
            runtime_id=self.runtime_id
        )
        self.send_packet(pkt)

        while len(self.runtimes) > 1:
            packet = self.recv_packet(PacketType.SHUTDOWN_ACK)

            entry = (packet['ip'], packet['port'], packet['runtime_id'])
            assert(entry in self.runtimes)

            self.runtimes.remove(entry)

        print('Shutting down...')


    def print_runtimes(self):
        print('======== RUNTIMES =======')
        for i, rt in enumerate(sorted(self.runtimes)):
            print('[{}]: {}:{} - {}'.format(i, *rt))
        print('=========================')

    def send_packet(self, packet, addr=None):
        if addr: # REQ socket shall be used
            self.req_sock = self.context.socket(zmq.REQ)
            self.req_sock.connect('tcp://{}:{}'.format(*addr))
            self.req_sock.send_pyobj(packet)
            self.req_sock.disconnect('tcp://{}:{}'.format(*addr))
            self.req_sock.close()

        else: # PUB (multicast) shall be used
            self.pub_sock.send_pyobj(packet)

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
                packet = sock.recv_pyobj()

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
