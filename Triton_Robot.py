import logging
from logging.handlers import RotatingFileHandler
from SensorLib.CameraHandler import CameraHandler
from CommSys.CommMode import CommMode
from CommSys.CommHandler import CommHandler
from CommSys.Packet import MsgType, Packet
from CommSys.AROVHandler import AROVHandler
import picamera
import struct
from enum import Enum
import ME_Integration.escController as esc
from ME_Integration.SleepyPi import SleepyPi
from systemd.journal import JournaldLogHandler
import time
from SensorLib.gpsNavi import BerryGPS

# Triton_Robot.py
#
# Last updated: 04/18/2022 | Primary Contact: Michael Fuhrer, mfuhrer@vt.edu
# Main application-level script for the ocean-wave power robot. Combines Comm Sys. with Sensor Lib. and ME Integration
# to allow a remote user to obtain sensor data and control the robot live.

MOTOR_TIMEOUT = 2
LOST_TIMER = 60

heartbeat_ts = 0

motor_ts = 0
motor_on = False

g_berrygps = None
g_lat, g_long = 37.229994, -80.429152
g_compass = 0
g_voltage = 25.4


class RobotState(Enum):
    NULL = b'\x00',
    STANDBY = b'\x01',  # Waiting for connection
    IDLE = b'\x02',  # Connection made but no commands
    LIVE_CONTROL = b'\x03',
    AUTO_CONTROL = b'\x04',
    LOW_POWER = b'\x05'


# Sends notification to landbase that robot is entering low-power mode
def shutdown_notify():
    global state
    farewell_packet = Packet(MsgType.INFO, data=b'Robot shutting down due to low-power')
    comm_handler.send_packet(farewell_packet)
    state = RobotState.LOW_POWER
    send_heartbeat()
    time.sleep(5)


comm_handler = CommHandler(landbase=False)
cam = picamera.PiCamera(resolution='320x240', framerate=2)
cam_handler = CameraHandler(comm_handler, cam)
arov = AROVHandler()
sleepy = SleepyPi(shutdown_target=shutdown_notify)

state = RobotState.STANDBY


def main():
    global state, heartbeat_ts, g_berrygps
    logger.info("Robot starting...")
    logger.info("Arming ESCs...")
    esc.arm()
    logger.info("ESCs Armed!")
    logger.info("Starting BerryGPS...")
    g_berrygps = BerryGPS()
    logger.info("BerryGPS started!")

    logger.info("Connecting to landbase...")
    comm_handler.start(CommMode.HANDSHAKE)
    state = RobotState.IDLE
    logger.info("Connection with landbase established!")
    heartbeat_ts = time.time()

    try:
        while True:
            digest_packet(comm_handler.recv_packet())
            check_motors()
            sleepy.check_shutdown()
            from_arov = arov.recvfrom()
            check_lost()
            if from_arov is not None:
                logger.info(f'Forwarding UDP message from AROV...')
                arov_packet = Packet(ptype=MsgType.UDP, data=from_arov[0])
                comm_handler.send_packet(arov_packet)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.critical(str(e))
    finally:
        logging.info("Robot stopping...")
        comm_handler.stop()
        cam_handler.stop()


