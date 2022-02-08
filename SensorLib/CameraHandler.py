import logging
from threading import Thread, Lock
import numpy as np
from CommSys.Packet import Packet, MsgType
import cv2
from SensorLib.USBCameraStream import USBCameraStream

desired_resolution = (240, 180)

logger = logging.getLogger(__name__)  # gets logger of highest-level script


class CameraHandler:
    def __init__(self, egress_tuple):
        self.queue = egress_tuple[0]
        self.lock = egress_tuple[1]
        self.camera = USBCameraStream()
        self.stopped = True

    def start(self):
        logger.info("CameraHandler starting...")
        self.camera.start()
        self.stopped = False
        Thread(target=self.update, args=()).start()

    def update(self):
        while True:
            if self.stopped:
                self.camera.stop()
                return

            frame = cv2.resize(self.camera.read(), desired_resolution)
            word = np.array(cv2.imencode('.jpg', frame)[1]).tostring()
            packet = Packet(MsgType.IMAGE, word)
            with self.lock:
                self.queue.append(packet)



    def stop(self):
        logger.info("CameraHandler stopping...")
        self.stopped = True
