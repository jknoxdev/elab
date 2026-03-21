# SPDX-License-Identifier: MIT
# MatrixPortal M4 - Web-controlled RGB Matrix Display + Graphics Modes

import board
import busio
import displayio
import framebufferio
import rgbmatrix
import terminalio
import time
import os
import math
import random
import bitmaptools

from digitalio import DigitalInOut
from adafruit_display_text import label
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_connection_manager import get_radio_socketpool
from adafruit_httpserver import Server, Request, Response, POST, GET

WIDTH  = 64
HEIGHT = 32

rain_buf = bytearray(WIDTH * HEIGHT) 

# ── Matrix Setup ──────────────────────────────────────────────────────────────
displayio.release_displays()
matrix = rgbmatrix.RGBMatrix(
    width=WIDTH, height=HEIGHT, bit_depth=4,
    rgb_pins=[board.MTX_R1, board.MTX_B1, board.MTX_G1,
              board.MTX_R2, board.MTX_B2, board.MTX_G2],
    addr_pins=[board.MTX_ADDRA, board.MTX_ADDRB,
               board.MTX_ADDRC, board.MTX_ADDRD],
    clock_pin=board.MTX_CLK,
    latch_pin=board.MTX_LAT,
    output_enable_pin=board.MTX_OE,
)
display = framebufferio.FramebufferDisplay(matrix, auto_refresh=True, rotation=180)

# ── Palette ───────────────────────────────────────────────────────────────────
# 0-63:   fire gradient (black → dark red → red → orange → yellow → white)
# 64-127: rainbow (plasma)
# 128:    black
# 129:    white
# 130-145: green shades (matrix rain, dim→bright)

palette = displayio.Palette(256)
palette[128] = 0x000000
palette[129] = 0xFFFFFF

for i in range(64):
    t = i / 63.0
    if t < 0.4:
        r = int(t / 0.4 * 180); g = 0; b = 0
    elif t < 0.7:
        r = 180 + int((t - 0.4) / 0.3 * 75)
        g = int((t - 0.4) / 0.3 * 120); b = 0
    else:
        r = 255; g = 120 + int((t - 0.7) / 0.3 * 135)
        b = int((t - 0.7) / 0.3 * 220)
    palette[i] = (r << 16) | (g << 8) | b

for i in range(64):
    h = i / 64.0 * 6.0
    x = int((1 - abs(h % 2 - 1)) * 200)
    v = 200
    if   h < 1: r, g, b = v, x, 0
    elif h < 2: r, g, b = x, v, 0
    elif h < 3: r, g, b = 0, v, x
    elif h < 4: r, g, b = 0, x, v
    elif h < 5: r, g, b = x, 0, v
    else:       r, g, b = v, 0, x
    palette[64 + i] = (r << 16) | (g << 8) | b

for i in range(16):
    g = int(3 + (i / 15.0) * 235)
    palette[130 + i] = (0 << 16) | (g << 8) | 0

# ── Display Groups ────────────────────────────────────────────────────────────
bitmap    = displayio.Bitmap(WIDTH, HEIGHT, 256)
tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
gfx_group = displayio.Group()
gfx_group.append(tile_grid)

scroll_label = label.Label(
    terminalio.FONT, text="Hello Detroit!", color=0x00FF00, x=WIDTH, y=HEIGHT // 2
)
text_group = displayio.Group()
text_group.append(scroll_label)

display.root_group = text_group

# ── App State ─────────────────────────────────────────────────────────────────
state = {
    "mode":  "scroll",
    "text":  "Hello Detroit!",
    "color": 0x00FF00,
    "speed": 0.03,
    "dirty": True,
}

# ── Graphics State ────────────────────────────────────────────────────────────
heat      = bytearray(WIDTH * HEIGHT)
plasma_t  = 0.0
stars     = [[random.randint(0, WIDTH * 10 - 1),
              random.randint(0, HEIGHT - 1),
              random.randint(1, 5)] for _ in range(55)]
# rain_cols = [[random.randint(0, HEIGHT - 1),
#               random.randint(3, 10),
#               random.random()] for _ in range(WIDTH)]
rain_cols = [[random.randint(0, HEIGHT - 1),    # ← this line
              random.randint(3, 10),
              random.random(),
              random.uniform(0.15, 0.35)] for _ in range(WIDTH)] 

