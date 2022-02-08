import logging
from threading import Thread, Lock
from CommSys.Packet import Packet, MIN_PACKET_SIZE
import serial

logger = logging.getLogger(__name__)  # gets logger of highest-level script


class CommHandler:
    def __init__(self):
        self.radio = serial.Serial("/dev/ttyAMA0", baudrate=57600, rtscts=True)
        self.sat = None

        self.use_radio = True

        self.in_queue = []
        self.in_lock = Lock()
        self.out_queue = []
        self.out_lock = Lock()

        self.t_in = Thread(target=self.update_ingress, args=())
        self.t_out = Thread(target=self.update_egress, args=())

        self.stopped = True

    def get_ingress_tuple(self):
        return self.in_queue, self.in_lock

    def get_egress_tuple(self):
        return self.out_queue, self.out_lock

    # Starts relevant communication threads.
    def start(self):
        logger.info("CommHandler starting...")
        self.stopped = False
        self.t_in.start()
        self.t_out.start()

    # Blocking stop to all ongoing communication threads. Waits for threads to safely exit before continuing.
    def stop(self):
        logger.info("CommHandler stopping...")
        self.stopped = True
        # Wait for threads to finish
        self.t_in.join()
        self.t_out.join()

    # Restarts (if applicable) any ongoing communication threads and changes communication mode to specified
    # argument. If no argument is specified, comm. method will swap.
    def change_comm_method(self, use_radio=None):
        if use_radio is None:
            use_radio = ~self.use_radio

        if not self.stopped:
            self.stop()
            self.use_radio = use_radio
            self.start()

        else:
            self.use_radio = use_radio

    def update_ingress(self):
        logger.info("CommHandler Ingress Thread started...")
        if self.use_radio:
            recv_data = b''
            while True:
                if self.stopped:
                    if len(recv_data) > 0:
                        logger.warning("Ingress: Dropping unhandled ingress radio data due to abrupt stop.")
                    return

                # Check serial line for new data
                recv_data += self.radio.read()
                logger.debug(f'Ingress: recv_data: {recv_data}')

                if len(recv_data) < MIN_PACKET_SIZE:
                    # Less than three bytes on datastream, not enough for a packet
                    logger.debug("Not enough bytes in recv_data to operate upon")
                else:
                    expected_length = int.from_bytes(recv_data[1:3], byteorder='big') + MIN_PACKET_SIZE

                    if len(recv_data) >= expected_length:
                        # Generate Packet from and remove relevant data from recv_data
                        packet = Packet.from_binary(recv_data[0:expected_length])
                        with self.in_lock:
                            self.in_queue.append(packet)
                        recv_data = recv_data[expected_length:]
                    else:
                        logger.debug(f'Ingress: Cannot create packet. '
                                     f'Expected length = {expected_length}, data length = {len(recv_data)}')

        else:
            # TODO
            return

    def update_egress(self):
        logger.info("CommHandler Egress Thread started...")
        if self.use_radio:
            while True:
                if self.stopped:
                    return

                if len(self.out_queue) == 0:
                    logger.debug("No outgoing packets in queue.")
                else:
                    logger.debug("CommHandler found packet in egress queue, handling...")
                    # Pop the oldest item from the queue and send its binary word over radio
                    with self.out_lock:
                        packet = self.out_queue.pop()

                    self.radio.write(packet.to_binary())
                    logger.debug(f'Egress: Sending {packet.m_type} packet')

        else:
            # TODO
            return
