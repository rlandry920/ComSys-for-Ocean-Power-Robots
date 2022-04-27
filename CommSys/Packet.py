from enum import Enum
import numpy as np
import struct
from CommSys.CommMode import CommMode

value = 5.13482358
value2 = 6512.65165
b = struct.pack('f', value)

# Packet.py
#
# Last updated: 04/12/2022 | Primary Contact: Michael Fuhrer, mfuhrer@vt.edu
# Triton Datagram implementation. Contains a low-overhead packet header and functions to convert packets
# to/from byte strings.
#
# Bytes: 0        1        2        3
#       ┌───────────────────────────────────┐
#       | ---------- SYNC_WORD ------------ |
#       | - Type - | -------- ID ---------- |
#       | --- Checksum --- | --- Length ----|
#       | -------------- Data ------------- |
#       |                 ...               |
#       └───────────────────────────────────┘

NUM_SYNC_BYTES = 4
NUM_TYPE_BYTES = 1
NUM_ID_BYTES = 3
NUM_CKSM_BYTES = 2
NUM_LEN_BYTES = 2

MIN_PACKET_SIZE = NUM_SYNC_BYTES + NUM_TYPE_BYTES + NUM_ID_BYTES + \
    NUM_CKSM_BYTES + NUM_LEN_BYTES
MAX_DATA_SIZE = pow(2, (8 * NUM_LEN_BYTES))

SYNC_WORD = b'\xAA' * NUM_SYNC_BYTES


class PacketError(Exception):
    pass

# Enumerated type values to represent data types Comm. System / applications may need to uniquely handle.
class MsgType(Enum):
    NULL = b'\x00'
    HANDSHAKE = b'\x01'  # Starts flow-control based communication
    HANDSHAKE_RESPONSE = b'\x02'  # Confirms connection
    SACK = b'\x03'  # Selective Ack
    CACK = b'\x04'  # Cumulative Ack
    DACK = b'\x05'  # Duplicate Ack

    TEXT = b'\x06'  # General text to deliver to applications
    INFO = b'\x07'  # General information about robot, used for logging
    ERROR = b'\x08'  # Critical error information

    GPS_DATA = b'\x09'  # GPS + Magnetometer Data (from robot to land base)
    IMAGE = b'\x0A'
    MTR_CMD = b'\x0B'  # Motor Command
    GPS_CMD = b'\x0C'
    MTR_SWITCH_CMD = b'\x0D'
    CTRL_REQ = b'\x0E'
    UDP = b'\x0F'  # UDP datagram to be forwarded

    HEARTBEAT_REQ = b'\x10' # Makes a request for a heartbeat from other party
    HEARTBEAT = b'\x11'     # Basic heartbe

    COMM_CHANGE = b'\x12'   # Notifies other party of a mode change, FORCES change, unlike handshakes


class Packet:
    def __init__(self, ptype: MsgType = MsgType.NULL, pid=0, data: bytes = b'', calc_checksum=False, cmode:CommMode=None):
        self.cmode = cmode  # Used by CommHandler to a. force tx of packet across medium or b. indicate which medium
                            # packet was rx'd through.

        # Parameterized Constructor, requires only ptype be set
        if ptype != MsgType.NULL:
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
            if data[0:NUM_SYNC_BYTES] != SYNC_WORD:
                raise PacketError(f'Failed to create packet,'
                                  f'invalid sync word: {data[0:4]}')
            index = NUM_SYNC_BYTES
            self.type = MsgType(data[index: index + NUM_TYPE_BYTES])
            index += NUM_TYPE_BYTES
            self.id = int.from_bytes(
                data[index: index + NUM_ID_BYTES], byteorder='big')
            index += NUM_ID_BYTES
            self.checksum = data[index: index + NUM_CKSM_BYTES]
            index += NUM_CKSM_BYTES
            self.length = int.from_bytes(
                data[index: index + NUM_LEN_BYTES], byteorder='big')
            index += NUM_CKSM_BYTES

            if len(data) - index >= self.length:
                self.data = data[index: index + self.length]
            else:
                raise PacketError(f'Failed to create packet,'
                                  f'payload length ({len(data) - index}) did not meet expected length ({self.length}).')

        else:
            raise PacketError(f'Failed to create packet, '
                              f'invalid parameters.')

    # Returns byte string representing the packet
    def to_binary(self):
        return SYNC_WORD + \
            self.type.value + \
            self.id.to_bytes(length=NUM_ID_BYTES, byteorder='big') + \
            self.checksum + \
            self.length.to_bytes(length=NUM_LEN_BYTES, byteorder='big') + \
            self.data

    # Mutes own checksum field, then returns calculated CRC-16 checksum of packet.
    def calc_checksum(self):
        temp = self.checksum
        self.checksum = bytes(2)  # Set own, mutable checksum to 0
        new_checksum = calc_checksum(self.to_binary())
        self.checksum = temp  # Reset checksum
        return new_checksum


# Global checksum function for any bytes object
def carry_around_add(a, b):
    c = a + b
    return (c & 0xffff) + (c >> 16)


def calc_checksum(msg):
    msg_padded = msg + (b'\x00' * (len(msg) % NUM_CKSM_BYTES))
    s = 0
    for i in range(0, len(msg), 2):
        w = msg_padded[i] + (msg_padded[i + 1] << 8)
        s = carry_around_add(s, w)
    return int.to_bytes(~s & 0xffff, NUM_CKSM_BYTES, 'big')


# Old CRC-16 checksum function, depreciated.
# def calc_checksum(data: bytes):
#     checksum_matrix = np.append(list(data), [0]*(len(data) % NUM_CKSM_BYTES))
#     checksum_matrix = np.reshape(checksum_matrix, [-1, 2])
#     checksum_matrix = checksum_matrix.astype(np.uint8)
#
#     checksum = np.array([0]*NUM_CKSM_BYTES, dtype=np.uint8)
#
#     for row in checksum_matrix:
#         checksum = row ^ checksum
#
#     checksum = int.from_bytes(checksum.tobytes(), byteorder='big')
#     # Calculate the two's compliment
#     checksum = (pow(2, (8*NUM_CKSM_BYTES)) - checksum)
#
#     return checksum.to_bytes(NUM_CKSM_BYTES, byteorder='big')

# Early packet construction tests.
if __name__ == "__main__":
    p0 = Packet(ptype=MsgType.TEXT, data=b'Hello world!')
    print(p0.to_binary())

    p1 = Packet(data=b'\xAA\xAA\xAA\xAA\x01\x00\x00\x00\xff\x00\x00\x00')
    print(p1.type, p1.id, p1.length, p1.data)

    try:
        p2 = Packet(data=b'\x01\x00\x00\x00\xff\x00\x00\x00')
    except PacketError as e:
        print("Success:", str(e))

    try:
        p3 = Packet(data=b'\x01\x00\x00\x00\x01\x00\x00\x00\xff\x00\x00\x00')
    except PacketError as e:
        print("Success:", str(e))
