import requests


def sendDirectionCommand(direction):
    # move_params = {
    #     "type": "direct",
    #     "direction": direction
    # }
    # r = requests.post(
    #     f"http://{FEATHER_M0}/move?type=direct&direction={direction}")
    # print(r.text)
    # return r.text
    return f"Moving {direction}"


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

# def makePathToCoordinates():


# Cannot implement below for demo due to limitations on how the Arduino acts as an I2C-slave :(
# @app.route('/randomNum', methods=['POST', 'DELETE'])
# def randomNum():
#     r = requests.post("http://<FeatherM0>:<port>/query")
#     return r.text
def get_feather_ip():
    global FEATHER_M0
    FEATHER_M0 = input(
        "Please enter the IP and port of the FeatherM0 Board's HTTP Server: ")
