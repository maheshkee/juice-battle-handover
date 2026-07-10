# Juice Battle 🥤

A real-time juice competition system for market stalls.

Two juice jars sit on weight-scale platforms. As visitors pour juice, their jar's persona gains points, emotes reactions, and battles the rival persona on a live dashboard.

---

## Hardware required

| Component           | Qty | Role                              |
|---------------------|-----|-----------------------------------|
| Arduino UNO Q       | 1   | Hub brain (MPU + MCU)             |
| ESP32-C3 SuperMini  | 2   | Sensor nodes (one per jar)        |
| CZL601 load cell    | 2   | Single-point weight sensing       |
| ADS1232 ADC         | 2   | 24-bit ADC for load cell          |
| Display (TBD)       | 1   | Live dashboard output             |

---

## Project structure

```
juice_battle/
├── hub/          App Lab app — UNO Q (Python + sketch)
├── firmware/     ESP32-C3 node firmware (same code, different config.h)
├── tests/        Unit tests — run without hardware
└── docs/         Architecture, contracts, hardware manifest
```

---

## First-time setup

```bash
# On the UNO Q board (SSH or SBC mode)
cd /home/arduino/arduino_apps/juice_battle

# Install hub Python dependencies
pip3 install paho-mqtt --break-system-packages

# Flash the ESP32 nodes (using Arduino IDE or PlatformIO on your PC)
# See firmware/README.md
```

---

## Running the hub

```bash
# Via App Lab
arduino-app-cli app start user:juice_battle

# Logs
arduino-app-cli app logs user:juice_battle --follow
```

---

## Session management

Every session must begin by reading `sessions/HANDOFF_FINAL.md`.
Every session must produce a new `sessions/SNNN_description.md` and update `HANDOFF_FINAL.md`.

See `SESSION_CLOSE_PROTOCOL.md` for the full procedure.

---

## Key contacts / docs

- `WORKING_CONTRACT.md` — engineering rules
- `docs/ARCHITECTURE.md` — system design
- `docs/INTERFACE_CONTRACTS.md` — data schemas and API contracts
- `docs/HARDWARE_MANIFEST.md` — confirmed hardware specs and pinouts
