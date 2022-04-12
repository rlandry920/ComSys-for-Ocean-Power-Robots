import rockBlock
import logging
from CommSys.CommHandler import CommMode
from CommSys.Packet import Packet, MsgType, PacketError
from threading import Lock, Thread

SER_DEVICE = "dev/ttyUSB0"

logger = logging.getLogger(__name__)

# Timeout does NOT represent the time it takes the other party to acknowledge the packet. RockBLOCK will acknowledge
# the packet locally because it is assumed to be a reliable link.
SAT_TX_TIMEOUT = 10


class RockBlockHandler(Thread):
    def __init__(self):
        self.proto = ISBDPacketProtocol()
        self.running = False

    def run(self):
        self.running = True
        while self.running:
            self.proto.message_check()

    def write_packet(self, packet: Packet):
        self.proto.write_packet(packet)

    def read_packet(self):
        return self.proto.read_packet()

    def close(self):
        self.stop()

    def stop(self):
        self.running = False
        self.join()


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
            # Packet was accepted by RockBLOCK - we can assume ISBD is a reliable transfer service so acknowledge it
            ack = Packet(ptype=MsgType.SACK, pid=packet.id, cmode=CommMode.SATELLITE)
            with self.received_packets_l:
                self.received_packets.append(ack)

    def read_packet(self):
        if len(self.received_packets) > 0:
            with self.received_packets_l:
                return self.received_packets.pop(0)
        return None
