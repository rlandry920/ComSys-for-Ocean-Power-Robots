import logging
from SensorLib.CameraHandler import CameraHandler
from CommSys.CommHandler import CommHandler

logging.basicConfig(filename='robot.log',
                    level=logging.DEBUG,
                    format='%(asctime)s | %(funcName)s | %(levelname)s | %(message)s')

comm_handler = CommHandler()
cam_handler = CameraHandler(comm_handler.get_egress_tuple())

LIVE_VIDEO = True


def main():
    logging.info("Robot Initializing....")
    comm_handler.start()
    cam_handler.start()
    logging.info("Robot Initialized!")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        pass
    except Exception as e:
        pass
    finally:
        logging.info("Robot stopping...")
        comm_handler.stop()
        cam_handler.stop()


if __name__ == "__main__":
    main()