scroll_x  = WIDTH

# ── WiFi ──────────────────────────────────────────────────────────────────────
esp32_cs    = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

print("Connecting to WiFi...")
esp.connect_AP(os.getenv("CIRCUITPY_WIFI_SSID"), os.getenv("CIRCUITPY_WIFI_PASSWORD"))
ip = esp.pretty_ip(esp.ip_address)
print(f"Connected! IP: {ip}")

pool   = get_radio_socketpool(esp)
server = Server(pool, debug=False)

# ── HTML ──────────────────────────────────────────────────────────────────────
def build_page(message=""):
    m = state["mode"]
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Matrix Control</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: monospace; background: #0a0a0a; color: #0f0;
            max-width: 520px; margin: 32px auto; padding: 16px; }}
    h1 {{ letter-spacing: 6px; font-size: 22px; margin-bottom: 2px; }}
    .sub {{ color: #333; font-size: 11px; margin-bottom: 24px; }}
    .board {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin-bottom: 24px; }}
    .btn {{ padding: 14px 4px; background: #111; color: #0a0;
            border: 1px solid #1a1a1a; font-family: monospace; font-size: 12px;
            cursor: pointer; text-align: center; line-height: 1.6;
            transition: all 0.1s; }}
    .btn:hover {{ border-color: #0f0; color: #0f0; }}
    .btn.active {{ background: #0f0; color: #000; border-color: #0f0; font-weight: bold; }}
    hr {{ border: none; border-top: 1px solid #1a1a1a; margin: 20px 0; }}
    label {{ display: block; font-size: 10px; color: #444; margin-bottom: 4px; letter-spacing: 2px; }}
    input, select {{ width: 100%; padding: 8px; margin-bottom: 14px;
                     background: #111; color: #0f0; border: 1px solid #1f1f1f;
                     font-family: monospace; font-size: 13px; }}
    .go {{ width: 100%; padding: 12px; background: #0f0; color: #000;
           border: none; font-family: monospace; font-size: 15px;
           font-weight: bold; cursor: pointer; letter-spacing: 3px; }}
    .status {{ color: #ff0; margin-top: 14px; font-size: 12px; min-height: 18px; }}
  </style>
  <script>
    const MODES = ['scroll','fire','plasma','stars','rain'];
    function setMode(mode) {{
      fetch('/mode', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
        body: 'mode=' + mode
      }}).then(() => {{
        MODES.forEach(m => document.getElementById('btn-'+m).classList.remove('active'));
        document.getElementById('btn-'+mode).classList.add('active');
      }});
    }}
    window.onload = () => document.getElementById('btn-{m}').classList.add('active');
  </script>
</head>
<body>
  <h1>[ MATRIX ]</h1>
  <p class="sub">IP: {ip}</p>

  <div class="board">
    <button id="btn-scroll" class="btn" onclick="setMode('scroll')">📜<br>SCROLL</button>
    <button id="btn-fire"   class="btn" onclick="setMode('fire')">🔥<br>FIRE</button>
    <button id="btn-plasma" class="btn" onclick="setMode('plasma')">🌈<br>PLASMA</button>
    <button id="btn-stars"  class="btn" onclick="setMode('stars')">✨<br>STARS</button>
    <button id="btn-rain"   class="btn" onclick="setMode('rain')">💊<br>RAIN</button>
  </div>

  <hr>

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
    <button class="go" type="submit">&#9654; SEND TO MATRIX</button>
  </form>
  <p class="status">{message}</p>
</body>
</html>"""

# ── Routes ────────────────────────────────────────────────────────────────────
@server.route("/", GET)
def index(request: Request):
    return Response(request, build_page(), content_type="text/html")

@server.route("/mode", POST)
def set_mode(request: Request):
    body = request.body.decode("utf-8")
    params = {}
    for pair in body.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k] = v
    state["mode"]  = params.get("mode", "scroll")
    state["dirty"] = True
    return Response(request, '{"ok":true}', content_type="application/json")

@server.route("/update", POST)
def update(request: Request):
    body = request.body.decode("utf-8")
    params = {}
    for pair in body.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k] = v.replace("+", " ").replace("%21", "!").replace("%3F", "?")
    state["text"]  = params.get("text", state["text"])
    state["color"] = int(params.get("color", "00ff00"), 16)
    state["speed"] = float(params.get("speed", "0.03"))
    state["mode"]  = "scroll"
    state["dirty"] = True
    return Response(
        request,
        build_page(f"&#10003; \"{state['text']}\""),
        content_type="text/html"
    )

# ── Graphics ──────────────────────────────────────────────────────────────────
def clear_bitmap(idx=128):
    for y in range(HEIGHT):
        for x in range(WIDTH):
            bitmap[x, y] = idx

def draw_fire():
    for i in range(WIDTH * HEIGHT):
        c = heat[i]
        if c > 0:
            heat[i] = max(0, c - random.randint(0, 3))
    for y in range(HEIGHT - 1, 0, -1):
        for x in range(WIDTH):
            avg = (heat[y * WIDTH + x] +
                   heat[y * WIDTH + (x - 1) % WIDTH] +
                   heat[y * WIDTH + (x + 1) % WIDTH] +
                   heat[(y - 1) * WIDTH + x]) // 4
            heat[(y - 1) * WIDTH + x] = avg
    for x in range(WIDTH):
        heat[(HEIGHT - 1) * WIDTH + x] = random.randint(180, 255)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            bitmap[x, y] = heat[y * WIDTH + x] * 63 // 255

def draw_plasma():
    global plasma_t
    for y in range(HEIGHT):
        for x in range(WIDTH):
            v = (math.sin(x / 5.0 + plasma_t) +
                 math.sin(y / 3.0 + plasma_t * 0.9) +
                 math.sin((x + y) / 7.0 + plasma_t * 0.7))
            idx = int((v + 3.0) / 6.0 * 63.0)
            bitmap[x, y] = 64 + max(0, min(63, idx))
    plasma_t += 0.12

def draw_stars():
    clear_bitmap(128)
    for star in stars:
        star[0] = (star[0] - star[2]) % (WIDTH * 10)
        x = star[0] // 10
        brightness = min(15, star[2] * 3)
        bitmap[x, star[1]] = 130 + brightness

def draw_rain():
    # Fade existing pixels
    for y in range(HEIGHT):
        for x in range(WIDTH):
            idx = bitmap[x, y]
            if 131 <= idx <= 145:
                if random.randint(0, 1):  # 50% chance to fade each frame
                    bitmap[x, y] = max(130, idx - 1)
            elif idx != 128 and idx < 130:
                bitmap[x, y] = 128
    # Advance column heads
    for x in range(WIDTH):
        col = rain_cols[x]
        # col[2] += 0.25
        col[2] += col[3]
        if col[2] >= 1.0:
            col[2] = 0.0
            col[0] = (col[0] + 1) % HEIGHT
            bitmap[x, col[0]] = 145  # bright head

# ── Main Loop ─────────────────────────────────────────────────────────────────
server.start(str(ip))
print(f"Server at http://{ip}/")

while True:
    mode = state["mode"]

    if state["dirty"]:
        if mode == "scroll":
            scroll_label.text  = state["text"]
            scroll_label.color = state["color"]
            scroll_x = WIDTH
            display.root_group = text_group
        else:
            clear_bitmap(128)
            # Reset fire heat on entry
            if mode == "fire":
                for i in range(WIDTH * HEIGHT):
                    heat[i] = 0
            display.root_group = gfx_group
        state["dirty"] = False

    server.poll()

    if mode == "scroll":
        scroll_label.x = scroll_x
        scroll_x -= 1
        if scroll_x < -(len(state["text"]) * 6):
            scroll_x = WIDTH
        time.sleep(state["speed"])

    elif mode == "fire":
        draw_fire()
        time.sleep(0.02)

    elif mode == "plasma":
        draw_plasma()
        time.sleep(0.02)

    elif mode == "stars":
        draw_stars()
        time.sleep(0.02)

    elif mode == "rain":
        draw_rain()
        # time.sleep(0.003)
