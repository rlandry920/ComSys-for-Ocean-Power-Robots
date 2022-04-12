import serial
from serial.threaded import ReaderThread
import time
import logging
from threading import Lock
from CommSys.Packet import Packet, SYNC_WORD, MIN_PACKET_SIZE, PacketError

SER_DEVICE = "/dev/ttyAMA0"
BAUD = 115200
RTSCTS = False

logger = logging.getLogger(__name__)


class PacketReaderThread(ReaderThread):
    def __init__(self):
        self.ser = serial.Serial(SER_DEVICE, baudrate=BAUD)
        super(PacketReaderThread, self).__init__(self.ser, SerialPacketProtocol)
    
    def start(self):
        if not self.is_alive():
            super(PacketReaderThread, self).start()
    
    def close(self):
        if self.is_alive():
            super(PacketReaderThread, self).close()
    
    def write_packet(self, packet):
        if self.is_alive():
            return self.protocol.write_packet(packet)

    def read_packet(self):
        if self.is_alive():
            return self.protocol.read_packet()


class SerialPacketProtocol(serial.threaded.Protocol):
    def __init__(self):
        self.read_buf = b''
        self.received_packets = []
        self.received_packets_l = Lock()
        self.transport = None
        self.reliable_medium = False

    def connection_made(self, transport):
        self.transport = transport

    def connection_lost(self, exc):
        self.transport = None
        self.read_buf = b''
        super(SerialPacketProtocol, self).connection_lost(exc)

    def data_received(self, data):
        self.read_buf += data

        sync_ind = self.read_buf.find(SYNC_WORD)
        if sync_ind >= 0:
            # Sync word exists in read buffer, head to it
            if sync_ind > 0:
                logger.debug("SerialHandler jumping to found sync word")
                self.read_buf = self.read_buf[sync_ind:]

        # Try to make a packet from read_buf
        try:
            packet = Packet(data=self.read_buf)
            if packet.checksum == packet.calc_checksum():
                # Valid packet was created
                logger.debug(f"SerialHandler found valid packet (ID: {packet.id} Type: {packet.type}).")
                with self.received_packets_l:
                    self.received_packets.append(packet)
                self.read_buf = self.read_buf[(packet.length + MIN_PACKET_SIZE):]
            else:
                logger.debug(f"SerialHandler dropped packet (ID: {packet.id}) due to invalid checksum. "
                             f"Expected: {packet.checksum}, Actual: {packet.calc_checksum()}")
                logger.debug(f"Bad packet: {packet.to_binary()[0:32]}")
                self.read_buf = self.read_buf[len(SYNC_WORD):]  # Force jump to next syncword
        except PacketError as e:
            pass
        except ValueError:  # Invalid MsgType was given
            logger.debug(f"SerialHandler dropped packet due to invalid MsgType")
            self.read_buf = self.read_buf[len(SYNC_WORD):]  # Force jump to next syncword

    def write_packet(self, packet: Packet):
        self.transport.write(packet.to_binary())

    def read_packet(self):
        if len(self.received_packets) > 0:
            with self.received_packets_l:
                return self.received_packets.pop(0)
        return None
