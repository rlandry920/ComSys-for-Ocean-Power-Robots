import logging
from SensorLib.CameraHandler import CameraHandler
from CommSys.CommHandler import CommHandler, CommMode
from CommSys.Packet import MsgType, Packet
import picamera
import struct
import time
import ME_Integration.escController as esc

logging.basicConfig(filename='robot.log',
                    level=logging.DEBUG,
                    format='%(asctime)s | %(funcName)s | %(levelname)s | %(message)s')


comm_handler = CommHandler()
cam = picamera.PiCamera(resolution='320x240', framerate=1)
cam_handler = CameraHandler(comm_handler, cam)

LIVE_VIDEO = True

def main():
    logging.info("Robot starting...")
    print("Arming ESCs...")
    esc.arm()
    print("ESCs armed!")
    print("Testing forwards...")
    esc.drive_motor(0.3)
    time.sleep(2)
    print("Testing backwards...")
    esc.drive_motor(-0.3)
    time.sleep(2)
    esc.drive_motor(0)
    print("Motors tested!")

    handshake_packet = Packet(ptype=MsgType.HANDSHAKE)
    comm_handler.send_packet(handshake_packet)
    print("Connecting to landbase...")
    comm_handler.start(CommMode.HANDSHAKE)
    print("Connection with landbase established!")

    msg1 = b'SYNC'
    msg2 = b'HELLO_WORLD!'
    msg3 = b' Lorem ipsum dolor sit amet, consectetur adipiscing elit. Proin mattis aliquet nisi at hendrerit. Aenean in' \
           b'terdum pulvinar nibh, vel molestie metus dapibus sit amet. Donec facilisis egestas eros tempus suscipit. Al' \
           b'iquam sed lacus enim. Nulla faucibus semper neque at molestie. Donec sit amet tempus dui. In hac habitasse ' \
           b'platea dictumst. Quisque vulputate auctor lacus, non mattis tellus porta sed. Vestibulum sodales porttitor ' \
           b'nibh, eget ultrices ligula lacinia nec. Nullam nec eleifend diam, in laoreet nibh.' \
           b'\n\n' \
           b'Morbi felis urna, hendrerit a est nec, varius ultrices ex. Proin ultricies erat in sodales malesuada. In po' \
           b'suere tortor vitae velit cursus vestibulum ac quis enim. Fusce imperdiet lacus eget mauris placerat, et lao' \
           b'reet nulla dignissim. Nulla sollicitudin diam vitae ante vulputate tempor. Ut bibendum neque ut orci consec' \
           b'tetur, a finibus felis vulputate. Integer elementum mauris et erat viverra, vestibulum fringilla mauris pel' \
           b'lentesque. Nullam volutpat a mi at commodo. Morbi metus arcu, euismod sit amet maximus id, semper scelerisq' \
           b'ue dui. Vivamus scelerisque massa vel ex hendrerit, id aliquet odio ultricies. Nunc fringilla id sapien a m' \
           b'alesuada. Sed accumsan semper laoreet. Sed pharetra sodales sodales. '

    pkt1 = Packet(MsgType.TEXT, 0, msg1)
    pkt2 = Packet(MsgType.TEXT, 0, msg2)
    pkt3 = Packet(MsgType.TEXT, 0, msg3)

    comm_handler.send_packet(pkt1)
    comm_handler.send_packet(pkt2)
    comm_handler.send_packet(pkt3)

    cam_handler.start()

    try:
        while True:
            digest_packet(comm_handler.recv_packet())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        pass
    finally:
        logging.info("Robot stopping...")
        comm_handler.stop()
        cam_handler.stop()


def digest_packet(packet: Packet):
    if packet is None:
        return
    elif packet.type == MsgType.TEXT:
        print(packet.data.decode('utf-8'))
    elif packet.type == MsgType.MTR_CMD:
        print(packet.length)
        left, right = struct.unpack('2f', packet.data)
        print(f'Recieved motor cmd (ID: {packet.id} LEFT: {str(left)} RIGHT: {str(right)})')
        esc.drive_motor(left)
    else:
        print(f'Received packet (ID: {packet.id} of type {packet.type})')


if __name__ == "__main__":
    main()
