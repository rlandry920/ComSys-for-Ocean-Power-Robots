#!flask/bin/python
import sys
from flask import Flask, render_template, request, redirect, Response
import random
import json

from util_functions import *

app = Flask(__name__)

FEATHER_M0 = None


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


@ app.route('/turnLeft', methods=['POST', 'DELETE'])
def turnLeft():
    return sendDirectionCommand("left")


@ app.route('/turnRight', methods=['POST', 'DELETE'])
def turnRight():
    return sendDirectionCommand("right")


@ app.route('/moveForward', methods=['POST', 'DELETE'])
def moveForward():
    return sendDirectionCommand("forward")


@ app.route('/moveBackward', methods=['POST', 'DELETE'])
def moveBackward():
    return sendDirectionCommand("backward")


@ app.route('/heartbeat', methods=['POST'])
def get_robot_heartbeat():
    status = request.form['status']
    latitude = float(request.form['latitude'])
    longitude = float(request.form['longitude'])

    print("Heartbeat Received")
    print(f"Robot Status: {status}")
    print(f"Latitude: {latitude} | Longitude: {longitude}")

    return "Heartbeat ACKd"


@ app.route('/stopTurnLeft', methods=['POST', 'DELETE'])
def stopTurnLeft():
    return "Robot stopped turning left"


@ app.route('/stopTurnRight', methods=['POST', 'DELETE'])
def stopTurnRight():
    return "Robot stopped turning right"


@ app.route('/stopMoveForward', methods=['POST', 'DELETE'])
def stopMoveForward():
    return "Robot stopped moving forward"


@ app.route('/stopMoveBackward', methods=['POST', 'DELETE'])
def stopMoveBackward():
    return "Robot stopped moving backward"


if __name__ == '__main__':
    get_feather_ip()
    app.run(host="0.0.0.0")  # Set host to 0.0.0.0 to run flask externally
