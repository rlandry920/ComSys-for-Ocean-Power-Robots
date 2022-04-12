from CommSys.CommHandler import CommHandler, CommMode
from CommSys.Packet import Packet, MsgType
from SensorLib.FPS import FPS
import logging
import json
import time
from threading import Thread
from wsgiref.simple_server import *
from ws4py.server.wsgirefserver import WSGIServer, WebSocketWSGIRequestHandler
from ws4py.server.wsgiutils import WebSocketWSGIApplication
from ws4py.websocket import WebSocket

from WebGUI.WebGUI_Flask import app

HEARTBEAT_TIMER = 15

fps = FPS()
comm_handler = CommHandler(reliable_img=False)
app.config['commHandler'] = comm_handler
heartbeat_ts = 0
heartbeat_sent = False

logging.basicConfig(filename='landbase.log',
                    level=logging.DEBUG,
                    format='%(asctime)s | %(funcName)s | %(levelname)s | %(message)s')

logger = logging.getLogger(__name__)
websocketData = make_server('', 8000, server_class=WSGIServer,
                            handler_class=WebSocketWSGIRequestHandler,
                            app=WebSocketWSGIApplication(handler_cls=WebSocket))
websocketData.initialize_websockets_manager()

app.config['websocketData'] = websocketData

websocketCamera = make_server('', 9000, server_class=WSGIServer,
                              handler_class=WebSocketWSGIRequestHandler,
                              app=WebSocketWSGIApplication(handler_cls=WebSocket))
websocketCamera.initialize_websockets_manager()


def main():
    logger.info("Landbase starting...")
    print("Connecting to robot...")
    comm_handler.start(mode=CommMode.SATELLITE)
    print("Connected!")
    webgui_msg("Connected to robot!")

    # Live video WebSocket - https://www.codeinsideout.com/blog/pi/stream-picamera-h264/
    websocketCamera_thread = Thread(target=websocketCamera.serve_forever)
    websocketCamera_thread.start()

    websocketData_thread = Thread(target=websocketData.serve_forever)
    websocketData_thread.start()

    fps.start()

    lat = 37.2284
    long = -80.4234
    try:
        while True:
            # req_heartbeat()
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


def req_heartbeat():
    global heartbeat_sent, heartbeat_ts
    t = time.time()
    if t - HEARTBEAT_TIMER > heartbeat_ts and not heartbeat_sent:
        print("Sending heartbeat request...")
        heartbeat_req = Packet(MsgType.HEARTBEAT_REQ)
        comm_handler.send_packet(heartbeat_req)
        heartbeat_ts = t


def digest_packet(packet: Packet):
    global heartbeat_sent
    if packet is None:
        return
    elif packet.type == MsgType.TEXT:
        print(packet.data.decode('utf-8'))
        webgui_msg(packet.data.decode('utf-8'))
    elif packet.type == MsgType.HEARTBEAT:
        latency = time.time() - heartbeat_ts
        heartbeat_txt = f'Heartbeat from robot received. Latency: %.2f. Msg: {packet.data.decode("utf-8")}' % latency
        print(heartbeat_txt)
        webgui_msg(heartbeat_txt)
    elif packet.type == MsgType.IMAGE:
        # Broadcast h264 encoded image
        print(f'Received image packet. Length: {packet.length}')
        websocketCamera.manager.broadcast(packet.data, binary=True)
    elif packet.type == MsgType.HANDSHAKE:
        print(f'New connection with robot established.')
        webgui_msg("New connection with robot established.")
    else:
        print(f'Received packet (ID: {packet.id} of type {packet.type})')


def webgui_msg(txt: str):
    msg = {
        "type": "message",
        "message": txt
    }
    websocketData.manager.broadcast(json.dumps(msg))


if __name__ == '__main__':
    try:
        Thread(target=main).start()
        app.run(host="0.0.0.0", port=5000)
    except KeyboardInterrupt:
        pass
