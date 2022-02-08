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


def main():
    logger.info("Landbase starting...")
    comm_handler = CommHandler()
    in_queue, in_lock = comm_handler.get_ingress_tuple()
    comm_handler.start()
    fps.start()
    logger.info("Landbase started!")
    try:
        while True:
            if len(in_queue) > 0:
                packet = None
                with in_lock:
                    packet = in_queue.pop()
                digest_img_packet(packet)
    except KeyboardInterrupt:
        pass
    finally:
        logging.info("Landbase stopping...")
        comm_handler.stop()
        fps.stop()

        logger.info("[INFO] elasped time: {:.2f}".format(fps.elapsed()))
        logger.info("[INFO] approx. FPS: {:.2f}".format(fps.fps()))


def digest_img_packet(packet: Packet):
    if packet.m_type != MsgType.IMAGE:
        return

    decode_word = np.fromstring(packet.m_payload, dtype=np.uint8)
    frame = cv2.imdecode(packet.m_payload, cv2.IMREAD_COLOR)
    cv2.imshow('frame', frame)
    cv2.waitKey(1)

    fps.update()


if __name__ == "__main__":
    main()
