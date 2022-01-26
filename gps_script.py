import math

#  North is 0
#  East is 90
#  South is 180
#  West is 270


curr_lat = 39.099912
curr_long = -94.581213
curr_dir = 0

# go_to_lat = input("Enter the latitude you want to go to: ")
# go_to_long = input("Enter the longitude you want to go: ")
go_to_lat = 38.627089
go_to_long = -90.200203


def find_bearing(lat1, long1, lat2, long2):
    lat1 = (lat1/180)*math.pi
    lat2 = (lat2/180)*math.pi

    delta_long = (long2-long1) * math.pi/180

    x = math.cos(lat2) * math.sin(delta_long)
    y = (math.cos(lat1) * math.sin(lat2)) - \
        (math.sin(lat1) * math.cos(lat2)*math.cos(delta_long))

    B_radians = math.atan2(x, y)
    B_degrees = (B_radians*180)/math.pi
    if(B_degrees < 0):
        B_degrees += 360

    return B_degrees


def find_angle(lat1, long1, lat2, long2):
    dx = long2-long1
    dy = lat2-lat1
    B_radians = math.atan2(dx, dy)
    B_degrees = (B_radians*180)/math.pi
    if(B_degrees < 0):
        B_degrees += 360

    print(B_degrees)


def get_curr_dir():
    return curr_dir


def turn_clockwise():
    global curr_dir
    curr_dir += 1
    if curr_dir == 360:
        curr_dir = 0


def turn_counterclockwise():
    global curr_dir
    curr_dir -= 1
    if curr_dir == 0:
        curr_dir = 360


def find_turn_dir(curr_dir, bearing):
    temp_angle = (curr_dir + 180) % 360
    if(curr_dir < 180 and bearing < temp_angle and curr_dir < bearing) or (curr_dir >= 180 and ((bearing < 360 and curr_dir < bearing) or (bearing < temp_angle))):
        return "clockwise"
    return "counterclockwise"


# https://community.esri.com/t5/coordinate-reference-systems-blog/distance-on-a-sphere-the-haversine-formula/ba-p/902128
def find_distance(lat1, long1, lat2, long2):

    R = 6371000  # radius of Earth in meters
    phi_1 = math.radians(lat1)
    phi_2 = math.radians(lat2)

    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(long2 - long1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi_1) * \
        math.cos(phi_2) * math.sin(delta_lambda / 2.0) ** 2

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    meters = R * c  # output distance in meters

    return meters


def find_path_to_coord(lat1, long1, lat2, long2):
    bearing = find_bearing(curr_lat, curr_long, go_to_lat, go_to_long)
    print("Bearing: " + str(bearing) + " degrees")

    robot_dir = get_curr_dir()

    turn_dir = find_turn_dir(robot_dir, bearing)
    print("Turning "+turn_dir)

    while(abs(curr_dir-bearing) < 2):
        if(turn_dir == "clockwise"):
            turn_clockwise()
        else:
            turn_counterclockwise()

    print("Finished turning")

    dist = find_distance(lat1, long1, lat2, long2)

    print("Moving " + str(dist) + " meters forward")


find_path_to_coord(curr_lat, curr_long, go_to_lat, go_to_lat)
