from enum import Enum
import numpy as np

# Triton Datagram
# Bytes: 0        1        2        3
#       ┌───────────────────────────────────┐
#       | - Type - | -------- ID ---------- |
#       | --- Checksum --- | --- Length ----|
#       | -------------- Data ------------- |
#       |                 ...               |

#       └───────────────────────────────────┘

NUM_TYPE_BYTES = 1
NUM_ID_BYTES = 3
NUM_CKSM_BYTES = 2
NUM_LEN_BYTES = 2

MIN_PACKET_SIZE = NUM_ID_BYTES + NUM_TYPE_BYTES + \
                  NUM_CKSM_BYTES + NUM_LEN_BYTES
MAX_DATA_SIZE = pow(2, (8 * NUM_LEN_BYTES))


class PacketError(Exception):
    pass


class MsgType(Enum):
    NULL = b'\x00'
    HANDSHAKE = b'\x01'  # Starts flow-control based communication
    SACK = b'\x02'  # Selective Ack
    CACK = b'\x03'  # Cumulative Ack
    DACK = b'\x04'  # Duplicate Ack

    TEXT = b'\x05'  # General text to deliver to applications
    INFO = b'\x06'  # General information about robot, used for logging
    ERROR = b'\x07'  # Critical error information

    GPS_DATA = b'\x08'  # GPS + Magnetometer Data (from robot to land base)
    IMAGE = b'\x09'
    MTR_CMD = '\x0A'  # Motor Command
    GPS_CMD = b'\x0B'

    IP = b'\x0C'  # Data is an IP datagram to be forwarded (NOT IMPLEMENTED BY RELEASE)


class Packet:
    def __init__(self, ptype: MsgType = MsgType.NULL, pid=None, data: bytes = b'', calc_cksm=False):
        # Parameterized Constructor
        if pid is not None:
            # Check data length to ensure it is < 2^16
            if len(data) > MAX_DATA_SIZE:
                raise PacketError(f'Failed to create packet, '
                                  f'maximum data length ({len(data)}/{MAX_DATA_SIZE}) exceeded.')

            self.type = ptype
            self.id = pid
            self.checksum = bytes(NUM_CKSM_BYTES)
            self.length: int = len(data)
            self.data = data
            if calc_checksum:
                self.checksum = self.calc_checksum()

        # From-Binary Constructor
        elif len(data) >= MIN_PACKET_SIZE:
            index = 0
            self.type = MsgType(data[index: index + NUM_TYPE_BYTES])
            index += NUM_TYPE_BYTES
            self.id = int.from_bytes(data[index: index + NUM_ID_BYTES], byteorder='big')
            index += NUM_ID_BYTES
            self.checksum = data[index: index + NUM_CKSM_BYTES]
            index += NUM_CKSM_BYTES
            self.length = int.from_bytes(data[index: index + NUM_LEN_BYTES], byteorder='big')
            index += NUM_CKSM_BYTES

            if len(data)-index >= self.length:
                self.data = data[index: index + self.length]
            else:
                raise PacketError(f'Failed to create packet,'
                                  f'payload length ({len(data)-index}) did not meet expected length ({self.length}).')

        else:
            raise PacketError(f'Failed to create packet, '
                              f'invalid parameters.')

    def to_binary(self):
        return self.type.value + \
               self.id.to_bytes(length=NUM_ID_BYTES, byteorder='big') + \
               self.checksum + \
               self.length.to_bytes(length=NUM_LEN_BYTES, byteorder='big') + \
               self.data

    def calc_checksum(self):
        temp = self.checksum
        self.checksum = bytes(2)  # Set own, mutable checksum to 0
        new_checksum = calc_checksum(self.to_binary())
        self.checksum = temp  # Reset checksum
        return new_checksum


# Global checksum function for any bytes object
def calc_checksum(data: bytes):
    checksum_matrix = np.append(list(data), [0]*(len(data) % NUM_CKSM_BYTES))
    checksum_matrix = np.reshape(checksum_matrix, [-1, 2])
    checksum_matrix = checksum_matrix.astype(np.uint8)

    checksum = np.array([0]*NUM_CKSM_BYTES, dtype=np.uint8)

    for row in checksum_matrix:
        checksum = row ^ checksum

    checksum = int.from_bytes(checksum.tobytes(), byteorder='big')
    checksum = (pow(2, (8*NUM_CKSM_BYTES)) - checksum)  # Calculate the two's compliment

    return checksum.to_bytes(NUM_CKSM_BYTES, byteorder='big')


if __name__ == "__main__":
    Packet(data=b'\x01\x00\x00\x00\xff\x00\x00\x00')