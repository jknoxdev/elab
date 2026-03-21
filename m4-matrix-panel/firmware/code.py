# SPDX-License-Identifier: MIT
# MatrixPortal M4 - Web-controlled RGB Matrix Display + Graphics Modes
# v2 - bitmaptools arrayblit speedup + fingerprint mode

import board
import busio
import displayio
import framebufferio
import rgbmatrix
import terminalio
import bitmaptools
import time
import os
import math
import random

from digitalio import DigitalInOut
from adafruit_display_text import label
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_connection_manager import get_radio_socketpool
from adafruit_httpserver import Server, Request, Response, POST, GET

WIDTH  = 64
HEIGHT = 32

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
# 0-63:   fire gradient
# 64-127: rainbow plasma
# 128:    black
# 129:    white
# 130-145: green shades dim→bright (matrix rain)
# 146:    bright red (alert)
# 147:    dim red (alert bg)

palette = displayio.Palette(256)
palette[128] = 0x000000
palette[129] = 0xFFFFFF
palette[146] = 0xFF0000
palette[147] = 0x330000

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
    g = int(3 + (i / 15.0) * 252)   # floor=3 so dimmest is almost black
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
    "mode":        "rain",
    "text":        "Hello Detroit!",
    "color":       0x00FF00,
    "speed":       0.03,
    "dirty":       True,
    "fingerprint": "A1:B2:C3:D4:E5:F6:07:18:29:3A:4B:5C:6D:7E:8F:90",
}

# ── Graphics Buffers ──────────────────────────────────────────────────────────
heat      = bytearray(WIDTH * HEIGHT)
rain_buf  = bytearray(WIDTH * HEIGHT)   # ← single flat buffer for arrayblit
plasma_t  = 0.0
stars     = [[random.randint(0, WIDTH * 10 - 1),
              random.randint(0, HEIGHT - 1),
              random.randint(1, 5)] for _ in range(55)]
rain_cols = [[random.randint(0, HEIGHT - 1),
              random.randint(3, 10),
              random.random(),
              random.uniform(0.15, 0.40)] for _ in range(WIDTH)]
scroll_x  = WIDTH
alert_tick = 0

# ── WiFi ──────────────────────────────────────────────────────────────────────
esp32_cs    = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

ip = "no wifi"
wifi_ok = False
server = None 

try:
    print("Connecting to WiFi...")
    esp.connect_AP(os.getenv("CIRCUITPY_WIFI_SSID"), os.getenv("CIRCUITPY_WIFI_PASSWORD"))
    ip = esp.pretty_ip(esp.ip_address)
    print(f"Connected! IP: {ip}")
    pool   = get_radio_socketpool(esp)
    server = Server(pool, debug=False)
    wifi_ok = True
except Exception as e:
    print(f"WiFi failed: {e} - running offline")
    wifi_ok = False

