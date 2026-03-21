# SPDX-License-Identifier: MIT
# MatrixPortal M4 - Web-controlled RGB Matrix Display
# Hit the board's IP in a browser to change text/color/speed

import board
import busio
import displayio
import framebufferio
import rgbmatrix
import terminalio
import time
import os

from digitalio import DigitalInOut
from adafruit_display_text import label
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_connection_manager import get_radio_socketpool
from adafruit_httpserver import Server, Request, Response, POST, GET

# ── Matrix Setup ──────────────────────────────────────────────────────────────
displayio.release_displays()

matrix = rgbmatrix.RGBMatrix(
    width=64, height=32, bit_depth=4,
    rgb_pins=[board.MTX_R1, board.MTX_G1, board.MTX_B1,
              board.MTX_R2, board.MTX_G2, board.MTX_B2],
    addr_pins=[board.MTX_ADDRA, board.MTX_ADDRB,
               board.MTX_ADDRC, board.MTX_ADDRD],
    clock_pin=board.MTX_CLK,
    latch_pin=board.MTX_LAT,
    output_enable_pin=board.MTX_OE,
    # tile=-1,  # ← flip it  and storage.erase_filesystem()
)
display = framebufferio.FramebufferDisplay(matrix, auto_refresh=True)

# ── Display State ─────────────────────────────────────────────────────────────
state = {
    "text": "Hello Detroit!",
    "color": 0x00FF00,
    "speed": 0.03,
    "dirty": True,
}

group = displayio.Group()
scroll_label = label.Label(
    terminalio.FONT,
    text=state["text"],
    color=state["color"],
    x=64,
    y=16,
)
group.append(scroll_label)
display.root_group = group

# ── ESP32 SPI WiFi Setup ──────────────────────────────────────────────────────
esp32_cs    = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

print("Connecting to WiFi...")
esp.connect_AP(
    os.getenv("CIRCUITPY_WIFI_SSID"),
    os.getenv("CIRCUITPY_WIFI_PASSWORD")
)
ip = esp.pretty_ip(esp.ip_address)
print(f"Connected! IP: {ip}")

pool = get_radio_socketpool(esp)

# ── HTTP Server ───────────────────────────────────────────────────────────────
server = Server(pool, debug=False)

# ── HTML UI ───────────────────────────────────────────────────────────────────
def build_page(message=""):
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Matrix Control</title>
  <style>
    body {{ font-family: monospace; background: #111; color: #0f0;
            max-width: 480px; margin: 40px auto; padding: 16px; }}
    h1 {{ color: #0f0; letter-spacing: 4px; }}
    input, select {{ width: 100%; padding: 8px; margin: 8px 0 16px 0;
                     background: #222; color: #0f0; border: 1px solid #0f0;
                     font-family: monospace; font-size: 14px; box-sizing: border-box; }}
    button {{ width: 100%; padding: 10px; background: #0f0; color: #111;
              border: none; font-family: monospace; font-size: 16px;
              font-weight: bold; cursor: pointer; letter-spacing: 2px; }}
    .status {{ color: #ff0; margin-top: 12px; }}
    label {{ font-size: 12px; color: #aaa; }}
  </style>
</head>
<body>
  <h1>[ MATRIX ]</h1>
  <form method="POST" action="/update">
    <label>MESSAGE TEXT</label>
    <input type="text" name="text" value="{state['text']}" maxlength="80">
    <label>COLOR</label>
    <select name="color">
      <option value="00ff00">Green</option>
      <option value="ff0000">Red</option>
      <option value="0080ff">Blue</option>
      <option value="ffff00">Yellow</option>
      <option value="ff8000">Orange</option>
      <option value="ff00ff">Magenta</option>
      <option value="ffffff">White</option>
      <option value="00ffff">Cyan</option>
    </select>
    <label>SCROLL SPEED</label>
    <select name="speed">
      <option value="0.01">Fast</option>
      <option value="0.03">Normal</option>
      <option value="0.07">Slow</option>
      <option value="0.15">Crawl</option>
    </select>
    <button type="submit">&#9654; SEND TO MATRIX</button>
  </form>
  <p class="status">{message}</p>
  <p style="color:#444;font-size:11px;">Board IP: {ip}</p>
</body>
</html>"""

# ── Routes ────────────────────────────────────────────────────────────────────
@server.route("/", GET)
def index(request: Request):
    return Response(request, build_page(), content_type="text/html")

@server.route("/update", POST)
def update(request: Request):
    body = request.body.decode("utf-8")
    params = {}
    for pair in body.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k] = v.replace("+", " ").replace("%21", "!").replace("%3F", "?")

    state["text"] = params.get("text", state["text"])
    state["color"] = int(params.get("color", "00ff00"), 16)
    state["speed"] = float(params.get("speed", "0.03"))
    state["dirty"] = True

    return Response(
        request,
        build_page(f"&#10003; Updated: \"{state['text']}\""),
        content_type="text/html"
    )

# ── Main Loop ─────────────────────────────────────────────────────────────────
server.start(str(ip))
print(f"Server running at http://{ip}/")

scroll_x = display.width

while True:
    if state["dirty"]:
        scroll_label.text = state["text"]
        scroll_label.color = state["color"]
        scroll_x = display.width
        state["dirty"] = False

    scroll_label.x = scroll_x
    scroll_x -= 1
    if scroll_x < -(len(state["text"]) * 6):
        scroll_x = display.width

    server.poll()
    time.sleep(state["speed"])
