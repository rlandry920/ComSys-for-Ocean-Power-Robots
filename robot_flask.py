#!flask/bin/python
import sys
from flask import Flask, render_template, request, redirect, Response
import random
import json
import requests

app = Flask(__name__)


@app.route('/', methods=['GET', 'POST', 'DELETE'])
def output():
    return


@app.route('/goToCoordinates', methods=['POST', 'DELETE'])
def goToCoordinates():
    data = request.get_json()[0]
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
    if(latitude == "" and longitude == ""):
        return "Invalid latitude and longitude"
    elif(latitude == ""):
        return "Invalid latitude"
    elif(longitude == ""):
        return "Invalid longitude"
    else:
        r = request("http://<FeatherM0>:<port>/move?type=coords&latitude=" +
                    str(latitude)+"&longitude="+str(longitude))
        return r.text


@app.route('/turnLeft', methods=['POST', 'DELETE'])
def turnLeft():
    r = requests.post(
        "http://<FeatherM0>:<port>/move?type=direct&direction=left")
    return r.text


@app.route('/turnRight', methods=['POST', 'DELETE'])
def turnRight():
    r = requests.post(
        "http://<FeatherM0>:<port>/move?type=direct&direction=right")
    return r.text


@app.route('/moveForward', methods=['POST', 'DELETE'])
def moveForward():
    r = requests.post(
        "http://<FeatherM0>:<port>/move?type=direct&direction=forward")
    return r.text


@app.route('/moveBackward', methods=['POST', 'DELETE'])
def moveBackward():
    r = requests.post(
        "http://<FeatherM0>:<port>/move?type=direct&direction=backward")
    return r.text


@app.route('/stopTurnLeft', methods=['POST', 'DELETE'])
def stopTurnLeft():
    return "Robot stopped turning left"


@app.route('/stopTurnRight', methods=['POST', 'DELETE'])
def stopTurnRight():
    return "Robot stopped turning right"


@app.route('/stopMoveForward', methods=['POST', 'DELETE'])
def stopMoveForward():
    return "Robot stopped moving forward"


@app.route('/stopMoveBackward', methods=['POST', 'DELETE'])
def stopMoveBackward():
    return "Robot stopped moving backward"


@app.route('/randomNum', methods=['POST', 'DELETE'])
def randomNum():
    r = requests.post("http://<FeatherM0>:<port>/query")
    return r.text


if __name__ == '__main__':
    # run!
    app.run()