# ── HTML ──────────────────────────────────────────────────────────────────────
def build_page(message=""):
    m = state["mode"]
    fp = state["fingerprint"]
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
    .board {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-bottom: 8px; }}
    .board2 {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-bottom: 24px; }}
    .btn {{ padding: 14px 4px; background: #111; color: #0a0;
            border: 1px solid #1a1a1a; font-family: monospace; font-size: 12px;
            cursor: pointer; text-align: center; line-height: 1.6;
            transition: all 0.1s; }}
    .btn:hover {{ border-color: #0f0; color: #0f0; }}
    .btn.active {{ background: #0f0; color: #000; border-color: #0f0; font-weight: bold; }}
    .btn.alert {{ color: #f00; border-color: #300; }}
    .btn.alert:hover {{ border-color: #f00; color: #f00; }}
    .btn.alert.active {{ background: #f00; color: #000; border-color: #f00; }}
    .btn.fp {{ color: #0af; border-color: #013; }}
    .btn.fp:hover {{ border-color: #0af; color: #0af; }}
    .btn.fp.active {{ background: #0af; color: #000; border-color: #0af; }}
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
    const MODES = ['scroll','fire','plasma','stars','rain','alert','fingerprint'];
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
    <button id="btn-fingerprint" class="btn fp" onclick="setMode('fingerprint')">🔑<br>FINGERPRINT</button>
  </div>
  <div class="board2">
    <button id="btn-alert" class="btn alert" onclick="setMode('alert')" style="grid-column: span 3">
      ⚠️ &nbsp; TAMPER ALERT &nbsp; ⚠️
    </button>
  </div>

  <hr>

  <form method="POST" action="/update">
    <label>MESSAGE TEXT</label>
    <input type="text" name="text" value="{state['text']}" maxlength="80">
    <label>FINGERPRINT / DEVICE ID</label>
    <input type="text" name="fingerprint" value="{fp}" maxlength="120">
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
def index(request: Request):
    return Response(request, build_page(), content_type="text/html")

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

def update(request: Request):
    body = request.body.decode("utf-8")
    params = {}
    for pair in body.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k] = v.replace("+", " ").replace("%21","!").replace("%3F","?").replace("%3A",":")
    state["text"]        = params.get("text", state["text"])
    state["fingerprint"] = params.get("fingerprint", state["fingerprint"])
    state["color"]       = int(params.get("color", "00ff00"), 16)
    state["speed"]       = float(params.get("speed", "0.03"))
    state["mode"]        = "scroll"
    state["dirty"]       = True
    return Response(request, build_page(f"&#10003; \"{state['text']}\""), content_type="text/html")

# ── Graphics ──────────────────────────────────────────────────────────────────
def clear_buf(buf, idx=128):
    for i in range(len(buf)):
        buf[i] = idx

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
    for i in range(WIDTH * HEIGHT):
        heat[i] = min(255, heat[i])
        rain_buf[i] = heat[i] * 63 // 255
    bitmaptools.arrayblit(bitmap, rain_buf, x1=0, y1=0, x2=WIDTH, y2=HEIGHT)

def draw_plasma():
    global plasma_t
    for y in range(HEIGHT):
        for x in range(WIDTH):
            v = (math.sin(x / 5.0 + plasma_t) +
                 math.sin(y / 3.0 + plasma_t * 0.9) +
                 math.sin((x + y) / 7.0 + plasma_t * 0.7))
            idx = int((v + 3.0) / 6.0 * 63.0)
            rain_buf[y * WIDTH + x] = 64 + max(0, min(63, idx))
    bitmaptools.arrayblit(bitmap, rain_buf, x1=0, y1=0, x2=WIDTH, y2=HEIGHT)
    plasma_t += 0.12

def draw_stars():
    clear_buf(rain_buf, 128)
    for star in stars:
        star[0] = (star[0] - star[2]) % (WIDTH * 10)
        x = star[0] // 10
        brightness = min(15, star[2] * 3)
        rain_buf[star[1] * WIDTH + x] = 130 + brightness
    bitmaptools.arrayblit(bitmap, rain_buf, x1=0, y1=0, x2=WIDTH, y2=HEIGHT)

def draw_rain():
    # Fade existing pixels in buffer
    for i in range(WIDTH * HEIGHT):
        idx = rain_buf[i]
        if 131 <= idx <= 145:
            if random.randint(0, 1):
                rain_buf[i] = max(130, idx - 1)
        elif idx != 128 and idx < 130:
            rain_buf[i] = 128
    # Advance column heads
    for x in range(WIDTH):
        col = rain_cols[x]
        col[2] += col[3]
        if col[2] >= 1.0:
            col[2] = 0.0
            col[0] = (col[0] + 1) % HEIGHT
            rain_buf[col[0] * WIDTH + x] = 145
    # One native C call to push entire buffer to bitmap
    bitmaptools.arrayblit(bitmap, rain_buf, x1=0, y1=0, x2=WIDTH, y2=HEIGHT)

def draw_alert():
    global alert_tick
    alert_tick += 1
    bg = 146 if (alert_tick // 6) % 2 == 0 else 147
    clear_buf(rain_buf, bg)
    bitmaptools.arrayblit(bitmap, rain_buf, x1=0, y1=0, x2=WIDTH, y2=HEIGHT)

def draw_fingerprint(scroll_x):
    return scroll_x

# ── Main Loop ─────────────────────────────────────────────────────────────────
if wifi_ok:
    from adafruit_httpserver import Route
    server.add_routes([
        Route("/",       GET,  index),
        Route("/mode",   POST, set_mode),
        Route("/update", POST, update),
    ])
    server.start(str(ip))
    print(f"Server at http://{ip}/")


fp_scroll_x = WIDTH
fp_text     = None

while True:
    mode = state["mode"]

    if state["dirty"]:
        alert_tick  = 0
        fp_scroll_x = WIDTH
        if mode == "scroll":
            scroll_label.text  = state["text"]
            scroll_label.color = state["color"]
            scroll_x = WIDTH
            display.root_group = text_group
        elif mode == "fingerprint":
            scroll_label.text  = "KEY: " + state["fingerprint"]
            scroll_label.color = 0x00AAFF
            fp_scroll_x = WIDTH
            display.root_group = text_group
        else:
            clear_buf(rain_buf, 128)
            if mode == "fire":
                for i in range(WIDTH * HEIGHT):
                    heat[i] = 0
            display.root_group = gfx_group
        state["dirty"] = False
    
    if wifi_ok:
        server.poll()

    if mode == "scroll":
        scroll_label.x = scroll_x
        scroll_x -= 1
        if scroll_x < -(len(state["text"]) * 6):
            scroll_x = WIDTH
        time.sleep(state["speed"])

    elif mode == "fingerprint":
        scroll_label.x = fp_scroll_x
        fp_scroll_x -= 1
        fp_text = "KEY: " + state["fingerprint"]
        if fp_scroll_x < -(len(fp_text) * 6):
            fp_scroll_x = WIDTH
        time.sleep(0.02)

    elif mode == "fire":
        draw_fire()
        time.sleep(0.03)

    elif mode == "plasma":
        draw_plasma()
        time.sleep(0.04)

    elif mode == "stars":
        draw_stars()
        time.sleep(0.04)

    elif mode == "rain":
        draw_rain()

    elif mode == "alert":
        draw_alert()
        time.sleep(0.05)