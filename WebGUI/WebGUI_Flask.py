#!flask/bin/python
from flask import Flask, request, Response, render_template, redirect, url_for
import logging
import numpy as np
import logging
import cv2
from threading import Thread

from WebGUI.WebGUI_Utils import *

app = Flask(__name__, static_url_path='/static', static_folder='static')

currDirection = 0
currCoordinates = {
    "lat": 37.2284,
    "long": -80.4234
}

logger = logging.getLogger(__name__)


@app.route('/')
def index():
    return render_template('index.html')


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
        return sendMoveToCommand(float(latitude), float(longitude), app.config['commHandler'])


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

    return sendDirectionCommand(command, app.config['commHandler'])


@app.route('/stop', methods=['POST', 'DELETE'])
def stop():
    return sendDirectionCommand("stop", app.config['commHandler'])


@app.route('/getDirection', methods=['POST', 'DELETE'])
def getDirection():
    return str(currDirection)


@app.route('/getCoordinates', methods=['POST', 'DELETE'])
def getCoordinates():
    return currCoordinates


@app.route('/heartbeat', methods=['POST'])
def get_robot_heartbeat():
    status = request.form['status']
    latitude = float(request.form['latitude'])
    longitude = float(request.form['longitude'])

    print("Heartbeat Received")
    print(f"Robot Status: {status}")
    print(f"Latitude: {latitude} | Longitude: {longitude}")

    return "Heartbeat ACKd"

# Some file is trying to access root/Decoder.js instead of the static URL, this is a temporary fix to resolve this


@app.route('/Decoder.js')
def reroute_js():
    return redirect(url_for('static', filename='script/Decoder.js'))
