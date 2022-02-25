#!flask/bin/python
from flask import Flask, request, Response, render_template
from logging import Logger
import numpy as np
from CommSys.CommHandler import CommHandler, CommMode
from SensorLib.FPS import FPS
from camera import Camera
import logging
import cv2
from threading import Thread

from util_functions import *

app = Flask(__name__, static_url_path='/static', static_folder='static')

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


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/script.js')
def script():
    return render_template('index.js')


def gen(camera):
    while True:
        frame = camera.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.route('/video_feed')
def video_feed():
    return Response(gen(Camera()),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/goToCoordinates', methods=['POST', 'DELETE'])
def goToCoordinates():
    data = request.get_json()[0]
    latitude, longitude = getStringCoordinates(data)
    error = checkCoordinates(latitude, longitude)

    if error != None:
        return error
    else:
        return sendMoveToCommand(float(latitude), float(longitude), comm_handler)


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

    elif command == "moveBackward":
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
    logger.info("Landbase starting...")
    comm_handler.start(mode=CommMode.DEBUG)
    fps.start()
    try:
        while True:
            if comm_handler.recv_flag():
                packet = comm_handler.recv_packet()
                digest_packet(packet)
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Landbase stopping...")
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
    Thread(target=main).start()
    app.run(host="0.0.0.0", port=5000)
