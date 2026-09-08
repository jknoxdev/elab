# MatrixPortal M4 — Dev Env Bringup (macOS)

Board: Adafruit MatrixPortal M4 (SAMD51 + ESP32 co-processor) driving a 64x32 HUB75 RGB matrix panel.

## 1. Flash CircuitPython

- Double-tap the reset button on the M4 → boots into UF2 bootloader, mounts as `MATRIXBOOT`.
- Drag `firmware/builds/adafruit-circuitpython-matrixportal_m4-en_US-10.1.4.uf2` onto `MATRIXBOOT`.
  - (10.2.0-alpha.1 also present in builds/ — stick to 10.1.4 stable unless testing a specific alpha feature.)
- Board auto-reboots and remounts as `CIRCUITPY`.

## 2. Install CircuitPython libraries

`code.py` imports these external (non-core) libs — not bundled with CircuitPython itself:
- `adafruit_display_text`
- `adafruit_esp32spi`
- `adafruit_connection_manager`
- `adafruit_httpserver`
- `adafruit_bus_device` (pulled in as a dependency of esp32spi)

Easiest path — `circup`:
```
pip install circup
circup install adafruit_display_text adafruit_esp32spi adafruit_connection_manager adafruit_httpserver
```
`circup` auto-detects the mounted `CIRCUITPY` drive and matches library versions to the installed CircuitPython version. Alternative: pull matching versions manually from the Adafruit CircuitPython Bundle and drop into `CIRCUITPY/lib/`.

## 3. Deploy code + secrets

- Copy `firmware/code.py` → `CIRCUITPY/code.py`
- Copy `firmware/settings.toml` → `CIRCUITPY/settings.toml` (holds `CIRCUITPY_WIFI_SSID` / `CIRCUITPY_WIFI_PASSWORD`, read via `os.getenv()` in code.py)
- Saving any file to `CIRCUITPY` triggers an automatic soft-reload of `code.py`.

## 4. Serial console

Same tool as the nRF52840 workflow:
```
tio /dev/tty.usbmodem*
```
Baud is irrelevant (USB CDC). This is where `print()` output and tracebacks show up — useful for confirming WiFi connect / server start (`Connected! IP: ...`).

## 5. Known gotchas

- `.gitignore` currently lists `./settings.toml`, but the file actually lives at `firmware/settings.toml` — that pattern won't match from a repo root gitignore. **Fix before pushing** — it currently has a live WiFi PSK in it.
- Color channel mismatch on this panel (documented in `verification/remap-colors.md`): green renders as blue, blue as magenta, etc. Needs a rgb_pins remap or panel rewire before using color-coded states (e.g. alert red vs. status green) for anything meaningful.

---
*Living doc — appended to as bringup steps are confirmed on the actual laptop.*
