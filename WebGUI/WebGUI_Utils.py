from CommSys.Packet import Packet, MsgType
import struct
import sys
import requests


# WebGUI_Utils.py
#
# Last updated: 04/26/2022
# Contains utility functions that are used by the Flask script. These functions create packets that can
# be sent to the robot using the CommSys.
#


# Create packet for movement command


def sendDirectionCommand(direction, speed, commHandler):
    if(direction == "turnLeft"):
        left = -speed
        right = speed
    elif(direction == "turnRight"):
        left = speed
        right = -speed
    elif(direction == "moveForward"):
        left = speed
        right = speed
    elif(direction == "moveBackward"):
        left = -speed
        right = -speed
    elif(direction == "stop"):
        left = 0
        right = 0
    else:
        return

    # Send values for left and right motor

    motor_command = struct.pack('f', left) + \
        struct.pack('f', right) + bytes([0])

    motor_command_packet = Packet(MsgType.MTR_CMD, 0, motor_command, False)

    commHandler.send_packet(motor_command_packet)

    return f"Robot {direction}"


# Create packet for autonomous navigation
def sendMoveToCommand(latitude, longitude, commHandler):
    move_command = struct.pack('f', latitude) + \
        struct.pack('f', longitude) + bytes([0])

    motor_command_packet = Packet(MsgType.GPS_CMD, 0, move_command, False)

    commHandler.send_packet(motor_command_packet)
    return f"Robot moving to ({round(latitude,4)}, {round(longitude,4)})"

# Turn coordinates into strings


def getStringCoordinates(data):
    latitude = ""
    longitude = ""
    if("lat_py" in data):
        lat = data["lat_py"][:-1].replace('.', '')
        lat = lat.replace('-', '')
        if(lat.isnumeric()):
            latitude = data["lat_py"]
    if("long_py" in data):
        long = data["long_py"][:-1].replace('.', '')
        long = long.replace('-', '')
        if(long.isnumeric()):
            longitude = data["long_py"]

    return latitude, longitude

# Make sure coordinates are valid


def checkCoordinates(latitude, longitude):
    if(latitude == "" and longitude == ""):
        return "Invalid latitude and longitude"
    elif(latitude == ""):
        return "Invalid latitude"
    elif(longitude == ""):
        return "Invalid longitude"
    else:
        return None

# Turn live control on or off


def liveControl(enable, commHandler):
    if enable:
        request_packet = Packet(ptype=MsgType.CTRL_REQ, data=b'\x01')
        message = "Requesting live control..."
    else:
        request_packet = Packet(ptype=MsgType.CTRL_REQ, data=b'\x00')
        message = "Halting live control..."

    commHandler.send_packet(request_packet)
    return message
