#!flask/bin/python
from flask import Flask, request, Response
from logging import Logger
import numpy as np
from CommSys.CommHandler import CommHandler
from SensorLib.FPS import FPS
from camera import Camera
import base64
import io
import random
import json
import logging
import sys
import cv2

from util_functions import *

app = Flask(__name__)

FEATHER_M0 = None

fps = FPS()
comm_handler = CommHandler()

currDirection = 0
currCoordinates = {
    "lat": 37.2284,
    "long": -80.4234
}

logging.basicConfig(filename='landbase.log',
                    level=logging.DEBUG,
                    format='%(asctime)s | %(funcName)s | %(levelname)s | %(message)s')

logger = logging.getLogger(__name__)

display_resolution = (240, 120)


@app.route('/', methods=['GET', 'POST', 'DELETE'])
def output():
    return


@app.route('/goToCoordinates', methods=['POST', 'DELETE'])
def goToCoordinates():
    data = request.get_json()[0]
    latitude, longitude = getCoordinates(data)
    error = checkCoordinates(latitude, longitude)

    if(error != None):
        return error
    else:
        move_params = {
            "type": "coords",
            "latitude": latitude,
            "longitude": longitude
        }
        url = f"http://{FEATHER_M0}/move?type=coords&latitude={str(latitude)}&longitude={str(longitude)}"
        print(url)
        r = requests.post(url
                          )
        print(r.status_code)
        return r.text


@ app.route('/move', methods=['POST', 'DELETE'])
def move():
    data = request.get_json()[0]
    command = data["command"]
    speed = data["speed"]

    global currDirection
    global currCoordinates
    if(command == "turnLeft"):
        currDirection -= 5
    elif(command == "turnRight"):
        currDirection += 5
    elif(command == "moveForward"):
        currCoordinates['lat'] += 0.005
        currCoordinates['long'] += 0.005

    elif(command == "moveBackward"):
        currCoordinates['lat'] -= 0.005
        currCoordinates['long'] -= 0.005

    return sendDirectionCommand(command, comm_handler)


@ app.route('/stop', methods=['POST', 'DELETE'])
def stop():
    return sendDirectionCommand("stop", comm_handler)


@ app.route('/getDirection', methods=['POST', 'DELETE'])
def getDirection():
    return str(currDirection)


@ app.route('/getCoordinates', methods=['POST', 'DELETE'])
def getCoordinates():
    return currCoordinates


@ app.route('/heartbeat', methods=['POST'])
def get_robot_heartbeat():
    status = request.form['status']
    latitude = float(request.form['latitude'])
    longitude = float(request.form['longitude'])

    print("Heartbeat Received")
    print(f"Robot Status: {status}")
    print(f"Latitude: {latitude} | Longitude: {longitude}")

    return "Heartbeat ACKd"


def main():
    Logger.info("Landbase starting...")
    comm_handler.start()
    print("Connection with robot established!")
    fps.start()
    try:
        while True:
            if comm_handler.recv_flag():
                packet = comm_handler.recv_packet()
                digest_packet(packet)
    except KeyboardInterrupt:
        pass
    finally:
        logging.info("Landbase stopping...")
        comm_handler.stop()
        fps.stop()

        logger.info("[INFO] elasped time: {:.2f}".format(fps.elapsed()))
        logger.info("[INFO] approx. FPS: {:.2f}".format(fps.fps()))


def digest_packet(packet: Packet):
    if packet is None:
        return
    elif packet.type == MsgType.TEXT:
        print(packet.data.decode('utf-8'))
    elif packet.type == MsgType.IMAGE:
        decode_word = np.frombuffer(packet.data, dtype=np.uint8)
        frame = cv2.resize(cv2.imdecode(
            decode_word, cv2.IMREAD_COLOR), display_resolution)
        cv2.imshow('frame', frame)
        cv2.waitKey(1)
        fps.update()
    else:
        print(f'Received packet (ID: {packet.id} of type {packet.type})')


if __name__ == '__main__':
    # get_feather_ip()
    # Set host to 0.0.0.0 to run flask externally
    # main()
    app.run(host="0.0.0.0", port=5001)
