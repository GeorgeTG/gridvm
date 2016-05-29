from enum import IntEnum, unique


@unique
class PacketType(IntEnum):
    """ All packets contain these keys by default:
        -- ip:          IP address of the sender
        -- port:        Port number that the sender is listening
        -- runtime_id:  Unique id of the runtime
    """

    UNINIT = 0b00000000

    DISCOVER_REQ = 0b00000010
    DISCOVER_REP = 0b00000011

    DISCOVER_THREAD_REQ = 0b00000110
    DISCOVER_THREAD_REP = 0b00000111

    SHUTDOWN_REQ = 0b00000100
    SHUTDOWN_ACK = 0b00000101

    THREAD_MESSAGE =     0b00001000 # thread_uid, status
    RUNTIME_STATUS_REQ = 0b00011001 # thread_uid, status
    RUNTIME_PRINT_REQ  = 0b00011010 # thread_uid, msg

    MIGRATE_THREAD =      0b00100000 # thread_uid, thread
    MIGRATION_COMPLETED = 0b00100001 # thread_uid

    ACK   = 0b11111111
    RETRY = 0b11111110
    NACK  = 0b11111100

    PRINT = 0b10000000

    """
        """

    def reply_type(self):
        if self.value & 1 > 0:
            raise ValueError('PacketType [{}] does not have a reply type'.format(self.name))
        return PacketType(self.value | 1)
