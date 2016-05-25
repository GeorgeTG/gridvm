
from .ptype import PacketType
from .packet import Packet

def make_packet(type, payload=b'', **kwargs):
    """Factory function to easily create packets"""
    pkt = Packet(type=type)

    pkt.payload = payload
    for key, value in kwargs.items():
        pkt[key] = value
    return pkt


def make_reply(packet, new_payload=b'', **kwargs):
    """Create an reply packet for the packet provided
        'packet' can be Packet or bytes
    """
    if isinstance(packet, bytes):
        packet = Packet.from_bytes(packet)
    elif not isinstance(packet, Packet):
        raise TypeError('Expected bytes or Packet, got {}'.format(type(packet)))

    try:
        fid = packet['file_id']
    except KeyError:
        fid = 0

    return make_packet(
       type=packet.type.reply_type(),
        payload=new_payload,
        file_id=fid,
        **kwargs
    )
