# MatrixPortal M4 — Web-Controlled RGB Matrix Display

CircuitPython firmware for the Adafruit MatrixPortal M4, driving a 64x32 HUB75 RGB LED matrix panel with a small self-hosted web UI for switching display modes.

![Matrix rain effect, close-up](../verification/mpanel-cu.gif)

## Hardware

- Adafruit MatrixPortal M4 (SAMD51 + ESP32 co-processor)
- 64x32 HUB75 RGB matrix panel
- 5V panel power supply, USB-C for the M4

## Modes

Selectable at runtime from the web UI (`/mode` POST) or set as the boot default in `code.py`'s `state["mode"]`:

| Mode | Description |
|---|---|
| `scroll` | Scrolls arbitrary text set via the web form |
| `fire` | Procedural fire/heat simulation |
| `plasma` | Sine-based plasma gradient |
| `stars` | Scrolling starfield |
| `rain` | Matrix-style digital rain (default) |
| `alert` | Flashing red "TAMPER ALERT" banner |
| `fingerprint` | Scrolls a device/key fingerprint string |

![Matrix rain, wider shot](../verification/mpanel-cu2.gif)

## Web UI

On boot, if `CIRCUITPY_WIFI_SSID` / `CIRCUITPY_WIFI_PASSWORD` (set in `settings.toml`) connect successfully, the board starts an `adafruit_httpserver` instance and prints its IP to the serial console. The page at `/` lets you:

- Switch modes (buttons)
- Set scroll text, color, and speed
- Set the `fingerprint` field shown in `fingerprint` mode

If WiFi fails to connect, the board falls back to running the last-set mode offline with no server.

![Matrix panel, extreme close-up](verification/mpanel-ecu.gif)

## Setup

See [`docs/bringup.md`](docs/bringup.md) for flashing CircuitPython, installing libraries, and deploying code to the board.

## Known issues

- **Color channel remap** — this panel currently shows green as blue, blue as magenta, etc. See [`verification/remap-colors.md`](../verification/remap-colors.md). Needs a `rgb_pins` order fix or panel rewire before color is used to convey status (e.g. red = alert, green = OK).
- **`settings.toml` / `.gitignore` mismatch** — the ignore pattern doesn't match the file's actual path; treat any committed `settings.toml` as exposed until this is fixed.
- **`fingerprint` field is arbitrary text set over unauthenticated HTTP** — fine for a demo, not yet wired to any real device identity or auth.

## Other firmware variants in this repo

- `code-rain-orig.py` — earlier matrix-rain-only version
- `code-rain-default-wifi.py` — rain version with WiFi credentials as inline defaults
- `code-text-page.py` — simpler scroll-text-only page, no graphics modes
