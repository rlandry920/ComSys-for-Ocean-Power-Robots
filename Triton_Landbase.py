import cv2
import logging
import numpy as np
from CommSys.Packet import Packet, MsgType
from CommSys.CommHandler import CommHandler
from SensorLib.FPS import FPS

fps = FPS()

logging.basicConfig(filename='landbase.log',
                    level=logging.DEBUG,
                    format='%(asctime)s | %(funcName)s | %(levelname)s | %(message)s')

logger = logging.getLogger(__name__)

display_resolution = (240, 120)

def main():
    logger.info("Landbase starting...")
    comm_handler = CommHandler()
    comm_handler.start()
    print("Connection with robot established!")
    fps.start()
    try:
        while True:
            if comm_handler.recv_flag():
                packet = comm_handler.recv_packet()
                digest_packet(packet)
    except KeyboardInterrupt:
        pass
    finally:
        logging.info("Landbase stopping...")
        comm_handler.stop()
        fps.stop()

        logger.info("[INFO] elasped time: {:.2f}".format(fps.elapsed()))
        logger.info("[INFO] approx. FPS: {:.2f}".format(fps.fps()))


def digest_packet(packet: Packet):
    if packet is None:
        return
    elif packet.type == MsgType.TEXT:
        print(packet.data.decode('utf-8'))
    elif packet.type == MsgType.IMAGE:
        decode_word = np.frombuffer(packet.data, dtype=np.uint8)
        frame = cv2.resize(cv2.imdecode(decode_word, cv2.IMREAD_COLOR), display_resolution)
        cv2.imshow('frame', frame)
        cv2.waitKey(1)
        fps.update()
    else:
        print(f'Received packet (ID: {packet.id} of type {packet.type})')


if __name__ == "__main__":
    main()
