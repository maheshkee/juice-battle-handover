# Juice Battle

## 1. What Is Juice Battle

IoT-powered juice pouring competition for a market stall. Two jars sit on load cell sensors — one per team. The crowd picks a side and pours juice into their jar. Load cells detect every pour in real time, transmitting weight deltas over BLE to a hub. The dashboard shows live scores, pour animations, and crowd stats on a large display. Built by Dharanova. Runs entirely on an Arduino UNO Q board — no cloud, no internet, no laptop required at the stall.

---

## 2. Hardware Required

| Item | Role |
|---|---|
| Arduino UNO Q (SKU ABX00162/ABX00173) | Hub. Runs Linux (MPU) + Zephyr (MCU). |
| 2× ESP32-C3 SuperMini (JB-0, JB-1) | Sensor nodes. |
| 2× CZL601 single-point load cell (40 kg rated) | Weight sensing. |
| 2× ADS1232 24-bit ADC boards | Load cell amplifier/digitiser. |
| Arzopa 28″ display | Scoreboard display. |
| Wireless HDMI transmitter/receiver | Cable-free video to display. |
| USB-C PD power adapter | Powers AQ3. |
| 2× USB adapters | Power JB-0 and JB-1. |

### Node wiring — critical

- **JB-0**: standard wiring.
- **JB-1**: green and white wires **SWAPPED** at ADS1232 INNA+/INNA− (polarity fix for reversed load cell signal).
- Both nodes negate `raw_value` in firmware (`-raw_value`) to compensate for polarity.

### Voltage discipline — read before touching headers

- MCU headers: 3.3 V logic, 5 V tolerant — **except A0 and A1**.
- MPU headers (JCTL, JMISC): **1.8 V ONLY**. Applying 3.3 V here causes permanent hardware damage.

---

## 3. System Architecture

```
JB-0 (ESP32-C3) ──BLE GATT──┐
                              ├──► BlueZ / D-Bus (MPU Linux)
JB-1 (ESP32-C3) ──BLE GATT──┘          │
                                   ble_scanner.py
                                         │  TCP socket
                                     main.py (orchestrator)
                                   ┌─────┴──────┐
                                game.py      storage.py
                                         │
                                   dashboard.py (Flask + SocketIO)
                                         │
                                   Chromium kiosk → Arzopa display
```

### Architecture principles — non-negotiable

- **Hub = prefrontal cortex.** Owns all logic, state, and history.
- **Node = amygdala.** Detects weight change, reports `delta_g` only. No decisions.
- **`main.py` = orchestrator.** Zero logic. Wires modules only. No imports between modules.

### Node state machine

```
IDLE → CALIBRATING → GAME_READY → WAITING_FOR_POUR
     → POUR_IN_PROGRESS → SETTLING → STABLE_SETTLED
     → GLASS_COUNTED | PARTIAL_POUR
```

### Key design decisions — the WHY matters

| Decision | Why |
|---|---|
| Count glasses, not grams | Eliminates density conversion (juice ≠ water) and prevents display flicker from sub-glass pours. |
| Volume-based scoring | Operator sets `glass_volume_g` once. System counts only whole glasses. No fractions. |
| GATT notify pattern | Only proven BLE pattern on this board. Polling and write patterns were unreliable in testing. |
| BlueZ D-Bus directly | Direct kernel access. No BLE library abstraction bugs. |
| `slope_threshold = fmaxf(15.0f, 5.0f × sigma_g)` | Derived at boot from live noise floor. Never hardcoded — every environment differs. |
| `POUR_WINDOW_S = 20.0 s` minimum | Real-world testing showed tap drip gaps reach 18+ seconds. Shorter windows caused false glass splits. |

---

## 4. Repository Structure

```
juice_battle/
├── firmware/
│   └── node/
│       └── juicebattle/
│           └── juicebattle.ino     # ESP32-C3 sketch — flash via Arduino IDE
├── hub/
│   ├── main.py                     # Orchestrator — zero logic, wires modules
│   ├── ble_scanner.py              # BlueZ D-Bus BLE pipeline
│   ├── game.py                     # All scoring logic
│   ├── storage.py                  # SQLite persistence
│   ├── dashboard.py                # Flask + SocketIO web server + HTML template
│   ├── config.py                   # All tunable constants
│   ├── juice-battle.service        # systemd unit — hub
│   ├── juice-ble-scanner.service   # systemd unit — BLE scanner
│   ├── data/
│   │   └── jb.db                   # SQLite database (excluded from git)
│   └── static/                     # Frontend assets (logo, sounds, QR, socket.io.js)
├── setup.sh                        # Run once on a fresh board
├── deploy.sh                       # Developer redeploy after code changes
├── juice_battle_kiosk.sh           # XFCE kiosk launcher (installed to /home/arduino/)
└── README.md                       # This file
```

---

## 5. First-Time Setup (Fresh Board)

### Clone and set up

```bash
git clone git@github.com:gratiantechnologies/project13.git
cd project13
git checkout juice-battle-main
cd juice_battle

chmod +x setup.sh
./setup.sh

sudo reboot
```

