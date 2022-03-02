// player -- based on https://www.codeinsideout.com/blog/pi/stream-picamera-h264/
import "./Decoder.js"
import "./YUVCanvas.js"
import "./Player.js"

window.player = new Player({
  useWorker: true,
  webgl: 'auto',
  size: { width: 848, height: 480 }
})
var playerElement = document.getElementById('viewer')
playerElement.appendChild(window.player.canvas)
// Websocket
var wsUri =
  window.location.protocol.replace(/http/, 'ws')
  + '//' + window.location.hostname + ':9000'
var ws = new WebSocket(wsUri)
ws.binaryType = 'arraybuffer'
ws.onopen = function (e) {
  console.log('Client connected')
  ws.onmessage = function (msg) {
    // decode stream
    window.player.decode(new Uint8Array(msg.data));
  }
}
ws.onclose = function (e) {
  console.log('Client disconnected')
}