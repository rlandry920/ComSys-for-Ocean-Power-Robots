from CommSys.CommHandler import CommHandler, CommMode
from CommSys.Packet import Packet, MsgType
from SensorLib.FPS import FPS
import logging
import json
from threading import Thread
from wsgiref.simple_server import *
from ws4py.server.wsgirefserver import WSGIServer, WebSocketWSGIRequestHandler
from ws4py.server.wsgiutils import WebSocketWSGIApplication
from ws4py.websocket import WebSocket

from WebGUI.WebGUI_Flask import app

fps = FPS()
comm_handler = CommHandler()
app.config['commHandler'] = comm_handler

logging.basicConfig(filename='landbase.log',
                    level=logging.DEBUG,
                    format='%(asctime)s | %(funcName)s | %(levelname)s | %(message)s')

logger = logging.getLogger(__name__)
websocketData = make_server('', 8000, server_class=WSGIServer,
                            handler_class=WebSocketWSGIRequestHandler,
                            app=WebSocketWSGIApplication(handler_cls=WebSocket))

websocketCamera = make_server('', 9000, server_class=WSGIServer,
                              handler_class=WebSocketWSGIRequestHandler,
                              app=WebSocketWSGIApplication(handler_cls=WebSocket))


def main():
    logger.info("Landbase starting...")
    comm_handler.start(mode=CommMode.HANDSHAKE)

    # Live video WebSocket - https://www.codeinsideout.com/blog/pi/stream-picamera-h264/
    websocketCamera.initialize_websockets_manager()
    websocketCamera_thread = Thread(target=websocketCamera.serve_forever)
    websocketCamera_thread.start()

    websocketData.initialize_websockets_manager()
    websocketData_thread = Thread(target=websocketData.serve_forever)
    websocketData_thread.start()

    fps.start()

    lat = 37.2284
    long = -80.4234
    try:
        while True:
            if comm_handler.recv_flag():
                packet = comm_handler.recv_packet()
                digest_packet(packet)
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Landbase stopping...")
        comm_handler.stop()
        fps.stop()

        logger.info("[INFO] elasped time: {:.2f}".format(fps.elapsed()))
        logger.info("[INFO] approx. FPS: {:.2f}".format(fps.fps()))


def digest_packet(packet: Packet):
    if packet is None:
        return
    elif packet.type == MsgType.TEXT:
        print(packet.data.decode('utf-8'))
    elif packet.type == MsgType.IMAGE:
        # Broadcast h264 encoded image
        print(f'Received image packet. Length: {packet.length}')
        websocketCamera.manager.broadcast(packet.data, binary=True)
    else:
        print(f'Received packet (ID: {packet.id} of type {packet.type})')


if __name__ == '__main__':
    try:
        Thread(target=main).start()
        app.run(host="0.0.0.0", port=5000)
    except KeyboardInterrupt:
        pass