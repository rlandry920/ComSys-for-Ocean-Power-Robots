import queue
from CommSys.CommMode import CommMode
from CommSys.Packet import Packet, MsgType, NUM_ID_BYTES, SYNC_WORD, MIN_PACKET_SIZE, PacketError
from CommSys.SerialHandler import SerialHandler, RADIO_TX_TIMEOUT
from CommSys import EmailHandler
from CommSys.RockBlockHandler import RockBlockHandler, SAT_TX_TIMEOUT
from threading import Thread, Lock
import logging
import time
import copy
from enum import Enum
from queue import Queue

# CommHandler.py
#
# Last updated: 04/26/2022 | Primary Contact: Michael Fuhrer, mfuhrer@vt.edu
# Contains the primary implementation of our communication system. It uses selective-repeat ARQ and multi-threading to
# handle sending and receiving data over multiple channels asynchronously. It also contains our handshake protocols to
# allow the robot and landbase to coordinate which channel to use.
#
# TODO List:
# - Verify handshake behavior over satellite
# - Reduce computation overhead & latency
# - Add dynamic tx_timeout
# - Add CACK behavior

logger = logging.getLogger(__name__)

HANDSHAKE_TIMEOUT = 3600  # 1 hr expiration time
RX_CACK_DELAY = 0.100  # Unused
WINDOW_SIZE = 8
MAX_ID = pow(2, (8 * NUM_ID_BYTES))

debug_string = b''

username = "iridium.yanglab@gmail.com"
password = "durham365"

ALLOWED_SAT_MSG_TYPES = [MsgType.HANDSHAKE, MsgType.HANDSHAKE_RESPONSE, MsgType.TEXT, MsgType.INFO, MsgType.ERROR,
                         MsgType.GPS_DATA, MsgType.GPS_CMD, MsgType.HEARTBEAT_REQ, MsgType.HEARTBEAT,
                         MsgType.COMM_CHANGE]


