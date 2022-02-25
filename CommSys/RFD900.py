# Relevant methods to read from radio/UART
import queue

import serial
import time
from threading import Thread, Lock
from CommSys.Packet import Packet, PacketError, MIN_PACKET_SIZE
import logging

SER_DEVICE = "/dev/ttyAMA0"
BAUD=115200
RTSCTS = False
FLUSH_TIME = 10

logger = logging.getLogger(__name__)


class RFD900:
    def __init__(self):
        self.radio = None
        self.read_buf = b''
        self.flush_timer = 0
        self.read_queue_lock = Lock()
        self.read_queue = []
        self.t = Thread(target=self.__update)
        self.stopped = True

    def start(self):
        if self.stopped:
            logger.debug("RFD900x Handler started.")
            self.radio = serial.Serial(SER_DEVICE, baudrate=BAUD, rtscts=RTSCTS)
            self.stopped = False
            self.t.start()

    def stop(self):
        if not self.stopped:
            self.stopped = True
            self.t.join()
            self.radio.close()
            self.radio = None
            logger.debug("RFD900x Handler stopped.")

    def write(self, packet: Packet):
        if not self.stopped:
            self.radio.write(packet.to_binary())

    def read(self):
        if len(self.read_queue) > 0:
            with self.read_queue_lock:
                return self.read_queue.pop(0)
        return None

    def __update(self):
        while not self.stopped:
            # Read any incoming bytes from serial
            read_len = self.radio.inWaiting()
            self.read_buf += self.radio.read(read_len)

            if read_len > 0:
                # Reset timer if any bytes were added
                self.flush_timer = time.time() + FLUSH_TIME

            # Try to make a packet from read_buf
            try:
                packet = Packet(data=self.read_buf)
                if packet.checksum == packet.calc_checksum():
                    # Valid packet was created
                    with self.read_queue_lock:
                        self.read_queue.append(packet)
                else:
                    logger.debug(f"Radio dropped packet (ID: {packet.id}) due to invalid checksum. "
                                 f"Expected: {packet.checksum}, Actual: {packet.calc_checksum()}")
                self.read_buf = self.read_buf[(packet.length + MIN_PACKET_SIZE):]
            except PacketError:
                pass
            except ValueError:
                # Invalid MsgType was given, flush read_buf
                self.read_buf = b''
                logger.debug(f"Radio dropped packet due to invalid MsgType")

            if time.time() > self.flush_timer and len(self.read_buf) > 0:
                self.read_buf = b''
                logger.warning("RFD900 buffer being flushed due to timeout.")
