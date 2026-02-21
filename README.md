# elab

> Personal electronics lab — bus analysis, embedded systems, hardware teardowns

A collection of hands-on hardware experiments, firmware work, and protocol analysis. Each project folder contains its own README with setup notes, wiring diagrams, logic analyzer captures, and lessons learned.

---

## Projects

| Project | Board | Topics |
|---------|-------|--------|
| [hb0100-centurion](./hb0100-centurion/) | Raspberry Pi Pico (RP2040) | SPI display, I2C IMU, logic analysis, TUI serial |

---

## Lab Equipment

- **Logic Analyzer:** NanoDLA (PulseView)
- **MCU:** Raspberry Pi Pico / RP2040
- **IDE:** Arduino IDE with Earle Philhower RP2040 core
- **Terminal:** screen / PuTTY

---

## Philosophy

These aren't polished tutorials — they're lab notes. Mistakes, dead ends, and wrong sample rates included. The goal is to understand what's happening at the silicon level, not just make the demo run.

---

## Structure

```
elab/
├── hb0100-centurion/     # HackerBox 0100 Centurion bus analysis
├── rf-lab/               # SDR, RF sniffing (coming)
├── net-lab/              # Packet analysis, switching (coming)
└── adl/                  # Advanced dev, original projects (coming)
```

---

## License

Apache 2.0 — see [LICENSE](./LICENSE)
