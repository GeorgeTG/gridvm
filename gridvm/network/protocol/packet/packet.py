import json
import collections

from collections import MutableMapping

from .header import PacketHeader
from .ptype import PacketType


def _json_to_bytes(mapping, encoding='utf-8'):
    """Dump a json object to bytes"""
    return json.dumps(mapping).encode(encoding)

def _bytes_to_json(data, encoding='utf-8'):
    """Get a json object from bytes"""
    try:
        return json.loads( data.decode(encoding) )
    except:
        return {}

class Packet():
    """This class represents a tinynfs packet"""
    def __init__(self, type=PacketType.UNINIT, payload=None, meta=None):
        self.header = PacketHeader()
        self.type = type
        self.payload = payload if payload else b''
        self._meta = meta if meta else dict()

    def items(self):
        return self._meta.items()

    def __getitem__(self, key):
        item = self._meta[key]
        if isinstance(item, list):
           return tuple(item)
        return item

    def __setitem__(self, key, value):
        self._meta[key] = value

    def __contains__(self, key):
        return key in self._meta

    def __delitem__(self, key):
        del self._meta[key]

    @property
    def payload(self):
        return self._payload

    @payload.setter
    def payload(self, value):
        if not isinstance(value, (bytes, bytearray)):
            raise TypeError('payload should be bytes')
        self._payload = bytes(value)

    @property
    def type(self):
        return PacketType(self.header.ptype)

    @type.setter
    def type(self, ptype):
        if not isinstance(ptype, PacketType):
            raise TypeError("Bad packet type")
        self.header.ptype = ptype.value

    def _get_checksum(self):
        return b'0000'

    def to_bytes(self):
        """Convert this Packet to raw bytes"""
        metadata = _json_to_bytes(self._meta)
        self.header._offset =  len(metadata)
        self.header.length = PacketHeader.size + len(metadata) + len(self._payload)
        return self.header.to_bytes() + metadata + self._payload + self._get_checksum()

    @classmethod
    def from_bytes(cls, buf):
        """Get a Packet instance from raw bytes"""
        pkt = cls()

        # reconstruct the header
        pkt.header = PacketHeader.from_bytes(buf[:PacketHeader.size])

        # offset to split metadata and payload
        offset = pkt.header._offset + PacketHeader.size

        pkt._meta = _bytes_to_json(buf[PacketHeader.size:offset])
        pkt._payload = buf[offset:-4] #exclude checksum

        #TODO: checums maybe ?

        return pkt

    def __str__(self):
        desc = 'Packet object @ {:#018x}\n'.format(id(self))
        desc += 'Type: {}\n'.format(self.type.name)
        for key, value in self.items():
            desc += '{}: {}\n'.format(key, value)
        desc += 'Payload: {} bytes.'.format(len(self._payload))
        return desc

    def __eq__(self, other):
        return all(
            (self.header == other.header,
            self.payload == other.payload,
            self._meta == other._meta
            ))

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return self.type

    def __len__(self):
        return len(self.payload) + len(self.header)
