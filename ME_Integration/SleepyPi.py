import RPi.GPIO as GPIO
from smbus2 import SMBus
import os
import struct
import time
import logging

# SleepyPi.py
#
# Last updated: 04/18/2022 | Primary Contact: Michael Fuhrer, mfuhrer@vt.edu
# Object orientated approach to allow communication between SleepyPi board and robot script through
# I2C and GPIO pins.
#
# TODO List
# - Use debouncing on read voltages to reduce noise

logger = logging.getLogger(__name__)

SHUTDOWN_PIN = 24
NOTIFY_PIN = 25  # Used to let SleepyPi know RPi is on
SLEEPYPI_ADDR = 0x70


class SleepyPi():
    def __init__(self, shutdown_target=None):
        self.shutdown_target = shutdown_target  # Function that will be called if shutdown signal is received.
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(SHUTDOWN_PIN, GPIO.IN)
        GPIO.setup(NOTIFY_PIN, GPIO.OUT)
        GPIO.output(NOTIFY_PIN, GPIO.HIGH)
        logger.debug("SleepyPi Started")

    # Uses I2C to read float voltage from SleepyPi board. Previously encountered occasionally I/O errors so added a
    # try-catch which returns None if exception was encountered.
    def read_voltage(self):
        bus = SMBus(1)
        try:
            response = bytearray(bus.read_i2c_block_data(SLEEPYPI_ADDR, 0, 4))
            voltage = struct.unpack('1f', response)[0]
            logger.debug(f'SleepyPi gave voltage: {voltage}')
            bus.close()
            return voltage
        except Exception:
            return None

    # Checks the shutdown signal pin to determine whether the Pi should safely reboot in low-power mode
    def check_shutdown(self):
        if GPIO.input(SHUTDOWN_PIN):
            logger.debug("Received shutdown signal from SleepyPi")
            if callable(self.shutdown_target):
                self.shutdown_target()
            os.system("sudo shutdown -h now")


if __name__ == "__main__":
    sp = SleepyPi()
    while True:
        print("Voltage:", sp.read_voltage())
        sp.check_shutdown()
        time.sleep(2)
