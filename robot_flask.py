#!flask/bin/python
import sys
from flask import Flask, render_template, request, redirect, Response
import random
import json
import requests

app = Flask(__name__)

FEATHER_M0 = None

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
        move_params = {
            "type": "coords",
            "latitude": latitude,
            "longitude": longitude
            }
        r = requests.post(f"http://{FEATHER_M0}/move", data=move_params)
        print(r.text)
        return r.text


@app.route('/turnLeft', methods=['POST', 'DELETE'])
def turnLeft():
    move_params = {
        "type": "direct",
        "direction": "left"
    }
    r = requests.post(f"http://{FEATHER_M0}/move", data=move_params)
    print(r.text)
    return r.text


@app.route('/turnRight', methods=['POST', 'DELETE'])
def turnRight():
    move_params = {
        "type": "direct",
        "direction": "right"
    }
    r = requests.post(f"http://{FEATHER_M0}/move", data=move_params)
    print(r.text)
    return r.text


@app.route('/moveForward', methods=['POST', 'DELETE'])
def moveForward():
    move_params = {
        "type": "direct",
        "direction": "forward"
    }
    r = requests.post(f"http://{FEATHER_M0}/move", data=move_params)
    print(r.text)
    return r.text


@app.route('/moveBackward', methods=['POST', 'DELETE'])
def moveBackward():
    move_params = {
        "type": "direct",
        "direction": "backward"
    }
    r = requests.post(f"http://{FEATHER_M0}/move", data=move_params)
    print(r.text)
    return r.text


@app.route('/heartbeat', methods=['POST'])
def get_robot_heartbeat():
    status = request.form['status']
    latitude = float(request.form['latitude'])
    longitude = float(request.form['longitude'])

    print("Heartbeat Received")
    print(f"Robot Status: {status}")
    print(f"Latitude: {latitude} | Longitude: {longitude}")

    return "Heartbeat ACKd"


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


# Cannot implement below for demo due to limitations on how the Arduino acts as an I2C-slave :(
# @app.route('/randomNum', methods=['POST', 'DELETE'])
# def randomNum():
#     r = requests.post("http://<FeatherM0>:<port>/query")
#     return r.text


def get_feather_ip():
    global FEATHER_M0
    FEATHER_M0 = input("Please enter the IP and port of the FeatherM0 Board's HTTP Server: ")


if __name__ == '__main__':
    get_feather_ip()
    app.run(host="0.0.0.0")  # Set host to 0.0.0.0 to run flask externally
