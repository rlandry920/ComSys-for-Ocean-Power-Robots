from CommSys.CommMode import CommMode
from CommSys.CommHandler import CommHandler
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
import struct

from WebGUI.WebGUI_Flask import app

HEARTBEAT_TIMER = 15
LOST_TIMER = 60

state_dict = {
    0: "Null",
    1: "Standby",
    2: "Idle",
    3: "Live Control",
    4: "Autonomous Navigation",
    5: "Low Power Mode"
}

fps = FPS()
comm_handler = CommHandler(landbase=True)
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
    comm_handler.start(mode=CommMode.HANDSHAKE)
    print("Connected!")
    webgui_msg("Connected to robot!")

    # Live video WebSocket - https://www.codeinsideout.com/blog/pi/stream-picamera-h264/
    websocketCamera_thread = Thread(target=websocketCamera.serve_forever)
    websocketCamera_thread.start()

    websocketData_thread = Thread(target=websocketData.serve_forever)
    websocketData_thread.start()

    fps.start()

    try:
        while True:
            req_heartbeat()
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
    elif t - LOST_TIMER > heartbeat_ts:
        print("Lost connection to robot!")
        webgui_msg("Lost connection to robot!")
        webgui_state("LOST")
        restart_commhandler()


def restart_commhandler():
    print("Restarting CommHandler...")
    comm_handler.stop()
    print("Connecting to robot...")
    comm_handler.start(mode=CommMode.HANDSHAKE)
    print("Connected!")
    webgui_msg("Connected to robot!")


def digest_packet(packet: Packet):
    global heartbeat_sent
    if packet is None:
        return
    elif packet.type == MsgType.TEXT:
        print(packet.data.decode('utf-8'))
        webgui_msg(packet.data.decode('utf-8'))
    elif packet.type == MsgType.HEARTBEAT:
        latency = time.time() - heartbeat_ts

        state = state_dict[packet.data[0]]
        webgui_state(state)
        lat, long, compass, voltage = struct.unpack('4f', packet.data[1:17])
        webgui_gps(lat, long, compass)
        webgui_voltage(voltage)

        heartbeat_txt = f'Heartbeat from robot received. Latency: %.2f.' % latency
        if len(packet.data) > 17:
            heartbeat_txt += f" Msg: {packet.data[17:].decode('utf-8')}"

        print(heartbeat_txt)
        webgui_msg(heartbeat_txt)

        if state == "Low Power Mode":
            restart_commhandler()  # Robot is entering low power, wait for it to restart communications

    elif packet.type == MsgType.IMAGE:
        # Broadcast h264 encoded image
        print(f'Received image packet. Length: {packet.length}')
        websocketCamera.manager.broadcast(packet.data, binary=True)
    elif packet.type == MsgType.HANDSHAKE:
        print(f'New connection with robot established.')
        webgui_msg("New connection with robot established.")
        heartbeat_sent = False
    else:
        print(f'Received packet (ID: {packet.id} of type {packet.type})')


def webgui_msg(txt: str):
    msg = {
        "type": "message",
        "message": txt
    }
    websocketData.manager.broadcast(json.dumps(msg))


def webgui_gps(lat: float, long: float, compass: float):
    msg = {
        "type": "gps",
        "lat": lat,
        "long": long,
        "compass": compass
    }
    websocketData.manager.broadcast(json.dumps(msg))


def webgui_voltage(voltage: float):
    msg = {
        "type": "voltage",
        "voltage": voltage
    }
    websocketData.manager.broadcast(json.dumps(msg))


def webgui_state(state: str):
    msg = {
        "type": "state",
        "state": state
    }
    websocketData.manager.broadcast(json.dumps(msg))


if __name__ == '__main__':
    try:
        Thread(target=main).start()
        app.run(host="0.0.0.0", port=5000)
    except KeyboardInterrupt:
        pass
