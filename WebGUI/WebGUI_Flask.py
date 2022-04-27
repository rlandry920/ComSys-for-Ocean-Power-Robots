#!flask/bin/python
from flask import Flask, request, Response, render_template, redirect, url_for
import logging
import numpy as np
import logging
import cv2
import json
from threading import Thread

from WebGUI.WebGUI_Utils import *

# WebGUI_Flask.py
#
# Last updated: 04/26/2022
# This serves as a backend for the landbase in order to keep the UI seperate from all of the
# commands. Each of the routes has a function attatched to it that will be run whenever the route
# is accessed. The landbase can access these functions using HTTP. These function can then send messages
# to the robot using the CommSys and also send messages back to the landbase using the websockets. This
# also packs all of the HTML and JS together.


app = Flask(__name__, static_url_path='/static', static_folder='static')

logger = logging.getLogger(__name__)

activeUsers = 0


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/script.js')
def script():
    return render_template('index.js')


@app.route('/openWindow', methods=['POST', 'DELETE'])
def openWindow():
    global activeUsers
    activeUsers += 1
    msg = {
        "type": "num-users",
        "num-users": activeUsers
    }
    app.config['websocketData'].manager.broadcast(json.dumps(msg))
    return "WINDOW OPENED"


@app.route('/goToCoordinates', methods=['POST', 'DELETE'])
def goToCoordinates():
    data = request.get_json()[0]
    latitude, longitude = getStringCoordinates(data)
    # Make sure coordinates are valid
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


# Hard coded values for GPS
@app.route('/move', methods=['POST', 'DELETE'])
def move():
    data = request.get_json()[0]
    command = data["command"]
    speed = data["speed"]

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


@app.route('/closeWindow', methods=['POST', 'DELETE'])
def closeWindow():
    global activeUsers
    if(activeUsers > 0):
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
