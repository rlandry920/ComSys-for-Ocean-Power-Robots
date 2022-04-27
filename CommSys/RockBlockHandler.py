import CommSys.rockBlock as rockBlock
import logging
from CommSys.CommMode import CommMode
from CommSys.Packet import Packet, MsgType, PacketError
from threading import Lock, Thread
import time

# RockBlockHandler.py
#
# Last updated: 04/26/2022 | Primary Contact: Michael Fuhrer, mfuhrer@vt.edu
# Coverts functions found in 3rd party API, rockBlock.py, into a format the matches our 'abstract' handler format,
# i.e. has callable write_packet and read_packet functions. Uses a threading to continously check the RockBLOCK for
# any new packets.
#
# TODO List:
# - Validate implementation
# - Automatically resend packet to RockBLOCK if sendMessage fails (should be non-blocking)

SER_DEVICE = "dev/ttyUSB0"

logger = logging.getLogger(__name__)


class RockBlockHandler(Thread):
    def __init__(self):
        self.reliable = True
        self.proto = ISBDPacketProtocol()
        self.running = False

    def run(self):
        self.running = True
        while self.running:
            self.proto.message_check()
            time.sleep(3)  # Wait 3s before checking again

    def write_packet(self, packet: Packet):
        self.proto.write_packet(packet)

    def read_packet(self):
        return self.proto.read_packet()

    def close(self):
        self.stop()

    def stop(self):
        self.running = False
        self.join()


# Using a special protocol to handle certain asynchronous events during an exchange with RockBLOCK device.
class ISBDPacketProtocol(rockBlock.rockBlockProtocol):
    def __init__(self):
        # does NOT represent the time it takes for landbase to send an ACK
        self.received_packets = []
        self.received_packets_l = Lock()
        self.rb = rockBlock.rockBlock(SER_DEVICE, self)

    def __del__(self):
        self.rb.close()

    def message_check(self):
        self.rb.messageCheck()

    # Uses data found in asynchronous rx event to create packet.
    def rockBlockRxReceived(self, mtmsn, data):
        try:
            packet = Packet(data=self.read_buf, cmode=CommMode.SATELLITE)
            if packet.checksum == packet.calc_checksum():
                # Valid packet was created
                logger.debug(f"RockBlockHandler found valid packet (ID: {packet.id} Type: {packet.type}).")
                with self.received_packets_l:
                    self.received_packets.append(packet)
            else:
                logger.debug(f"RockBlockHandler dropped packet (ID: {packet.id}) due to invalid checksum. "
                             f"Expected: {packet.checksum}, Actual: {packet.calc_checksum()}")

        except PacketError as e:
            pass

        except ValueError:  # Invalid MsgType was given
            logger.debug(f"RockBlockHandler dropped packet due to invalid MsgType")

    def write_packet(self, packet: Packet):
        if self.rb.sendMessage(packet.to_binary()):
            logger.debug(f"Packet (Type {packet.type}) successfully accepted!")
        else:
            logger.debug(f"Packet (Type {packet.type}) failed to send.")

    def read_packet(self):
        if len(self.received_packets) > 0:
            with self.received_packets_l:
                return self.received_packets.pop(0)
        return None


if __name__ == "__main__":
    rb = RockBlockHandler()
    packet = Packet(MsgType.TEXT, data=b'Hello world!!!')
    rb.start()
    rb.write_packet(packet)
    recv = None
    while recv is None:
        recv = rb.read_packet()
    print(f'Received packet! Type: {packet.type} Length: {packet.length} Data: {packet.data}')
