import queue

from CommSys.Packet import Packet, MsgType, NUM_ID_BYTES
from CommSys.RFD900 import RFD900
from threading import Thread
from multiprocessing import Process, Lock, Queue
from threading import Timer
import logging
import time
from enum import Enum

# TODO Test ****THOROUGHLY****
#   - prepend '__' to hidden functions once done testing

logger = logging.getLogger(__name__)

HANDSHAKE_TIMEOUT = 60
TX_TIMEOUT = 3
RX_CACK_DELAY = 0.100
WINDOW_SIZE = 8
MAX_ID = pow(2, (8 * NUM_ID_BYTES))
ORD_DELIVERY = True  # Determines whether the Selective Repeat Protocol must deliver packets to app. in order of ID


class CommMode(Enum):
    HANDSHAKE = 0,
    RADIO = 1,
    SATELLITE = 2,
    DEBUG = 3


class CommHandler(Process):
    def __init__(self):
        super(CommHandler, self).__init__()
        # Selective Repeat Flow-Control Values
        self.tx_base = 0
        self.tx_next_seq_num = 0
        self.tx_window = [None] * WINDOW_SIZE  # Queue of sent, un-ack'd packets # Todo TX window has to become a Queue

        self.rx_base = 0
        self.rx_window = [None] * WINDOW_SIZE  # Queue of received, buffered packets to send to application

        # Robot Interface Members
        self.in_queue = Queue()
        self.out_queue = Queue()

        # Serial/Radio Members
        self.radio = RFD900()
        self.radio_tx_lock = Lock()  # Lock to prevent RX thread from sending ACKs when TX thread is writing

        # Satellite Members
        self.satellite = None

        # Threading members
        self.t_in = Thread(target=self.__update_ingress)
        self.t_out = Thread(target=self.__update_egress)
        self.stopped = True

        self.comm_mode = None

    # Add packet to outgoing queue
    def send_packet(self, packet: Packet):
        self.out_queue.put(packet, True, None)  # Waits here until able to place item in queue

    # Pops and returns the oldest packet in the incoming queue, returns none if no available item in queue
    def recv_packet(self):
        try:
            return self.in_queue.get_nowait()
        except queue.Empty:
            return None

    def recv_flag(self):
        return not self.in_queue.empty()

    def start(self, mode=CommMode.HANDSHAKE):
        self.comm_mode = mode
        Process.start(self)
        if mode == CommMode.HANDSHAKE:
            # If in handshake mode, try to establish connection within timeout period
            handshake_expire = time.time() + HANDSHAKE_TIMEOUT
            # Incoming handshake will be forwarded to in_queue
            while self.in_queue.empty() and time.time() < handshake_expire:
                time.sleep(1)
            if self.in_queue.empty():
                raise CommSysError(f'Failed to establish connection!')
            else:
                logger.info("Successfully performed handshake.")

    def run(self):
        logger.info("CommHandler starting.")
        self.stopped = False
        self.change_mode(self.comm_mode)  # Used to start up radio
        self.t_in.start()
        self.t_out.start()
        # Continue process until both threads are finished
        while not self.stopped:
            pass
        self.t_in.join()
        self.t_out.join()
        logger.info("CommHandler closed.")

    def stop(self):
        if not self.stopped:
            self.stopped = True

    def change_mode(self, mode: CommMode):
        if mode == CommMode.HANDSHAKE:
            # Both radio and satellite should be on
            self.radio.start()
        elif mode == CommMode.RADIO:
            # Only radio should be on
            self.radio.start()
        elif mode == CommMode.SATELLITE:
            # Only satellite should be on
            self.radio.stop()
        elif mode == CommMode.DEBUG:
            # No comm device should be on
            self.radio.stop()

        self.comm_mode = mode

    def __update_egress(self):
        logger.debug("Update egress thread started.")
        while not self.stopped:
            if (self.tx_next_seq_num - self.tx_base) % MAX_ID < WINDOW_SIZE:
                # Packet waiting in out_queue and available slot in tx_window, pop packet from queue and transmit
                send_packet = self.out_queue.get(True, None)  # Wait here until item is available

                try:
                    self.__tx_packet(send_packet)
                except FlowControlError as e:
                    logger.warning(str(e))

        self.__shift_tx_window(WINDOW_SIZE)  # Cleanup transmission window

    def __update_ingress(self):
        logger.debug("Update ingress thread started.")
        while not self.stopped:
            try:
                self.__read()
            except FlowControlError as e:
                logger.warning(str(e))

    # Add packet to tx_window and increment sequence number
    def __tx_packet(self, packet: Packet):
        packet.id = self.tx_next_seq_num  # Set packet ID
        packet.checksum = packet.calc_checksum()  # Recalculate packet's checksum w/ new ID

        window_index = (packet.id - self.tx_base) % MAX_ID
        # Check to ensure that there is room in the window
        if window_index < 0 or window_index >= WINDOW_SIZE:
            raise FlowControlError(f'Cannot add packet to full transmission window!')

        if self.tx_window[window_index] is not None:
            raise FlowControlError(f'Attempting to overwrite an item already in transmission window!')

        logger.debug(f"Transmitting packet (ID: {packet.id}, MsgType: {packet.type})")

        self.tx_window[window_index] = {"packet": packet,
                                        "timer": Timer(TX_TIMEOUT, self.__resend_packet, args=[packet.id])}
        self.tx_window[window_index]["timer"].start()
        self.__write(packet)
        self.tx_next_seq_num = (self.tx_next_seq_num + 1) % MAX_ID

    # Add packet to rx_window, handle ack'ing behavior
    def __rx_packet(self, packet: Packet):
        # Ensure checksum matches expectation
        if packet.checksum != packet.calc_checksum():
            logger.debug(f"Dropped packet (ID: {packet.id}) due to invalid checksum.")
            return  # Drop packet

        # Check if received packet was an ACK packet
        if packet.type == MsgType.SACK or packet.type == MsgType.CACK or packet.type == MsgType.DACK:
            self.__handle_ack(packet)
            return

        if packet.id == self.rx_base:
            # Packet is in-order, deliver directly to application alongside any packets waiting in buffer
            self.rx_window[0] = packet
            self.__deliver_rx_window()

            # Cumulative ACK handler
            self.__send_ack(packet.id)  # TODO: replace with CACK handler

        elif (packet.id - WINDOW_SIZE) % MAX_ID < self.rx_base or \
                (self.rx_base < packet.id < (self.rx_base + WINDOW_SIZE)):
            # Packet is out-of-order
            window_index = (packet.id - self.rx_base) % MAX_ID
            if not ORD_DELIVERY:
                # Deliver directly to application, add placeholder to buffer
                logger.debug(f"Received out-of-order packet (ID: {packet.id}, Expected ID: {self.rx_base}). "
                             f"Delivering directly to application regardless.")
                self.in_queue.put(packet, True, None)
                self.rx_window[window_index] = "DEL"  # Delivered tag
            else:
                # Buffer the packet
                logger.debug(f"Received out-of-order packet (ID: {packet.id}, Expected ID: {self.rx_base}). "
                             f"Buffering.")
                self.rx_window[window_index] = packet
            # Send selective ACK
            self.__send_ack(packet.id)

        else:
            # Received packet outside of reception window, send duplicate ack
            self.__send_ack(packet.id, MsgType.DACK)

    def __recv_handshake(self, packet: Packet, mode: CommMode):
        if packet.type != MsgType.HANDSHAKE or packet.checksum != packet.calc_checksum():
            return  # Drop all invalid handshake packets

        logger.info(f"Handshake received over {mode}.")
        self.comm_mode = mode  # Switch comm_mode to the medium handshake was received over
        self.in_queue.put(packet, True, None)
        # If handshake already exists in tx_window, acknowledge it
        for i in range(WINDOW_SIZE):
            if self.tx_window[i] is not None and self.tx_window[i] != "ACK":
                if self.tx_window[i]["packet"].type == MsgType.HANDSHAKE:
                    self.__acknowledge_tx_index(i)
                    return
            else:
                break
        # Otherwise create and transmit a return handshake
        logger.info("Returning handshake.")
        handshake_packet = Packet(MsgType.HANDSHAKE, 0, b'')
        self.__tx_packet(handshake_packet)

    # Used to interpret incoming ACK packets
    def __handle_ack(self, packet: Packet):
        window_index = (packet.id - self.tx_base) % MAX_ID

        # Acknowledgement of base packet - same behavior regardless of ack type
        if packet.id == self.tx_base:
            self.__acknowledge_tx_index(window_index)
            # Keep shifting tx_window until its base is an unacknowledged packet / None
            while self.tx_window[0] == "ACK":
                self.__shift_tx_window(1)

        # Out-of-Order Selective acknowledgment
        elif packet.type == MsgType.SACK or packet.type == MsgType.DACK:
            self.__acknowledge_tx_index(window_index)

        # Cumulative acknowledgement
        elif packet.type == MsgType.CACK:
            self.__shift_tx_window(window_index + 1)

    def __send_ack(self, pid, ack_type=MsgType.SACK):
        logger.debug(f"Acknowledging packet (ID: {pid}) with {ack_type}.")
        ack_packet = Packet(ptype=ack_type, pid=pid)
        self.__write(ack_packet)

    def __resend_packet(self, pid):
        try:
            window_index = (pid - self.tx_base) % MAX_ID
            # Make sure packet is in tx_window and isn't already ACK'd
            if window_index < 0 or window_index >= WINDOW_SIZE or self.tx_window[window_index] is None:
                raise FlowControlError(f"Tried to resend packet ({pid}) not in transmission window!")

            if type(self.tx_window[window_index]) == str:
                raise FlowControlError(f"Tried to resend packet ({pid}) that has already been acknowledged")

            logger.debug(f"Retransmitting packet (ID: {pid}).")
            self.__write(self.tx_window[window_index]["packet"])
            self.tx_window[window_index]["timer"] = Timer(TX_TIMEOUT, self.__resend_packet, args=[pid])
            self.tx_window[window_index]["timer"].start()
        except FlowControlError as e:
            logger.warning(str(e))

    def __read(self):
        if self.comm_mode == CommMode.SATELLITE:
            # TODO Satellite
            pass
        elif self.comm_mode == CommMode.RADIO:
            # Radio Communication
            new_packet = self.radio.read()
            if new_packet is not None:
                self.__rx_packet(new_packet)
        elif self.comm_mode == CommMode.HANDSHAKE:
            # Handshake mode, accept new packets from either interface
            new_packet = self.radio.read()
            if new_packet is not None:
                self.__recv_handshake(new_packet, CommMode.RADIO)
            # TODO Satellite

    def __write(self, packet: Packet):
        if self.comm_mode == CommMode.SATELLITE:
            # TODO Satellite
            pass
        elif self.comm_mode == CommMode.RADIO:
            # Radio Communication
            with self.radio_tx_lock:
                self.radio.write(packet)

        elif self.comm_mode == CommMode.HANDSHAKE:
            # Write handshake packet over both mediums
            with self.radio_tx_lock:
                self.radio.write(packet)
            # TODO Satellite

        elif self.comm_mode == CommMode.DEBUG:
            # Debug
            print(f'Writing packet {packet.id}, {packet.type}: {packet.data[0:32]}', end='')
            if packet.length > 32:
                print('...')
            else:
                print('')

    def __acknowledge_tx_index(self, index):
        # Check to ensure that a valid ack_id was recv'd
        if index < 0 or index >= WINDOW_SIZE:
            raise FlowControlError(f'Received ACK_ID (ID: {self.tx_base + index}) outside of transmission window. '
                                   f'Expected IDs {self.tx_base}-{self.tx_next_seq_num}')

        if self.tx_window[index] == "ACK":
            raise FlowControlError(f'Duplicate acknowledged received for packet (ID: {self.tx_base + index})')

        if self.tx_window[index] is None:
            raise FlowControlError(f'Acknowledgment for unsent packet ({self.tx_base + index}) received.')

        logger.debug(f"Acknowledgement received for packet (ID: {self.tx_base + index}).")

        # Turn off resend timer
        self.tx_window[index]["timer"].cancel()
        # Replace with ACK
        self.tx_window[index] = "ACK"

    # Performs a zero-shift left 'amount' times on the tx_window
    def __shift_tx_window(self, amount):
        shift_amount = min(WINDOW_SIZE, amount)  # Places a ceiling on how much the window can shift
        # Cancel all timers in shift range
        shift_range = list(filter(lambda x: x is not None and x != "ACK", self.tx_window[0:shift_amount]))
        for pair in shift_range:
            pair["timer"].cancel()

        self.tx_base = (self.tx_base + shift_amount) % MAX_ID
        self.tx_window = self.tx_window[shift_amount:] + [None] * shift_amount

    # Delivers in-order packets to application and increments rx_base accordingly
    def __deliver_rx_window(self):
        none_index = self.rx_window.index(None)
        if none_index >= 0:
            to_deliver = self.rx_window[0:none_index]
            self.rx_window = self.rx_window[none_index:] + [None] * none_index
            self.rx_base = (self.rx_base + none_index) % MAX_ID
        else:
            to_deliver = self.rx_window
            self.rx_window = [None] * WINDOW_SIZE
            self.rx_base = (self.rx_base + WINDOW_SIZE) % MAX_ID

        to_deliver = list(filter(lambda x: type(x) == Packet, to_deliver))  # Filter needed in case of "DEL" placeholder
        for item in to_deliver:
            self.in_queue.put(item, True, None)


class CommSysError(Exception):
    pass


class FlowControlError(CommSysError):
    pass
