import struct
import sys

"""
Ptype          1 byte   [PacketType]
Length         2 bytes  [Packet length]
Split offset   2 bytes  [Split metadata from binary payload] [0=header.size]
"""

STRUCT_FORMAT = '!BHH'

class PacketHeader(object):
    """A wrapper class for raw headers"""

    fields = ['ptype', '_offset', 'length']
    size = struct.calcsize(STRUCT_FORMAT)

    def __init__(self, **kwargs):
        self.ptype = 0
        self.length = PacketHeader.size
        self._offset = PacketHeader.size

    def to_bytes(self):
        """Convert to raw bytes ready to be transmited"""
        return struct.pack(
            STRUCT_FORMAT,
            self.ptype,
            self.length,
            self._offset
        )
    @classmethod
    def from_bytes(cls, buf):
        """Get a PacketHeader instance from raw bytes"""
        fields = struct.unpack_from(STRUCT_FORMAT, buf)

        header = cls() # create a new header instance
        header.ptype = fields[0]
        header.length = fields[1]
        header._offset = fields[2]
        return header

    def __eq__(self, other):
        """ Lazy header equality """
        return type(self) == type(other) and all( getattr(self, field) == getattr(other, field)
                      for field in self.fields )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __len__(self):
        return PacketHeader.size
