#!flask/bin/python
from flask import Flask, request, Response, render_template, redirect, url_for
import logging
import numpy as np
import logging
import cv2
import json
from threading import Thread

from WebGUI.WebGUI_Utils import *

app = Flask(__name__, static_url_path='/static', static_folder='static')

currDirection = 0
currCoordinates = {
    "lat": 37.2284,
    "long": -80.4234
}

logger = logging.getLogger(__name__)

activeUsers = 0


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/')
def openWindow():
    global activeUsers
    activeUsers += 1
    msg = {
        "type": "num-users",
        "num-users": activeUsers
    }
    app.config['websocketData'].manager.broadcast(json.dumps(msg))
    return "WINDOW OPENED"


@app.route('/script.js')
def script():
    return render_template('index.js')


@app.route('/goToCoordinates', methods=['POST', 'DELETE'])
def goToCoordinates():
    data = request.get_json()[0]
    latitude, longitude = getStringCoordinates(data)
    error = checkCoordinates(latitude, longitude)

    if error != None:
        return error
    else:
        message = sendMoveToCommand(float(latitude), float(
            longitude), app.config['commHandler'])
        msg = {
            "type": "message",
            "message": message
        }
        app.config['websocketData'].manager.broadcast(json.dumps(msg))
        return message


@app.route('/move', methods=['POST', 'DELETE'])
def move():
    data = request.get_json()[0]
    command = data["command"]
    speed = data["speed"]

    global currDirection
    global currCoordinates
    if (command == "turnLeft"):
        currDirection -= 5
    elif (command == "turnRight"):
        currDirection += 5
    elif (command == "moveForward"):
        currCoordinates['lat'] += 0.005
        currCoordinates['long'] += 0.005

    elif command == "moveBackward":
        currCoordinates['lat'] -= 0.005
        currCoordinates['long'] -= 0.005

    message = sendDirectionCommand(command, speed, app.config['commHandler'])
    msg = {
        "type": "message",
                "message": message
    }
    app.config['websocketData'].manager.broadcast(json.dumps(msg))
    return message


@app.route('/stop', methods=['POST', 'DELETE'])
def stop():
    message = sendDirectionCommand("stop", app.config['commHandler'])
    msg = {
        "type": "message",
                "message": message
    }
    app.config['websocketData'].manager.broadcast(json.dumps(msg))
    return message


@app.route('/switchMotor', methods=['POST', 'DELETE'])
def switchMotor():
    message = sendMotorSwitchCommand(
        request.data.decode('ascii'), app.config['commHandler'])
    msg = {
        "type": "message",
        "message": message
    }
    app.config['websocketData'].manager.broadcast(json.dumps(msg))
    return message


@app.route('/closeWindow', methods=['POST', 'DELETE'])
def closeWindow():
    print("WINDOW CLOSED")
    global activeUsers
    activeUsers -= 1
    msg = {
        "type": "num-users",
        "num-users": activeUsers
    }
    app.config['websocketData'].manager.broadcast(json.dumps(msg))
    return "Window Closed"


@app.route('/getNumUsers', methods=['POST', 'DELETE'])
def getNumUsers():
    return str(activeUsers)

# Some file is trying to access root/Decoder.js instead of the static URL, this is a temporary fix to resolve this


@app.route('/reqLiveControl', methods=['POST', 'DELETE'])
def reqLiveControl():
    data = request.get_json()[0]
    enable = data["enable"]
    return liveControl(enable, app.config['commHandler'])


@app.route('/Decoder.js')
def reroute_js():
    return redirect(url_for('static', filename='script/Decoder.js'))
