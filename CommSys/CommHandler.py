import queue

from CommSys.Packet import Packet, MsgType, NUM_ID_BYTES, SYNC_WORD, MIN_PACKET_SIZE, PacketError
from CommSys.SerialHandler import PacketReaderThread
from threading import Thread, Lock
import logging
import time
import copy
from enum import Enum
from queue import Queue

# TODO improve acking items outside of window
# TODO add handshake handle when not in handshake mode
# TODO add dynamic tx_timeout
# TODO add CACK behavior (low priority atm)

logger = logging.getLogger(__name__)

HANDSHAKE_TIMEOUT = 3600  # 1 hr expiration time
TX_TIMEOUT = 2.5
RX_CACK_DELAY = 0.100
WINDOW_SIZE = 8
MAX_ID = pow(2, (8 * NUM_ID_BYTES))

debug_string = b''


class CommMode(Enum):
    HANDSHAKE = 0,
    RADIO = 1,
    SATELLITE = 2,
    DEBUG = 3


class CommHandler():
    def __init__(self, window_size=WINDOW_SIZE, reliable_img=True, ordered_delivery=True,
                 tx_timeout=TX_TIMEOUT, handshake_timeout=HANDSHAKE_TIMEOUT, landbase=True):
        super(CommHandler, self).__init__()
        # Configuration
        self.window_size = window_size
        self.reliable_img = reliable_img  # Determines whether images are sent and received using RDT
        self.ordered_delivery = ordered_delivery  # Determines whether selective repeat protocol delivers packets
        # to the application in order
        self.tx_timeout = tx_timeout
        self.handshake_timeout = handshake_timeout

        # Selective Repeat Flow-Control Values
        self.tx_base = 0
        self.tx_next_seq_num = 0
        self.tx_window = [None] * self.window_size  # Queue of sent, un-ack'd packets
        self.tx_win_lock = Lock()

        self.rx_base = 0
        self.rx_window = [None] * self.window_size  # Queue of received, buffered packets to send to application

        # Robot Interface Members
        self.in_queue = Queue()
        self.out_queue = Queue()

        # Serial/Radio Members
        self.radio = PacketReaderThread()

        # Satellite Members
        if landbase:
            self.satellite = EmailHandler()
        else:
            self.satellite = RockBlockHandler()

        # Threading members
        self.t_in = None
        self.t_out = None
        self.stopped = True

        self.comm_mode = None

    # Add packet to outgoing queue
    def send_packet(self, packet: Packet):
        self.out_queue.put(packet, True, None)  # Waits here until able to place item in queue

    # Pops and returns the oldest packet in the incoming queue, returns none if no available item in queue
    def recv_packet(self):
        try:
            return self.in_queue.get(False)
        except queue.Empty:
            return None

    def recv_flag(self):
        return not self.in_queue.empty()

    def start(self, mode=CommMode.HANDSHAKE):
        if not self.stopped:
            return  # already started

        self.comm_mode = mode
        self.t_in = Thread(target=self.__update_ingress)
        self.t_out = Thread(target=self.__update_egress)
        self.run()
        if mode == CommMode.HANDSHAKE:
            # If in handshake mode, try to establish connection within timeout period
            handshake_expire = time.time() + HANDSHAKE_TIMEOUT
            # Incoming handshake will be forwarded to in_queue
            while self.in_queue.empty() and time.time() < handshake_expire:
                pass

            if self.in_queue.empty():
                raise CommSysError(f'Failed to establish connection!')
            else:
                logger.info("Successfully performed handshake.")
                self.recv_packet()  # clear handshake packet from queue

    def run(self):
        logger.info("CommHandler starting.")
        self.stopped = False
        self.change_mode(self.comm_mode)  # Used to start up radio
        self.t_in.start()
        self.t_out.start()

    def stop(self):
        if not self.stopped:
            self.stopped = True
            self.t_in.join()
            self.t_out.join()

            if self.comm_mode == CommMode.HANDSHAKE or self.comm_mode == CommMode.RADIO:
                self.radio.close()
        logger.info("CommHandler closed.")

    def change_mode(self, mode: CommMode):
        if mode == CommMode.HANDSHAKE:
            # Both radio and satellite should be on
            self.radio.start()
        elif mode == CommMode.RADIO:
            # Only radio should be on
            self.radio.start()
        elif mode == CommMode.SATELLITE:
            # Only satellite should be on
            self.radio.close()
        elif mode == CommMode.DEBUG:
            # No comm device should be on
            self.radio.close()

        self.comm_mode = mode

    def __update_egress(self):
        logger.debug("Update egress thread started.")
        while not self.stopped:
            self.__resend_expired_packets()
            if (self.tx_next_seq_num - self.tx_base) % MAX_ID < self.window_size:
                # Packet waiting in out_queue and available slot in tx_window, pop packet from queue and transmit
                try:
                    send_packet = self.out_queue.get(False)
                    self.__tx_packet(send_packet)
                except queue.Empty:
                    continue
                except FlowControlError as e:
                    logger.warning(str(e))
        logger.debug("Update egress thread exiting.")
        self.__shift_tx_window(self.window_size)  # Cleanup transmission window upon exiting

    def __update_ingress(self):
        logger.debug("Update ingress thread started.")
        while not self.stopped:
            try:
                self.__read()
            except FlowControlError as e:
                logger.warning(str(e))
        logger.debug("Update ingress thread exiting.")

    # Add packet to tx_window and increment sequence number
    def __tx_packet(self, packet: Packet):
        # Only accept handshake packets while in handshake mode
        if self.comm_mode == CommMode.HANDSHAKE and packet.type != MsgType.HANDSHAKE:
            logger.debug(f'Dropping non-handshake packet while in handshake mode')
            return

        if not self.reliable_img and packet.type == MsgType.IMAGE:
            # Send image packet unreliably
            logger.debug(f"Transmitting unreliable image (Length: {packet.length} Bytes)")
            self.__write(packet)

        else:
            packet.id = self.tx_next_seq_num  # Set packet ID
            packet.checksum = packet.calc_checksum()  # Recalculate packet's checksum w/ new ID

            with self.tx_win_lock:
                window_index = (packet.id - self.tx_base) % MAX_ID

                # Check to ensure that there is room in the window
                if window_index < 0 or window_index >= self.window_size:
                    raise FlowControlError(f'Cannot add packet to full transmission window! '
                                           f'Attempted addition: {packet.type} (ID: {packet.id})')

                if self.tx_window[window_index] is not None:
                    raise FlowControlError(f'Attempting to overwrite an item already in transmission window! '
                                           f'Attempted addition to index {window_index}: {packet.type} (ID: {packet.id})')
                self.tx_window[window_index] = {"packet": copy.deepcopy(packet),
                                                "timestamp": time.time()}

            logger.debug(
                f"Transmitting packet (ID: {packet.id}, MsgType: {packet.type}, Checksum {packet.checksum})")
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
            logger.debug(f"Received acknowledgement (ID: {packet.id} Type: {packet.type})")
            self.__handle_ack(packet)
            return

        # Check if handshake was received
        if packet.type == MsgType.HANDSHAKE:
            self.__recv_handshake(packet)

        # Deliver image packets directly, if applicable
        elif not self.reliable_img and packet.type == MsgType.IMAGE:
            logger.debug(f"Received unreliable image packet, "
                         f"delivering directly to application (Length: {packet.length}).")
            self.in_queue.put(packet)
            return

        # Non-RDT Related Packets
        if packet.id == self.rx_base:
            # Packet is in-order, deliver directly to application alongside any packets waiting in buffer
            logger.debug(f"Received packet (ID: {packet.id} Type: {packet.type})")
            self.rx_window[0] = packet
            self.__deliver_rx_window()
            # Cumulative ACK handler
            self.__send_ack(packet.id)  # TODO: replace with CACK handler

        elif 0 < (packet.id - self.rx_base) % MAX_ID < self.window_size:
            # Packet is out-of-order
            window_index = (packet.id - self.rx_base) % MAX_ID
            if not self.ordered_delivery:
                # Deliver directly to application, add placeholder to buffer
                logger.debug(f"Received out-of-order packet (ID: {packet.id}, Expected ID: {self.rx_base}). "
                             f"Delivering directly to application regardless.")
                self.in_queue.put(packet)
                self.rx_window[window_index] = "DEL"  # Delivered tag
            else:
                # Buffer the packet
                logger.debug(f"Received out-of-order packet (ID: {packet.id}, Expected ID: {self.rx_base}). "
                             f"Buffering.")
                self.rx_window[window_index] = packet
            # Send selective ACK
            self.__send_ack(packet.id)

        else:
            # Received packet outside of reception window, send duplicate ack if within past 20 packets
            # TODO 10 is arbitrary - fix?
            if (packet.id - self.rx_base) % MAX_ID > -10:
                logger.debug(f"Packet received (ID: {packet.id}) outside expected window,"
                             f" but within it's reason - acknowledging")
                self.__send_ack(packet.id, MsgType.DACK)
            else:
                logger.debug(f"Packet received (ID: {packet.id}) outside expected window,"
                             f" but seems outside reason - dropping")
                return

    # Used to interpret incoming ACK packets
    def __handle_ack(self, packet: Packet):
        window_index = (packet.id - self.tx_base) % MAX_ID

        # Selective acknowledgment
        if packet.type == MsgType.SACK or packet.type == MsgType.DACK:
            self.__acknowledge_tx_pid(packet.id)

        # Cumulative acknowledgement
        elif packet.type == MsgType.CACK:
            self.__shift_tx_window(window_index + 1)

        # Keep shifting tx_window until its base is an unacknowledged packet / None
        while self.tx_window[0] == "ACK":
            self.__shift_tx_window(1)

        logger.debug(self.__tx_window_to_str())

    def __send_ack(self, pid, ack_type=MsgType.SACK):
        logger.debug(f"Sending acknowledgement for packet (ID: {pid}) with {ack_type}.")
        ack_packet = Packet(ptype=ack_type, pid=pid)
        self.__write(ack_packet)

    def __recv_handshake(self, packet: Packet, comm_mode: CommMode = None):
        if comm_mode is None:
            comm_mode=self.comm_mode

        if packet.type == MsgType.HANDSHAKE:
            logger.debug(f'Received handshake over {comm_mode}')
            self.__send_ack(packet.id, ack_type=MsgType.SACK)
            self.change_mode(comm_mode)
            self.in_queue.put(packet)  # Put handshake in in_queue so app knows connection was made
            # Update transmission bases to sync w/ client
            self.__reset_windows()
            self.tx_base = packet.id
            self.rx_base = (packet.id + 1 % MAX_ID)
        elif packet.type == MsgType.SACK or packet.type == MsgType.DACK or packet.type == MsgType.CACK:
            try:
                self.__acknowledge_tx_pid(packet.id)
                logger.debug(f'Received acknowledgement over {comm_mode} for handshake (ID: {packet.id})')
                self.change_mode(comm_mode)
                dummy_handshake = Packet(MsgType.HANDSHAKE, pid=packet.id)
                self.in_queue.put(dummy_handshake)  # Put handshake in in_queue so app knows connection was made
            except FlowControlError:
                logger.debug(f'Received acknowledgement over {comm_mode} for handshake (ID: {packet.id})'
                             f', but ID was incorrect.')

    def __resend_expired_packets(self):
        t = time.time()
        with self.tx_win_lock:
            expired_packets = list(filter(lambda x: x is not None
                                                    and type(x) != str
                                                    and (t - x["timestamp"]) > self.tx_timeout, self.tx_window))
            for packet_tuple in expired_packets:
                packet = packet_tuple["packet"]
                logger.debug(f"Retransmitting packet (ID: {packet.id}).")
                self.__write(packet)
                packet_tuple["timestamp"] = t


    def __read(self):
        if self.comm_mode == CommMode.SATELLITE:
            # TODO Satellite
            pass
        elif self.comm_mode == CommMode.RADIO:
            # Radio Communication
            new_packet = self.radio.read_packet()
            if new_packet is not None:
                self.__rx_packet(new_packet)
        elif self.comm_mode == CommMode.HANDSHAKE:
            # Handshake mode, accept new packets from either interface
            new_packet = self.radio.read_packet()
            if new_packet is not None:
                self.__recv_handshake(new_packet, CommMode.RADIO)
            # TODO Satellite
        elif self.comm_mode == CommMode.DEBUG:
            new_packet = read_debug_string()
            if new_packet is not None:
                print(f'----Received packet {new_packet.id}, {new_packet.type}: {new_packet.data[0:32]}', end='')
                self.__rx_packet(new_packet)

    def __write(self, packet: Packet):
        if self.comm_mode == CommMode.SATELLITE:
            # TODO Satellite
            pass
        elif self.comm_mode == CommMode.RADIO:
            # Radio Communication
            self.radio.write_packet(packet)

        elif self.comm_mode == CommMode.HANDSHAKE:
            # Write handshake packet over both mediums
            self.radio.write_packet(packet)
            # TODO Satellite

        elif self.comm_mode == CommMode.DEBUG:
            # Debug
            print(f'----Writing packet {packet.id}, {packet.type}: {packet.data[0:32]}', end='')
            if packet.length > 32:
                print('...')
            else:
                print('')
            # Additional check
            if packet.checksum == packet.calc_checksum():
                # Add packet to debug string
                global debug_string
                debug_string += packet.to_binary()
            else:
                print(f'Unexpected checksum error. '
                      f'Expected check: {packet.checksum} Calc check: {packet.calc_checksum()}')
                print(f'Erroneous packet: ({packet.to_binary()})')

    def __acknowledge_tx_pid(self, pid):
        index = (pid - self.tx_base) % MAX_ID
        # Check to ensure that a valid ack_id was recv'd
        if index < 0 or index >= self.window_size:
            raise FlowControlError(f'Received ACK_ID (ID: {self.tx_base + index}) outside of transmission window. '
                                   f'Expected IDs {self.tx_base}-{self.tx_next_seq_num}')

        if self.tx_window[index] == "ACK":
            raise FlowControlError(f'Attempted to acknowledge own already ack\'d packet (ID: {self.tx_base + index}).')

        if self.tx_window[index] is None:
            raise FlowControlError(f'Attempted to acknowledge own unsent packet ({self.tx_base + index}).')

        logger.debug(f"Marking own packet (ID: {self.tx_base + index}) as acknowledged.")
        with self.tx_win_lock:
            # Replace with ACK
            self.tx_window[index] = "ACK"

    # Performs a zero-shift left 'amount' times on the tx_window
    def __shift_tx_window(self, amount):
        shift_amount = min(self.window_size, amount)  # Places a ceiling on how much the window can shift

        with self.tx_win_lock:
            self.tx_base = (self.tx_base + shift_amount) % MAX_ID
            self.tx_window = self.tx_window[shift_amount:] + [None] * shift_amount

    # Delivers in-order packets to application and increments rx_base accordingly
    def __deliver_rx_window(self):
        none_index = self.rx_window.index(None) if None in self.rx_window else -1
        if none_index >= 0:
            # Deliver up to none_index
            to_deliver = self.rx_window[0:none_index]
            self.rx_window = self.rx_window[none_index:] + [None] * none_index
            self.rx_base = (self.rx_base + none_index) % MAX_ID
        else:
            # Entire window is populated, deliver everything
            to_deliver = self.rx_window
            self.rx_window = [None] * self.window_size
            self.rx_base = (self.rx_base + self.window_size) % MAX_ID

        to_deliver = list(filter(lambda x: type(x) == Packet, to_deliver))  # Filter needed in case of "DEL" placeholder
        for item in to_deliver:
            self.in_queue.put(item)

    def __reset_windows(self):
        self.tx_window = [None]*self.window_size
        self.rx_window = [None]*self.window_size

    def __tx_window_to_str(self):
        list_str = ''
        for item in self.tx_window:
            if item is not None and type(item) != str:
                list_str += f"Packet (ID: {str(item['packet'].id)})"
            else:
                list_str += str(item)
            list_str += ', '
        return list_str