After reboot: services start automatically, kiosk launches, dashboard is live at `http://AQ3.local:5000/v2`.

### Flash firmware to nodes

1. Open Arduino IDE.
2. Open `firmware/node/juicebattle/juicebattle.ino`.
3. Board: **ESP32C3 Dev Module**.
4. Flash JB-0 (`NODE_ID=0`), then JB-1 (`NODE_ID=1`).
5. For JB-1: remember the green/white wire swap at ADS1232 INNA+/INNA−.

`NODE_ID` lives only in `config.h` — never in any other file.

---

## 6. Operator Runbook (Running the Stall)

### Pre-event reset — run once before each stall event

```bash
sudo systemctl stop juice-battle juice-ble-scanner
rm ~/ArduinoApps/juice_battle/hub/data/jb.db
sudo systemctl start juice-ble-scanner juice-battle
```

This wipes all scores and pour history. Do this at the start of every event.

### Startup sequence — follow this order every time

1. Power on AQ3.
2. **Place jars on load cell platforms** ← must happen before step 3.
3. Power on JB-0 and JB-1.
4. Watch dashboard — **"BOTH NODES CONNECTED"** confirms ready to play.

> **WARNING:** Never place jars on platforms after nodes have powered on. Nodes tare at boot with the jar weight included. Placing the jar after tare registers as an ANOMALY event and corrupts the baseline.

### During the event

Dashboard is fully automatic. No operator input needed during play. The **Game Over** button (top right) ends the game manually if required.

---

## 7. Developer Runbook

### SSH into the board

```bash
ssh arduino@AQ3            # on the same network as the board
ssh arduino@192.168.4.1   # when connected to the JuiceBattle hotspot
```

### Deploy after code changes

```bash
cd ~/ArduinoApps/juice_battle
./deploy.sh          # restart hub only
./deploy.sh --ble    # restart hub + BLE scanner
```

### Push code to git

```bash
git add -A
git commit -m "your message"
git push origin HEAD:juice-battle-main
```

### Developer curl commands (not in UI — secret by obscurity)

```bash
curl -X POST http://localhost:5000/adjust/0/1    # jar 0 +1 glass
curl -X POST http://localhost:5000/adjust/0/-1   # jar 0 −1 glass
curl -X POST http://localhost:5000/adjust/1/2    # jar 1 +2 glasses
curl -X POST http://localhost:5000/game_over     # trigger game over
```

### Hotspot mode (standalone — no router needed)

```bash
sudo nmcli con up "JuiceBattle-AP"     # activate hotspot
sudo nmcli con down "JuiceBattle-AP"   # deactivate, return to normal WiFi
```

Password: `juicebattle2024`

---

## 8. Troubleshooting

### Node not connecting

```bash
sudo journalctl -u juice-ble-scanner -f
```

- `UnknownObject` in logs: scanner will auto re-arm discovery — wait 20 s.
- Still stuck: `sudo systemctl restart juice-ble-scanner`

### Dashboard not loading

```bash
sudo systemctl status juice-battle
sudo journalctl -u juice-battle -f
```

Hard refresh browser: `Ctrl+Shift+R`

### BLE scanner stuck after reboot

```bash
sudo systemctl restart bluetooth
sudo systemctl restart juice-ble-scanner
```

### Check all service health

```bash
sudo systemctl status juice-battle juice-ble-scanner bluetooth --no-pager
```

### View live logs — both services

```bash
journalctl -u juice-battle -u juice-ble-scanner -f
```

### Node sigma elevated (noisy readings)

| Node | Good sigma | Acceptable |
|---|---|---|
| JB-0 | ~3.15 g | up to ~6 g |
| JB-1 | ~3.92 g | up to ~6 g |

Both measured with jars present at tare. System adapts `slope_threshold` automatically. If sigma > 8 g: check load cell wiring and platform stability.

---

## 9. Key File Locations (Quick Reference)

| What | Where |
|---|---|
| Hub code | `~/ArduinoApps/juice_battle/hub/` |
| Firmware | `~/ArduinoApps/juice_battle/firmware/node/juicebattle/` |
| Database | `~/ArduinoApps/juice_battle/hub/data/jb.db` |
| Hub service | `/etc/systemd/system/juice-battle.service` |
| BLE service | `/etc/systemd/system/juice-ble-scanner.service` |
| Kiosk script | `/home/arduino/juice_battle_kiosk.sh` |
| Kiosk autostart | `/home/arduino/.config/autostart/juice_battle_kiosk.desktop` |
| Hub logs | `journalctl -u juice-battle -f` |
| BLE logs | `journalctl -u juice-ble-scanner -f` |

---

## 10. Node MAC Addresses

Locked. Do not change in firmware.

| Node | MAC | NODE_ID |
|---|---|---|
| JB-0 | `70:AF:09:32:F3:C2` | 0 |
| JB-1 | `10:00:3B:CD:63:32` | 1 |