# Interpret packet data based on message type
def digest_packet(packet: Packet):
    global state, motor_ts, motor_on, heartbeat_ts
    if packet is None:
        return

    elif packet.type == MsgType.TEXT:
        # Print packet data in log
        logger.info(f'Received text message: {packet.data.decode("utf-8")}')

    elif packet.type == MsgType.HEARTBEAT_REQ:
        # Send heartbeat back to landbase
        logger.info(f'Received heartbeat request')
        heartbeat_ts = time.time()
        send_heartbeat()

    elif packet.type == MsgType.MTR_CMD:
        # Control motors according to command
        left, right = struct.unpack('2f', packet.data[0:8])
        logger.info(f'Received motor command: LEFT={str(left)} RIGHT={str(right)}')
        if state == RobotState.LIVE_CONTROL:
            motor_on = True
            motor_ts = time.time()
            esc.setSpeed(esc.ESC_LEFT, left)
            esc.setSpeed(esc.ESC_RIGHT, right)
        elif state == RobotState.AUTO_CONTROL:
            state = RobotState.LIVE_CONTROL
            logger.info("Stopping autonomous navigation")
            info_packet = Packet(MsgType.INFO, data=b'Stopping autonomous navigation.')
            comm_handler.send_packet(info_packet)
        else:
            logger.warning(f"Live control hasn't been enable yet!")

    elif packet.type == MsgType.CTRL_REQ:
        # Enable / disable live control and camera feed
        enable = (packet.data == b'\x01')
        if enable and (state != RobotState.LIVE_CONTROL):
            if state == RobotState.AUTO_CONTROL:
                logger.info("Stopping autonomous navigation")
                info_packet = Packet(MsgType.INFO, data=b'Stopping autonomous navigation.')
                comm_handler.send_packet(info_packet)
            state = RobotState.LIVE_CONTROL
            logger.info("Starting live control.")
            cam_handler.start()
        elif not enable and state == RobotState.LIVE_CONTROL:
            state = RobotState.IDLE
            logger.info("Stopping live control.")
            cam_handler.stop()

    elif packet.type == MsgType.GPS_CMD:
        # Set state to autonomous control TODO use autonomous navigation script
        logger.info("Received new GPS_coordinate.")
        info = b'GPS coordinates received.'
        if state != RobotState.AUTO_CONTROL:
            state = RobotState.AUTO_CONTROL
            logger.info("Starting autonomous navigation")
            info += b' Starting autonomous navigation.'
        info_packet = Packet(MsgType.INFO, data=info)
        comm_handler.send_packet(info_packet)

    else:
        logger.info(f'Received packet (ID: {packet.id} of type {packet.type})')


# Failsafe to ensure motors are shutdown in case connection with landbase is suddenly dropped
def check_motors():
    global motor_ts, motor_on
    t = time.time()
    if motor_on and t - MOTOR_TIMEOUT > motor_ts:
        esc.setSpeed(esc.ESC_LEFT, 0)
        esc.setSpeed(esc.ESC_RIGHT, 0)
        motor_on = False


# Gather sensor data to send in heartbeat message
def send_heartbeat():
    global g_lat, g_long, g_compass, g_berrygps, g_voltage
    if type(g_berrygps) != BerryGPS:
        return
    try:
        gps_read = g_berrygps.readGPS()
        comp_read = g_berrygps.readCompass()
        voltage_read = sleepy.read_voltage()

        if gps_read is not None:
            g_lat, g_long = gps_read

        if comp_read is not None:
            g_compass = comp_read

        if voltage_read is not None:
            g_voltage = voltage_read
    except Exception as e:
        logger.error(str(e))

    state_val = state.value[0]
    if type(state_val) == int:
        state_val = state_val.to_bytes(1, 'big')

    hb_data = state_val + struct.pack('4f', g_lat, g_long, g_compass, g_voltage)
    my_ip = arov.get_IP()
    if my_ip is not None:
        hb_data += my_ip.encode('utf-8')

    heartbeat = Packet(MsgType.HEARTBEAT, data=hb_data)
    comm_handler.send_packet(heartbeat)


# Check time since last received heartbeat. Reboot comm_handler if time is greater than threshold.
def check_lost():
    global state, heartbeat_ts
    t = time.time()
    if t - LOST_TIMER > heartbeat_ts:
        logger.info("Lost connection with landbase. Starting handshake mode...")
        state = RobotState.STANDBY
        comm_handler.reboot(CommMode.HANDSHAKE)
        logger.info("Connection with landbase established!")
        heartbeat_ts = time.time()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)

    log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')
    log_file = '/home/pi/Documents/ComSys-for-Ocean-Power-Robots/robot.log'
    rotating_handler = RotatingFileHandler(log_file, mode='a', maxBytes=8 * 2048,  # Max 2KB
                                           backupCount=2, encoding=None, delay=0)
    rotating_handler.setFormatter(log_formatter)
    logger.addHandler(rotating_handler)

    journald_handler = JournaldLogHandler()
    journald_handler.setFormatter(log_formatter)
    logger.addHandler(journald_handler)

    main()
