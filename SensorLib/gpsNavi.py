#! /usr/bin/python
import time
import smbus
import signal
import sys
import math
from SensorLib import IMU
import datetime
import os
import logging

logger = logging.getLogger(__name__)

BUS = None
address = 0x42
gpsReadInterval = 0.03

# //////////////////////////////////////////////////////
RAD_TO_DEG = 57.29578
M_PI = 3.14159265358979323846
G_GAIN = 0.070  # [deg/s/LSB]  If you change the dps for gyro, you need to update this value accordingly
AA = 0.40  # Complementary filter constant

################# Compass Calibration values ############
# Use calibrateBerryIMU.py to get calibration values
# Calibrating the compass isnt mandatory, however a calibrated
# compass will result in a more accurate heading value.

magXmin = 0
magYmin = 0
magZmin = 0
magXmax = 0
magYmax = 0
magZmax = 0

'''
Here is an example:
magXmin =  -1748
magYmin =  -1025
magZmin =  -1876
magXmax =  959
magYmax =  1651
magZmax =  708
Dont use the above values, these are just an example.
'''

class BerryGPS():
    def __init__(self):
        self.IMU_found = True
        IMU.detectIMU()  # Detect if BerryIMU is connected.
        if (IMU.BerryIMUversion == 99):
            self.IMU_found = False
        IMU.initIMU()  # Initialise the accelerometer, gyroscope and compass

    def readCompass(self):
        if not self.IMU_found:
            return None

        ACCx = IMU.readACCx()
        ACCy = IMU.readACCy()
        ACCz = IMU.readACCz()
        MAGx = IMU.readMAGx()
        MAGy = IMU.readMAGy()
        MAGz = IMU.readMAGz()

        # Apply compass calibration
        MAGx -= (magXmin + magXmax) / 2
        MAGy -= (magYmin + magYmax) / 2
        MAGz -= (magZmin + magZmax) / 2
        ####################################################################
        ###################Tilt compensated heading#########################
        ####################################################################
        # Normalize accelerometer raw values.
        accXnorm = ACCx / math.sqrt(ACCx * ACCx + ACCy * ACCy + ACCz * ACCz)
        accYnorm = ACCy / math.sqrt(ACCx * ACCx + ACCy * ACCy + ACCz * ACCz)

        # Calculate pitch and roll
        pitch = math.asin(accXnorm)
        roll = -math.asin(accYnorm / math.cos(pitch))

        # Calculate the new tilt compensated values
        # The compass and accelerometer are orientated differently on the the BerryIMUv1, v2 and v3.
        # This needs to be taken into consideration when performing the calculations

        # X compensation
        if (IMU.BerryIMUversion == 1 or IMU.BerryIMUversion == 3):  # LSM9DS0 and (LSM6DSL & LIS2MDL)
            magXcomp = MAGx * math.cos(pitch) + MAGz * math.sin(pitch)
        else:  # LSM9DS1
            magXcomp = MAGx * math.cos(pitch) - MAGz * math.sin(pitch)

        # Y compensation
        if (IMU.BerryIMUversion == 1 or IMU.BerryIMUversion == 3):  # LSM9DS0 and (LSM6DSL & LIS2MDL)
            magYcomp = MAGx * math.sin(roll) * math.sin(pitch) + MAGy * math.cos(roll) - MAGz * math.sin(
                roll) * math.cos(
                pitch)
        else:  # LSM9DS1
            magYcomp = MAGx * math.sin(roll) * math.sin(pitch) + MAGy * math.cos(roll) + MAGz * math.sin(
                roll) * math.cos(
                pitch)

        # Calculate tilt compensated heading
        tiltCompensatedHeading = 180 * math.atan2(magYcomp, magXcomp) / M_PI

        if tiltCompensatedHeading < 0:
            tiltCompensatedHeading += 360

        ##################### END Tilt Compensation ########################
        return tiltCompensatedHeading

    def readGPS(self):
        if not self.IMU_found:
            return None

        response = []
        try:
            BUS = smbus.SMBus(1)
            while True:  # Newline, or bad char.
                c = BUS.read_byte(address)

                if c == 255:
                    return None
                elif c == 10:
                    break
                else:
                    response.append(c)

            return self.__parseResponse(response)
        except Exception as e:
            logger.error(str(e))

    def __parseResponse(self, gpsLine):
        if (gpsLine.count(36) == 1):  # Check #1, make sure '$' doesnt appear twice
            if len(gpsLine) < 84:  # Check #2, 83 is maximun NMEA sentenace length.
                CharError = 0;
                for c in gpsLine:  # Check #3, Make sure that only readiable ASCII charaters and Carriage Return are seen.
                    if (c < 32 or c > 122) and c != 13:
                        CharError += 1
                if (CharError == 0):  # Only proceed if there are no errors.
                    gpsChars = ''.join(chr(c) for c in gpsLine)
                    if (gpsChars.find('txbuf') == -1):  # Check #4, skip txbuff allocation error

                        gpsStr, chkSum = gpsChars.split('*', 2)  # Check #5 only split twice to avoid unpack error
                        gpsComponents = gpsStr.split(',')

                        chkVal = 0

                        for ch in gpsStr[1:]:  # Remove the $ and do a manual checksum on the rest of the NMEA sentence
                            chkVal ^= ord(ch)
                        if (chkVal == int(chkSum,
                                          16)):  # Compare the calculated checksum with the one in the NMEA sentence
                            return self.__parseNMEA(gpsChars)

    def __parseNMEA(self, data):
        if data[0:6] == "$GNRMC":
            sdata = data.split(",")
            if sdata[2] == 'V':
                logger.error("no satellite data available")
                return None
            if sdata[2] == 'A':
                time = sdata[1][0:2] + ":" + sdata[1][2:4] + ":" + sdata[1][4:6]
                lat = self.__decode(sdata[3])  # latitude
                dirLat = sdata[4]  # latitude sym
                lon = self.__decode(sdata[5])  # longitute
                dirLon = sdata[6]  # longitude sym
                speed = sdata[7]  # Speed in knots
                trCourse = sdata[8]  # True course
                date = sdata[9][0:2] + "/" + sdata[9][2:4] + "/" + sdata[9][4:6]  # date
                logger.debug(f'GPS RETURNED: {time}, {lat} {dirLat}, {lon} {dirLon}, {speed}, {trCourse}, {date}')
                return lat, lon


    def __decode(self, coord):
        # Converts DDDMM.MMMMM > DD deg MM.MMMMM min
        x = coord.split(".")
        head = x[0]
        tail = x[1]
        deg = head[0:-2]
        min = head[-2:]
        return deg + " deg " + min + "." + tail + " min"


def main():
    gps = BerryGPS()

    while True:
        comp_reading = gps.readCompass()
        if comp_reading is None:
            print("Compass: No Compass data available")
        else:
            print("Compass:", comp_reading)
        gps_reading = gps.readGPS()
        if gps_reading is None:
            print("GPS: No GPS data available")
        else:
            print("GPS:", gps_reading)

        time.sleep(5)





if __name__ == "__main__":
    main()
