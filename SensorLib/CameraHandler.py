import logging
from multiprocessing import Process
import numpy as np
from CommSys.CommHandler import CommHandler
from CommSys.Packet import Packet, MsgType
import cv2
from SensorLib.USBCameraStream import USBCameraStream

desired_resolution = (60, 30)

logger = logging.getLogger(__name__)  # gets logger of highest-level script


class CameraHandler:
    def __init__(self, comm_handler: CommHandler):
        self.comm_handler = comm_handler
        self.camera = USBCameraStream()
        self.stopped = True
        self.t = Process(target=self.update, args=())

    def start(self):
        logger.info("CameraHandler starting...")
        self.stopped = False
        self.t.start()

    def update(self):
        self.camera.start()
        while not self.stopped:
            frame = self.camera.read()
            if frame is not None:
                frame = cv2.resize(self.camera.read(), desired_resolution)
                word = np.array(cv2.imencode('.jpg', frame)[1]).tostring()
                packet = Packet(ptype=MsgType.IMAGE, pid=0, data=word)
                self.comm_handler.send_packet(packet)

    def stop(self):
        logger.info("CameraHandler stopping...")
        self.stopped = True
        self.t.join()
        self.camera.stop()
