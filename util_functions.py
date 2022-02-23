from CommSys.Packet import Packet, MsgType
import struct
import sys
import requests


def sendDirectionCommand(direction, commHandler):
    # move_params = {
    #     "type": "direct",
    #     "direction": direction
    # }
    # r = requests.post(
    #     f"http://{FEATHER_M0}/move?type=direct&direction={direction}")
    # print(r.text)
    # return r.text
    if(direction == "turnLeft"):
        left = 1
        right = 0
    elif(direction == "turnRight"):
        left = 0
        right = 1
    elif(direction == "moveForward"):
        left = 1
        right = 1
    elif(direction == "moveBackward"):
        left = -1
        right = -1
    elif(direction == "stop"):
        left = 0
        right = 0
    else:
        return
    motor_command = struct.pack('f', left) + \
        struct.pack('f', right) + bytes([0])

    motor_command_packet = Packet(MsgType.MTR_CMD, 0, motor_command, False)

    commHandler.send_packet(motor_command_packet)

    return f"Robot {direction}"


def getCoordinates(data):
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


def checkCoordinates(latitude, longitude):
    if(latitude == "" and longitude == ""):
        return "Invalid latitude and longitude"
    elif(latitude == ""):
        return "Invalid latitude"
    elif(longitude == ""):
        return "Invalid longitude"
    else:
        return None

# Cannot implement below for demo due to limitations on how the Arduino acts as an I2C-slave :(
# @app.route('/randomNum', methods=['POST', 'DELETE'])
# def randomNum():
#     r = requests.post("http://<FeatherM0>:<port>/query")
#     return r.text


def get_feather_ip():
    global FEATHER_M0
    FEATHER_M0 = input(
        "Please enter the IP and port of the FeatherM0 Board's HTTP Server: ")
