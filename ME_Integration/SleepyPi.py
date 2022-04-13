import RPi.GPIO as GPIO
from smbus2 import SMBus
import os
import struct
import time

SHUTDOWN_PIN = 24
NOTIFY_PIN = 25  # Used to let SleepyPi know RPi is on
SLEEPYPI_ADDR = 0x70


class SleepyPi():
    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(SHUTDOWN_PIN, GPIO.IN)
        GPIO.setup(NOTIFY_PIN, GPIO.OUT)
        GPIO.output(NOTIFY_PIN, GPIO.HIGH)

    def read_voltage(self):
        bus = SMBus(1)
        response = bus.read_block_data(SLEEPYPI_ADDR, 0x00, 4)
        print(response)
        voltage = struct.unpack('1f', response)
        bus.close()
        return voltage

    def check_shutdown(self):
        if GPIO.input(SHUTDOWN_PIN):
            os.system("sudo shutdown -h now")


if __name__ == "__main__":
    sp = SleepyPi()
    while True:
        print("Voltage:", sp.read_voltage())
        sp.check_shutdown()
        time.sleep(2)
