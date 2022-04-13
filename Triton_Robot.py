import logging
from logging.handlers import RotatingFileHandler
from SensorLib.CameraHandler import CameraHandler
from CommSys.CommMode import CommMode
from CommSys.CommHandler import CommHandler
from CommSys.Packet import MsgType, Packet
from CommSys.AROVHandler import AROVHandler
import picamera
import struct
import ME_Integration.escController as esc
from systemd.journal import JournaldLogHandler
import time

MOTOR_TIMEOUT = 2

motor_ts = 0
motor_on = False

comm_handler = CommHandler(landbase=False)
cam = picamera.PiCamera(resolution='320x240', framerate=5)
cam_handler = CameraHandler(comm_handler, cam)
arov = AROVHandler()

live_control = False


def main():
    logger.info("Robot starting...")
    logger.info("Arming ESCs...")
    esc.arm()
    logger.info("ESCs Armed!")

    logger.info("Connecting to landbase...")
    comm_handler.start(CommMode.HANDSHAKE)
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
    global live_control, motor_ts, motor_on
    if packet is None:
        return
    elif packet.type == MsgType.TEXT:
        logger.info(f'Received text message: {packet.data.decode("utf-8")}')
    elif packet.type == MsgType.HEARTBEAT_REQ:
        logger.info(f'Received heartbeat request')
        my_ip = arov.get_IP()
        heartbeat = Packet(MsgType.HEARTBEAT, data=my_ip.encode('utf-8'))
        comm_handler.send_packet(heartbeat)
    elif packet.type == MsgType.MTR_CMD:
        left, right = struct.unpack('2f', packet.data[0:8])
        logger.info(f'Received motor command: LEFT={str(left)} RIGHT={str(right)}')
        if live_control:
            motor_on = True
            motor_ts = time.time()
            esc.setSpeed(esc.ESC_LEFT, left)
            esc.setSpeed(esc.ESC_RIGHT, right)
        else:
            logger.warning(f"Live control hasn't been enable yet!")
    elif packet.type == MsgType.CTRL_REQ:
        enable = (packet.data == b'\x01')
        if enable and enable != live_control:
            logger.info("Starting live control.")
            cam_handler.start()
        elif not enable and enable != live_control:
            logger.info("Stopping live control.")
            cam_handler.stop()

        live_control = enable
    else:
        logger.info(f'Received packet (ID: {packet.id} of type {packet.type})')


def check_motors():
    global motor_ts, motor_on
    t = time.time()
    if motor_on and t - MOTOR_TIMEOUT > motor_ts:
        esc.setSpeed(esc.ESC_LEFT, 0)
        esc.setSpeed(esc.ESC_RIGHT, 0)
        motor_on = False


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
