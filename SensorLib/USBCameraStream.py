from threading import Thread
import cv2


# Multi-threaded approach to gathering images from USB camera following tutorial @
# https://www.pyimagesearch.com/2015/12/28/increasing-raspberry-pi-fps-with-python-and-opencv/

# Used in CameraHandler.py

class USBCameraStream:
    def __init__(self):
        self.stream = cv2.VideoCapture(0)
        (self.grabbed, self.frame) = self.stream.read()
        self.stopped = True

    def __del__(self):
        self.stream.release()

    def start(self):
        self.stopped = False
        Thread(target=self.update, args=()).start()
        return self

    def update(self):
        while True:
            if self.stopped:
                return

            (self.grabbed, self.frame) = self.stream.read()

    def read(self):
        return self.frame

    def stop(self):
        self.stopped = True
