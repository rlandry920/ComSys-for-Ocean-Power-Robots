import logging
from SensorLib.CameraHandler import CameraHandler
from CommSys.CommHandler import CommHandler, CommMode
from CommSys.Packet import MsgType, Packet

logging.basicConfig(filename='robot.log',
                    level=logging.DEBUG,
                    format='%(asctime)s | %(funcName)s | %(levelname)s | %(message)s')

comm_handler = CommHandler()
cam_handler = CameraHandler(comm_handler)

LIVE_VIDEO = True


def tx_window_test():
    comm_handler.start(mode=CommMode.DEBUG)

    for i in range(15):
        comm_handler.send_packet(Packet(ptype=MsgType.TEXT, pid=0, data=(b'Message #'+str(i).encode('utf-8'))))

    try:
        while True:
            pass
    except KeyboardInterrupt:
        pass
    finally:
        comm_handler.stop()

def main():
    logging.info("Robot starting...")
    handshake_packet = Packet(ptype=MsgType.HANDSHAKE, pid=0, data=b'')
    comm_handler.send_packet(handshake_packet)
    comm_handler.start()

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
    else:
        print(f'Received packet (ID: {packet.id} of type {packet.type})')


if __name__ == "__main__":
    main()
