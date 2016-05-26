from enum import IntEnum, unique


@unique
class PacketType(IntEnum):
    UNINIT = 0b00000000

    DISCOVER_REQ = 0b00000010
    DISCOVER_REP = 0b00000011

    SHUTDOWN_REQ = 0b00000100
    SHUTDOWN_ACK = 0b00000101

    PRINT = 0b10000000

    ACK = 0b11111111
    WAIT = 0b11111110
    
    """
    DISCOVER_THREAD_REQ
    DISCOVER_THREAD_REP

    THREAD_MIGRATION_REQ

    THREAD_MESSAGE_SEND
    """

    def reply_type(self):
        if self.value & 1 > 0:
            raise ValueError('PacketType [{}] does not have a reply type'.format(self.name))
        return PacketType(self.value | 1)
