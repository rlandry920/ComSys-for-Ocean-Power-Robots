from threading import Thread
import cv2

# USBCamera.py
#
# Last updated: 03/02/2022 | Primary Contact: Michael Fuhrer, mfuhrer@vt.edu
# Multi-threaded approach to gathering images from USB camera following tutorial @
# https://www.pyimagesearch.com/2015/12/28/increasing-raspberry-pi-fps-with-python-and-opencv/

# Depreciated

class USBCamera:
    def __init__(self):
        self.stream = None
        self.frame = None
        self.grabbed = None
        self.stopped = True
        self.t = Thread(target=self.__update)

    def __del__(self):
        self.stop()

    def start(self):
        if self.stopped:
            self.stream = cv2.VideoCapture(0)
            self.stopped = False
            self.t.start()
            return self

    def __update(self):
        while not self.stopped:
            (self.grabbed, self.frame) = self.stream.read()

    def read(self):
        return self.frame

    def stop(self):
        if not self.stopped:
            self.stopped = True
            self.t.join()
            self.stream.release()
            self.stream = None
