# HANDOFF_FINAL — Juice Battle
# For: S008 prep (next chat session)
# Generated: 2026-07-20 end of S007

---

## Current position (one line)
S007 complete — transport layer built: BLE scanner systemd service, TCP NDJSON publisher, Docker consumer. S008 next: game.py skeleton.

---

## What Juice Battle is

Crowd-facing real-time juice pouring competition at market stalls.
Two glass jars of juice compete. Visitors pour into glasses. Volume poured = score.
Score displayed as glass COUNT only. A glass counts when hub accumulates >= 150g from one node.

---

## Hardware

| Component | Detail |
|---|---|
| Hub | Arduino UNO Q, hostname AQ3, Debian Linux (MPU) + Zephyr (MCU) |
| Nodes | Two ESP32-C3 SuperMini — one per jar |
| Load cell | CZL601 40kg single-point. 2mV/V sensitivity. |
| ADC | WCMCU ADS1232 breakout. Gain=128 hardware-set. 10 SPS. |
| Jar | 10L glass jar. |
| Glass | 150ml per glass (operator-configurable at game start). |

---

## Wiring locked (ESP32-C3 → ADS1232)

| Signal | GPIO | ADS1232 Pin | Note |
|---|---|---|---|
| SCLK | GPIO4 | SCLK | Clock output |
| DOUT | GPIO5 | DOUT/DRDY | Data + ready signal |
| PDWN | GPIO6 | PDWN | Power down (HIGH=active) |
| A0 | GPIO7 | A0 | Channel select (LOW=ch1) |

POLARITY BUG: green/white CZL601 wires are physically swapped.
Current fix: ads1232.cpp returns -raw_value. TODO: swap wires in production build.

---

## Firmware files — current state

| File | Status | Notes |
|---|---|---|
| types.h | DONE | Quality enum: GOOD/DEGRADED/FAILED |
| config.h | DONE | NODE_ID=0, STABILITY_K_STOP=8, slope threshold comment |
| ads1232.h/cpp | DONE | Bit-bang, polarity fix (-raw_value) |
| noise.h/cpp | DONE | Welford algorithm, 100 samples |
| cal.h/cpp | DONE | 3-point piecewise cal, NVS persistent, confidence=0.968 |
| scale.h/cpp | DONE | Baseline capture + live read + noise clamp |
| stability.h/cpp | DONE | 4-state EMA machine, dynamic slope_threshold, K_stop=8 |
| comms.h/cpp | DONE | NimBLE 2.5.0, non-connectable BLE, 13-byte payload. Hardware verified. |
| juicebattle.ino | DONE | All modules wired. Comms integrated. Hardware verified. |

---

## Hub files — current state

| File | Status | Notes |
|---|---|---|
| config.py | DONE | All constants: BLE identity, TCP ports, msg types, game params |
| ble_scanner.py | DONE | GLib event-driven passive BLE scan, TCP NDJSON server on :7001, watchdog |
| transport.py | DONE | Docker consumer: TCP connect, NDJSON read, callback dispatch, auto-reconnect |
| juice-ble-scanner.service | DONE | systemd unit: Restart=always, User=arduino |
| setup.sh | DONE | One-time setup: apt python3-dbus, systemd enable+start |
| deploy.sh | DONE | Redeploy: systemctl restart |
| game.py | PENDING | S008 |
| dashboard.py | PENDING | S009 |
| main.py | PENDING | S009 |

---

## S008 — what to build at next session

**Goal:** game.py — the hub brain. Transport delivers events; game.py decides scores.

### Architecture
```
transport.py → game.py
                ├── process_pour_event(delta_g, sigma_g, node_id, hub_ts)
                ├── partial_accum[node_id]   += delta_g
                ├── if partial_accum >= GLASS_VOLUME_G: count += 1, reset accum
                └── returns GameSnapshot
```

### Hub state machine
```
WAITING_NODES → GAME_READY → GAME_RUNNING → GAME_PAUSED → GAME_OVER
```
- WAITING_NODES: waiting for both JB-0 and JB-1 to send a HEARTBEAT
- GAME_READY: both nodes seen, waiting for operator to press start
- GAME_RUNNING: accumulating pours, scoring
- GAME_PAUSED: operator paused mid-game
- GAME_OVER: operator ended game or time expired

### game.py interface (exact)
```python
class GameEngine:
    def process_pour_event(self, delta_g: float, sigma_g: float, node_id: int, hub_ts: str) -> GameSnapshot
    def node_seen(self, node_id: int)          # called on HEARTBEAT
    def start_game(self)                        # operator action
    def pause_game(self)                        # operator action
    def end_game(self)                          # operator action

@dataclass
class GameSnapshot:
    state: str
    scores: dict[int, int]                      # node_id → glass count
    partial_g: dict[int, float]                 # node_id → partial accum grams
    nodes_seen: set[int]
    last_event_ts: str
```

