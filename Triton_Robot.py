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

MOTOR_TIMEOUT = 2

motor_ts = 0
motor_on = False


class RobotState(Enum):
    NULL = b'\x00',
    STANDBY = b'\x01',  # Waiting for connection
    IDLE = b'\x02',  # Connection made but no commands
    LIVE_CONTROL = b'\x03',
    AUTO_CONTROL = b'\x04',
    LOW_POWER = b'\x05'


comm_handler = CommHandler(landbase=False)
cam = picamera.PiCamera(resolution='320x240', framerate=5)
cam_handler = CameraHandler(comm_handler, cam)
arov = AROVHandler()
sleepy = SleepyPi()

state = RobotState.STANDBY


def main():
    global state
    logger.info("Robot starting...")
    logger.info("Arming ESCs...")
    esc.arm()
    logger.info("ESCs Armed!")

    logger.info("Connecting to landbase...")
    comm_handler.start(CommMode.HANDSHAKE)
    state = RobotState.IDLE
    logger.info("Connection with landbase established!")

    try:
        while True:
            digest_packet(comm_handler.recv_packet())
            check_motors()

            from_arov = arov.recvfrom()
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


def digest_packet(packet: Packet):
    global state, motor_ts, motor_on
    if packet is None:
        return
    elif packet.type == MsgType.TEXT:
        logger.info(f'Received text message: {packet.data.decode("utf-8")}')
    elif packet.type == MsgType.HEARTBEAT_REQ:
        logger.info(f'Received heartbeat request')
        send_heartbeat()
    elif packet.type == MsgType.MTR_CMD:
        left, right = struct.unpack('2f', packet.data[0:8])
        logger.info(f'Received motor command: LEFT={str(left)} RIGHT={str(right)}')
        if state == RobotState.LIVE_CONTROL:
            motor_on = True
            motor_ts = time.time()
            esc.setSpeed(esc.ESC_LEFT, left)
            esc.setSpeed(esc.ESC_RIGHT, right)
        else:
            logger.warning(f"Live control hasn't been enable yet!")
    elif packet.type == MsgType.CTRL_REQ:
        enable = (packet.data == b'\x01')
        if enable and (state == RobotState.IDLE or state == RobotState.AUTO_CONTROL):
            state = RobotState.LIVE_CONTROL
            logger.info("Starting live control.")
            cam_handler.start()
        elif not enable and state == RobotState.LIVE_CONTROL:
            state = RobotState.IDLE
            logger.info("Stopping live control.")
            cam_handler.stop()
    else:
        logger.info(f'Received packet (ID: {packet.id} of type {packet.type})')


def check_motors():
    global motor_ts, motor_on
    t = time.time()
    if motor_on and t - MOTOR_TIMEOUT > motor_ts:
        esc.setSpeed(esc.ESC_LEFT, 0)
        esc.setSpeed(esc.ESC_RIGHT, 0)
        motor_on = False


def getGPS():
    return 37.229994, -80.429152


def getCompass():
    return 15.0


def send_heartbeat():
    lat, long = getGPS()
    comp = getCompass()
    voltage = sleepy.read_voltage()
    logger.info(state.value[0])
    logger.info(struct.pack('4f', lat, long, comp, voltage))
    hb_data = state.value[0] + struct.pack('4f', lat, long, comp, voltage)
    my_ip = arov.get_IP()
    if my_ip is not None:
        hb_data += my_ip.encode('utf-8')

    heartbeat = Packet(MsgType.HEARTBEAT, data=hb_data)
    comm_handler.send_packet(heartbeat)


def shutdown_notify():
    global state
    farewell_packet = Packet(MsgType.INFO, b'Robot shutting down due to low-power')
    comm_handler.send_packet(farewell_packet)
    state = RobotState.LOW_POWER
    send_heartbeat()
    time.sleep(10)

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
