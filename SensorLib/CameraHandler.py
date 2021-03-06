import logging
from threading import Thread
import numpy as np
from CommSys.CommHandler import CommHandler
from CommSys.Packet import Packet, MsgType
import cv2
import time
from SensorLib.USBCamera import USBCamera
from picamera import PiCamera
from SensorLib.FrameBuffer import FrameBuffer

# CameraHandler.py
#
# Last updated: 04/11/2022 | Primary Contact: Michael Fuhrer, mfuhrer@vt.edu
# Uses threading to take video frames and encode them for transmission. Supports either RaspberryPi Camera (for
# h264 encoding) or a USB Camera (for MJPEG encoding, depreciated - no longer supported by WebGUI).

h264_resolution = '160x120'
h264_framerate = 4
h264_bitrate = 28800

jpeg_resolution = (60, 30)
jpeg_framerate = 2

logger = logging.getLogger(__name__)  # gets logger of highest-level script


class CameraHandler:
    def __init__(self, comm_handler: CommHandler, camera=None):

        self.comm_handler = comm_handler
        if camera is None:
            self.camera = PiCamera(resolution=h264_resolution, framerate=h264_framerate)
        else:
         self.camera = camera
        self.stopped = True

        if type(self.camera) == PiCamera:
            self.target = self.update_picam
        elif type(self.camera) == USBCamera:
            self.target = self.update_usb
        else:
            raise TypeError("Unrecognized camera type!")

        self.t = None

    def start(self):
        logger.info("CameraHandler starting...")
        self.stopped = False
        self.t = Thread(target=self.target)
        self.t.start()

    def update_picam(self):
        self.camera: PiCamera
        logger.debug("CameraHandler using PiCamera.")
        frame_buffer = FrameBuffer()
        self.camera.start_recording(frame_buffer, format='h264', profile="baseline", bitrate=h264_bitrate)
        self.camera.request_key_frame()
        last_key_timestamp = time.time()
        while not self.stopped:
            if time.time() - last_key_timestamp > 1:    # Get a keyframe every second, improves visual quality
                self.camera.request_key_frame()
                last_key_timestamp = time.time()

            with frame_buffer.condition:
                frame_buffer.condition.wait()
                packet = Packet(ptype=MsgType.IMAGE, pid=0, data=frame_buffer.frame)
                self.comm_handler.send_packet(packet)

        self.camera.stop_recording()

    def update_usb(self):
        logger.debug("CameraHandler using USBCamera.")
        self.camera.start()
        while not self.stopped:
            frame = self.camera.read()
            if frame is not None:
                frame = cv2.resize(self.camera.read(), jpeg_resolution)
                word = np.array(cv2.imencode('.jpg', frame)[1]).tostring()
                packet = Packet(ptype=MsgType.IMAGE, pid=0, data=word)
                self.comm_handler.send_packet(packet)
                time.sleep(1 / jpeg_framerate)  # Enforces jpeg-framerate

        self.camera.stop()  # Stop camera on close

    def stop(self):
        if not self.stopped:
            logger.info("CameraHandler stopping...")
            self.stopped = True
            self.t.join()