### Session start checklist for S008
1. Read this handoff fully
2. `systemctl status jb-ble-scanner` — should be running
3. `nc localhost 7001` — should see HEARTBEAT lines if node is on
4. Build `hub/game.py` per interface above
5. Wire game.py into a test harness (no UI yet)

---

## BLE payload layout (13 bytes)

```
Byte  0:     version  = 0x01
Byte  1:     msg_type (0x01=HB, 0x02=ACTIVE, 0x03=SETTLED, 0x04=CAL, 0x05=SIGMA)
Byte  2:     node_id  (0 or 1)
Bytes 3–6:   delta_g  (float, little-endian)
Bytes 7–10:  sigma_g  (float, little-endian)
Bytes 11–12: seq_num  (uint16_t, little-endian)

Device name: "JB-0" or "JB-1"
Company ID: 0xFFFF (prototype/testing)
Advertising: non-connectable, 100ms interval, +9 dBm TX power
```

---

## Key engineering rules (non-negotiable)

1. Orchestrator law: juicebattle.ino and main.py own ZERO logic — wires modules only
2. NODE_ID lives only in config.h — the single difference between two node binaries
3. Never hardcode thresholds that depend on sigma_live
4. Hub = prefrontal cortex (accumulates, decides, scores). Node = amygdala (detects, reports).
5. Every C++ module returns {value, quality (GOOD/DEGRADED/FAILED), diagnosis}
6. delayMicroseconds(2) on every GPIO edge during bit-bang operations
7. No String class in modules — char arrays and snprintf only

---

## Real measured values (S003/S006, verified on hardware)

```
Best calibration (NVS persistent):
  raw_zero  = 94690
  raw_500   = 148353
  raw_1000  = 201742
  raw_5000  = 630410
  confidence= 0.968   GOOD

S006 Run 1:  sigma_g = 5.03g  → slope_threshold = 25.1 g/s
S006 Run 2:  sigma_g = 6.54g  → slope_threshold = 32.7 g/s
Dynamic formula:  slope_threshold = fmaxf(15.0f, 5.0f × sigma_g)
```

---

## Session records

| Session | Status | Description |
|---|---|---|
| S001 | DONE | Bootstrap, directory structure |
| S002 | DONE | Hardware wiring complete |
| S003 | DONE | Calibration verified (confidence=0.968, NVS persistent) |
| S004 | DONE | Boot redesign (baseline capture, noise under load) |
| S005 | DONE | Stability state machine (partial pass — threshold fix needed) |
| S006 | DONE | Stability fixes + comms BLE layer (hardware verified 2026-07-17) |
| S007 | DONE | Transport layer: BLE scanner service, TCP NDJSON, consumer |
| S008 | PENDING | game.py skeleton: hub state machine, partial pour accumulation, glass counting |
| S009 | PENDING | Dashboard + Socket.IO |
| S010 | PENDING | Full two-node integration test |

---

## Project folder structure

```
~/ArduinoApps/juice_battle/
├── docs/
│   ├── TODO.md
│   ├── SESSIONS.md
│   ├── LEARNINGS_AND_INSIGHTS.md
│   ├── HANDOFF_FINAL.md                ← this file
│   ├── ARCHITECTURE.md
│   ├── HARDWARE_MANIFEST.md
│   └── INTERFACE_CONTRACTS.md
├── firmware/node/
│   ├── types.h, config.h
│   ├── ads1232.h, ads1232.cpp
│   ├── noise.h, noise.cpp
│   ├── cal.h, cal.cpp
│   ├── scale.h, scale.cpp
│   ├── stability.h, stability.cpp
│   ├── comms.h, comms.cpp              ← S006, hardware verified
│   └── juicebattle.ino
└── hub/
    ├── config.py                        ← S007 DONE
    ├── ble_scanner.py                   ← S007 DONE (systemd service)
    ├── transport.py                     ← S007 DONE (Docker consumer)
    ├── juice-ble-scanner.service        ← S007 DONE
    ├── setup.sh                         ← S007 DONE
    ├── deploy.sh                        ← S007 DONE
    └── game.py                          ← S008 next
```

---

## SCP commands (laptop ↔ AQ3)

```
# Board → Laptop (pull firmware files)
scp arduino@AQ3:/home/arduino/ArduinoApps/juice_battle/firmware/node/* C:\Users\mahes\Documents\Arduino\juicebattle\

# Laptop → Board (push handoff doc)
scp C:\Users\mahes\HANDOFF_FINAL.md arduino@AQ3:/home/arduino/ArduinoApps/juice_battle/docs\
```

---

## Pending hardware

- [ ] Swap CZL601 green/white wires physically (currently software-corrected in ads1232.cpp)
- [ ] Second node: identical firmware, NODE_ID=1 in config.h only