class CommSysError(Exception):
    pass


class FlowControlError(CommSysError):
    pass


def read_debug_string():
    global debug_string
    sync_ind = debug_string.find(SYNC_WORD)
    if sync_ind >= 0:
        # Sync word exists in read buffer, head to it
        if sync_ind > 0:
            print(f"Debugger jumping to found sync word @ {sync_ind}")
            print(f"Debug_string before: {debug_string[0:32]}")
            debug_string = debug_string[sync_ind:]
            print(f"Debug_string after: {debug_string[0:32]}")

        # Try to make a packet from read_buf
        try:
            packet = Packet(data=debug_string)
            if packet.checksum != packet.calc_checksum():
                print(f"Debugger dropped packet (ID: {packet.id}) due to invalid checksum. "
                      f"Expected: {packet.checksum}, Actual: {packet.calc_checksum()}")
                print(f'Packet: {packet.to_binary()}')
                debug_string = debug_string[len(SYNC_WORD):]
                return None
            else:
                debug_string = debug_string[(packet.length + MIN_PACKET_SIZE):]
                return packet

        except PacketError as e:
            print(f"Unhandled PacketError: {str(e)}")
            return None
        except ValueError:
            # Invalid MsgType was given, flush read_buf
            print(f"Debugger dropped packet due to invalid MsgType")
            debug_string = debug_string[len(SYNC_WORD):]
            return None
