from enum import Enum

###
# Datagram:
# -----------------------------------------------------------------
# || Type (1 byte) || Length (2 bytes) || Payload (Length bytes) ||
# -----------------------------------------------------------------
###

NUM_TYPE_BYTES = 1
NUM_LENGTH_BYTES = 2  # Offers same possible length as a standard IP packet

MIN_PACKET_SIZE = NUM_TYPE_BYTES + NUM_LENGTH_BYTES


class CommError(BaseException):
    pass


class MsgType(Enum):
    NULL = b'\x00'
    TEXT = b'\x01'
    INFO = b'\x02'  # General information about robot, used for logging
    ERROR = b'\x03'  # Critical error information
    MTR_CMD = '\x07'  # Motor Command
    GPS_DATA = b'\x08'  # GPS + Magnetometer Data (from robot to land base)
    GPS_CMD = b'\x09'
    IMAGE = b'\x0A'
    IP = b'\x10'


class Packet:

    def __init__(self, msg_type=MsgType.NULL, payload=b''):
        if len(payload) > pow(2, (8 * NUM_LENGTH_BYTES)):
            raise CommError("Payload must contain less than 2^16 bytes!")

        self.m_type = msg_type
        self.m_length = len(payload)
        self.m_payload = payload

    def from_binary(self, binary_word):
        self.m_type = MsgType(binary_word[0:1])
        self.m_length = int.from_bytes(binary_word[1:3], byteorder='big')
        self.m_payload = binary_word[3:3 + self.m_length]
        return self

    def to_binary(self):
        return self.m_type.value + self.m_length.to_bytes(NUM_LENGTH_BYTES, byteorder='big') + self.m_payload
