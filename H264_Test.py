from WebGUI.WebGUI_Flask import app
from wsgiref.simple_server import *
from ws4py.server.wsgirefserver import WSGIServer, WebSocketWSGIRequestHandler
from ws4py.server.wsgiutils import WebSocketWSGIApplication
from ws4py.websocket import WebSocket
from SensorLib.FrameBuffer import FrameBuffer

import picamera
from threading import Thread, Condition

camera = picamera.PiCamera(resolution='640x480', framerate=24)


def main():
    print(camera)

    # Live video WebSocket - https://www.codeinsideout.com/blog/pi/stream-picamera-h264/
    websocketd = make_server('', 9000, server_class=WSGIServer,
                             handler_class=WebSocketWSGIRequestHandler,
                             app=WebSocketWSGIApplication(handler_cls=WebSocket))
    websocketd.initialize_websockets_manager()
    websocketd_thread = Thread(target=websocketd.serve_forever)

    broadcasting = True
    frame_buffer = FrameBuffer()
    camera.start_recording(frame_buffer, format='h264', profile="baseline", bitrate=115200)

    try:
        websocketd_thread.start()
        while broadcasting:
            with frame_buffer.condition:
                frame_buffer.condition.wait()
                websocketd.manager.broadcast(frame_buffer.frame, binary=True)
    finally:
        camera.close()
        websocketd_thread.join()


if __name__ == "__main__":
    Thread(target=main).start()
    app.run(host="0.0.0.0", port=5000)