class CommHandler():
    def __init__(self, window_size=WINDOW_SIZE, ordered_delivery=True, handshake_timeout=HANDSHAKE_TIMEOUT,
                 landbase=True):
        super(CommHandler, self).__init__()
        # Configuration
        self.landbase = landbase
        self.window_size = window_size
        # Determines whether images / motor commands are sent and received using RDT
        self.reliable_img = False
        self.reliable_mtr_cmd = False
        # Determines whether selective repeat protocol delivers packets
        self.ordered_delivery = ordered_delivery
        # to the application in order
        self.handshake_timeout = handshake_timeout

        # Selective Repeat Flow-Control Values
        self.tx_base = 0
        self.tx_next_seq_num = 0
        # Queue of sent, un-ack'd packets
        self.tx_window = [None] * self.window_size
        self.tx_win_lock = Lock()

        self.rx_base = 0
        # Queue of received, buffered packets to send to application
        self.rx_window = [None] * self.window_size

        # Robot Interface Members
        self.in_queue = Queue()
        self.out_queue = Queue()

        # Serial/Radio Members
        self.radio = SerialHandler()

        # Satellite Members
        # if landbase:
        #     self.satellite = EmailHandler(username, password)
        # else:
        #     self.satellite = RockBlockHandler()
        self.satellite = dummySatDevice()  # DEBUG

        self.comm_dict = {CommMode.RADIO: self.radio,
                          CommMode.SATELLITE: self.satellite}

        # Threading members
        self.t_in = None
        self.t_out = None
        self.stopped = True

        self.comm_mode = None

    # Append packet to egress queue. Blocking until packet is successfully added.
    def send_packet(self, packet: Packet):
        # TODO expand bad context conditions, e.g. can't send normal packets when in handshake mode
        if packet.cmode is None:
            packet.cmode = self.comm_mode

        if packet.cmode == CommMode.SATELLITE and packet.type not in ALLOWED_SAT_MSG_TYPES:
            raise CommSysError("Invalid packet type for satellite communication!")
            return

        # Waits here until able to place item in queue
        self.out_queue.put(packet, True, None)

    # Pops and returns the oldest packet in the ingress queue, returns none if no available item in queue
    def recv_packet(self):
        try:
            return self.in_queue.get(False)
        except queue.Empty:
            return None

    # Returns True if there is a packet in the ingress queue, returns False otherwise.
    def recv_flag(self):
        return not self.in_queue.empty()

    # Starts the CommHandler and its threads in the specified CommMode.
    def start(self, mode=CommMode.HANDSHAKE):
        if not self.stopped:
            return  # already started

        self.t_in = Thread(target=self.__update_ingress)
        self.t_out = Thread(target=self.__update_egress)

        self.radio.start()
        self.satellite.start()

        self.run()
        self.reboot(mode)

    # Clears tx/rx windows & egress/ingress queues. Changes CommMode to that specified. Raises exception if passed
    # CommMode.HANDSHAKE and handshake_timout seconds pass without a connection.
    def reboot(self, mode):
        self.comm_mode = mode
        self.tx_base = 0
        self.rx_base = 0
        self.__reset_windows()
        self.in_queue = Queue()
        self.out_queue = Queue()
        if mode == CommMode.HANDSHAKE:
            if not self.landbase:
                handshake_p1 = Packet(ptype=MsgType.HANDSHAKE, cmode=CommMode.RADIO)
                handshake_p2 = Packet(ptype=MsgType.HANDSHAKE, cmode=CommMode.SATELLITE)
                self.send_packet(handshake_p1)
                self.send_packet(handshake_p2)
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

    # Overrides Thread parent function.
    def run(self):
        logger.info("CommHandler starting.")
        self.stopped = False
        self.t_in.start()
        self.t_out.start()

    # Stops and joins all relevant threads.
    def stop(self):
        if not self.stopped:
            self.stopped = True
            self.t_in.join()
            self.t_out.join()
            self.radio.close()
            self.satellite.close()

        logger.info("CommHandler closed.")

    # Thread target which continuously 1) pops packets from egress queue and adds them to the tx_window whenever there
    # is room, and 2) resends any expired packets in tx_window
    def __update_egress(self):
        logger.debug("Update egress thread started.")
        while not self.stopped:
            self.__resend_expired_packets()

            try:
                send_packet = self.out_queue.get(False)
            except queue.Empty:
                continue

            logger.debug(f"send_packet: {send_packet.type} {send_packet.cmode}")
            if self.comm_dict[send_packet.cmode].reliable or \
                    (send_packet.type == MsgType.IMAGE and not self.reliable_img) or \
                    (send_packet.type == MsgType.MTR_CMD and not self.reliable_mtr_cmd):
                self.__tx_simple(send_packet)
            else:
                if (self.tx_next_seq_num - self.tx_base) % MAX_ID < self.window_size:
                    # Slot available in tx_window, add packet
                    try:
                        self.__tx_rdt(send_packet)
                    except FlowControlError as e:
                        logger.warning(str(e))
                else:
                    # No available space in tx_window - re-add packet to out_queue w/ warning
                    try:
                        self.out_queue.put_nowait(send_packet)
                        logger.warning("No room in tx window. Moved packet to back of queue.")
                    except queue.Full:
                        logger.warning("No room in tx window. Dropped packet because queue was full!")

        logger.debug("Update egress thread exiting.")
        # Cleanup transmission window upon exiting
        self.__shift_tx_window(self.window_size)

    # Thread target which continuously reads relevant interfaces and appends any found packets to ingress queue.
    def __update_ingress(self):
        logger.debug("Update ingress thread started.")
        while not self.stopped:
            try:
                self.__read()
            except FlowControlError as e:
                logger.warning(str(e))
        logger.debug("Update ingress thread exiting.")

    # Send packet to link-layer classes w/o RDT handling
    def __tx_simple(self, packet: Packet):
        packet.checksum = packet.calc_checksum()
        logger.debug(f"Simple transmission of packet (Type: {packet.type})")
        self.__write(packet)

    # Add packet to tx_window and increment sequence number
    def __tx_rdt(self, packet: Packet):
        packet.id = self.tx_next_seq_num  # Set packet ID
        # Recalculate packet's checksum w/ new ID
        packet.checksum = packet.calc_checksum()

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

    # Deliver packet directly to ingress queue if packet is valid.
    def __rx_simple(self, packet: Packet):
        # Ensure checksum and deliver directly to application
        if packet.checksum != packet.calc_checksum():
            logger.debug(
                f"Dropped packet (Type: {packet.type}) due to invalid checksum.")
            return  # Drop packet

        self.in_queue.put(packet)

    # Add packet to rx_window, handle ack'ing behavior
    def __rx_rdt(self, packet: Packet):
        # Ensure checksum matches expectation
        if packet.checksum != packet.calc_checksum():
            logger.debug(
                f"Dropped packet (ID: {packet.id}) due to invalid checksum.")
            return  # Drop packet

        # Check if received packet was an ACK packet
        if packet.type == MsgType.SACK or packet.type == MsgType.CACK or packet.type == MsgType.DACK:
            logger.debug(
                f"Received acknowledgement (ID: {packet.id} Type: {packet.type})")
            self.__handle_ack(packet)
            return

        # Application Packets handled below, e.g. TEXT, IMAGE, etc.
        if packet.id == self.rx_base:
            # Packet is in-order, deliver directly to application alongside any packets waiting in buffer
            logger.debug(
                f"Received packet (ID: {packet.id} Type: {packet.type})")
            self.rx_window[0] = packet
            self.__deliver_rx_window()
            # Cumulative ACK handler
            self.__send_ack(packet)  # TODO: replace with CACK handler

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
            self.__send_ack(packet)

        else:
            # Received packet outside of reception window, send duplicate ack if within past 20 packets
            if (packet.id - self.rx_base) % MAX_ID > -WINDOW_SIZE:
                logger.debug(f"Packet received (ID: {packet.id}) outside expected window,"
                             f" but within it's reason.")
                self.__send_ack(packet, MsgType.DACK)
            else:
                logger.debug(f"Packet received (ID: {packet.id}) outside expected window,"
                             f" but seems outside reason - dropping")
                return

    # Used to interpret incoming ACK packets and acknowledge packets in own tx_window
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

    # Sends an acknowledgement with specified type (if specified) using the pid from the provided packet.
    def __send_ack(self, packet, ack_type=MsgType.SACK):
        pid = packet.id
        logger.debug(
            f"Sending acknowledgement for packet (ID: {pid}) with {ack_type}.")
        ack_packet = Packet(ptype=ack_type, pid=pid, cmode=packet.cmode)
        self.__tx_simple(ack_packet)

    # Handles logic surrounding reception of handshakes and handshake responses. Either type will change the CommMode
    # to the medium the handshake (response) was received over. Will send a handshake response if packet is a handshake.
    def __recv_handshake(self, packet: Packet):
        if packet.type == MsgType.HANDSHAKE:
            logger.debug(f'Received handshake over {packet.cmode}')
            if not (self.comm_mode == CommMode.RADIO and packet.cmode == CommMode.SATELLITE):
                self.comm_mode = packet.cmode
            # Put handshake in in_queue so app knows connection was made
            self.in_queue.put(packet)
            # Update transmission bases to sync w/ client
            self.tx_base = packet.id
            self.rx_base = (packet.id + 1 % MAX_ID)
            self.__reset_windows()
            # Send unreliable handshake response back to other party
            response = Packet(ptype=MsgType.HANDSHAKE_RESPONSE, pid=packet.id, cmode=packet.cmode, calc_checksum=True)
            self.__write(response)
        elif packet.type == MsgType.HANDSHAKE_RESPONSE:
            try:
                self.__acknowledge_tx_pid(packet.id)
                logger.debug(
                    f'Received acknowledgement over {packet.cmode} for handshake (ID: {packet.id})')
                if not (self.comm_mode == CommMode.RADIO and packet.cmode == CommMode.SATELLITE):
                    logger.info(f"Setting comm_mode to {packet.cmode}")
                    self.comm_mode = packet.cmode
                # Put handshake in in_queue so app knows connection was made
                self.in_queue.put(packet)
                # Update transmission bases to sync w/ client
                self.tx_base = (packet.id + 1 % MAX_ID)
                self.rx_base = packet.id
                self.__reset_windows()
                # Put handshake in in_queue so app knows connection was made
                self.in_queue.put(packet)
            except FlowControlError:
                logger.debug(f'Received handshake response over {packet.cmode} for handshake (ID: {packet.id})'
                             f', but ID was incorrect.')
        logger.debug(f"CommMode is now: {self.comm_mode}")

    # Finds and resends any expired packets in tx_window
    def __resend_expired_packets(self):
        t = time.time()
        with self.tx_win_lock:
            expired_packets = list(filter(lambda x:
                                          x is not None
                                          and type(x) != str
                                          and ((t - x["timestamp"]) > RADIO_TX_TIMEOUT),
                                          self.tx_window))
            for packet_tuple in expired_packets:
                packet = packet_tuple["packet"]
                logger.debug(f"Retransmitting packet (ID: {packet.id}).")
                self.__write(packet)
                packet_tuple["timestamp"] = t

    # Retrieves packets from all relevant channels and processes them according to their type and channel
    def __read(self):
        new_packets = []
        radio_packet = self.radio.read_packet()
        if radio_packet is not None:
            new_packets.append(radio_packet)

        if self.comm_mode == CommMode.SATELLITE or self.comm_mode == CommMode.HANDSHAKE:
            if type(self.satellite) == EmailHandler:
                # Handle multiple read packets
                pass
            elif type(self.satellite) == RockBlockHandler:
                # Handle single read packet
                sat_packet = self.satellite.read_packet()
                if sat_packet is not None:
                    new_packets.append(sat_packet)

        for packet in new_packets:
            packet: Packet
            logger.debug(f"Read packet: {packet.type} {packet.cmode}")
            if packet.type == MsgType.HANDSHAKE or packet.type == MsgType.HANDSHAKE_RESPONSE:
                self.__recv_handshake(packet)

            elif (self.comm_dict[packet.cmode].reliable or \
                    (packet.type == MsgType.IMAGE and not self.reliable_img) or \
                    (packet.type == MsgType.MTR_CMD and not self.reliable_mtr_cmd)) and \
                    self.comm_mode != CommMode.HANDSHAKE:
                self.__rx_simple(packet)

            elif self.comm_mode != CommMode.HANDSHAKE:
                self.__rx_rdt(packet)

    # Write to device based on comm_mode specified in packet object
    def __write(self, packet: Packet):
        comm_mode = packet.cmode
        if comm_mode == CommMode.SATELLITE:
            self.satellite.write_packet(packet)
        elif comm_mode == CommMode.RADIO:
            self.radio.write_packet(packet)

    # Marks own packet with provided pid as acknowledged. Slides tx_window if pid is at the base of the window.
    def __acknowledge_tx_pid(self, pid):
        index = (pid - self.tx_base) % MAX_ID
        # Check to ensure that a valid ack_id was recv'd
        if index < 0 or index >= self.window_size:
            raise FlowControlError(f'Received ACK_ID (ID: {self.tx_base + index}) outside of transmission window. '
                                   f'Expected IDs {self.tx_base}-{self.tx_next_seq_num}')

        if self.tx_window[index] == "ACK":
            raise FlowControlError(
                f'Attempted to acknowledge own already ack\'d packet (ID: {self.tx_base + index}).')

        if self.tx_window[index] is None:
            raise FlowControlError(
                f'Attempted to acknowledge own unsent packet ({self.tx_base + index}).')

        logger.debug(
            f"Marking own packet (ID: {self.tx_base + index}) as acknowledged.")
        with self.tx_win_lock:
            # Replace with ACK
            self.tx_window[index] = "ACK"

    # Performs a zero-shift left 'amount' times on the tx_window
    def __shift_tx_window(self, amount):
        # Places a ceiling on how much the window can shift
        shift_amount = min(self.window_size, amount)

        with self.tx_win_lock:
            self.tx_base = (self.tx_base + shift_amount) % MAX_ID
            self.tx_window = self.tx_window[shift_amount:] + \
                             [None] * shift_amount

    # Delivers in-order packets to application and increments rx_base accordingly
    def __deliver_rx_window(self):
        none_index = self.rx_window.index(
            None) if None in self.rx_window else -1
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

        # Filter needed in case of "DEL" placeholder
        to_deliver = list(filter(lambda x: type(x) == Packet, to_deliver))
        for item in to_deliver:
            self.in_queue.put(item)

    # Clears both rx & tx windows.
    def __reset_windows(self):
        self.tx_next_seq_num = self.tx_base
        self.tx_window = [None] * self.window_size
        self.rx_window = [None] * self.window_size

    # Gives a string interpretation of the tx_window. Helpful for logging / debugging.
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

# Debugging function, depreciated.
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

# Debugging stand-in for actual satellite modem
class dummySatDevice():
    def __init__(self):
        self.reliable = True

    def start(self): print("DummySatDevice Started")

    def close(self): print("DummySatDevice Closed")

    def write_packet(self, packet: Packet): print(
        f"DummySatDevice Sending Packet: (ID: {packet.id}, MsgType: {packet.type})")

    def read_packet(self): print(f"DummySatDevice Received nothing!")
