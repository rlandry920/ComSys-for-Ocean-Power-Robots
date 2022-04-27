import socket
import errno
import netifaces as ni

# AROVHandler.py, previously RadioHandler.py
#
# Last updated: 04/18/2022 | Primary Contact: Michael Fuhrer, mfuhrer@vt.edu
# Proof-of-concept to demonstrate the robot forwarding any received data from a hypothetical AROV to the landbase.
# Also used to advertise IP address of robot to help with remote SSH'ing.

PORT = 1337


class AROVHandler():
    def __init__(self):
        self.s = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.s.bind(('', PORT))
        self.s.setblocking(False)

    def __del__(self):
        self.s.close()

    # Non-blocking approach from https://stackoverflow.com/questions/16745409/what-does-pythons-socket-recv-return-for-non-blocking-sockets-if-no-data-is-r
    def recvfrom(self):
        try:
            return self.s.recvfrom(4096)
        except socket.timeout:
            return None
        except socket.error as e:
            err = e.args[0]
            if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
                return None

    def sendto(self, data, addr):
        self.s.sendto(data, addr)

    def get_IP(self):
        try:
            return ni.ifaddresses('wlan0')[ni.AF_INET][0]['addr']
        except Exception as e:
            return None