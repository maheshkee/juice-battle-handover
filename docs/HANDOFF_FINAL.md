# HANDOFF_FINAL — Juice Battle
# For: S006 Part E / S007 prep (next chat session)
# Generated: 2026-07-17 end of S006

---

## Current position (one line)
S006 code complete — stability fixes + NimBLE comms layer written. Compile + hardware verify pending.

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
| Jar | 10L glass jar. Weight TBD (jar not yet available). |
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
| comms.h/cpp | DONE (unverified) | NimBLE 2.5.0, non-connectable BLE, 13-byte payload |
| juicebattle.ino | DONE (unverified) | All modules wired. Comms integrated. |

**UNVERIFIED**: comms.h/cpp and the updated juicebattle.ino have not been compiled or tested on hardware.
S006 Part E (compile + upload + serial verify) is the first task for the next hardware session.

---

## S006 Part E — what to do at next hardware session

```
Step 1: Compile
  arduino-cli compile --fqbn esp32:esp32:esp32c3 \
    ~/ArduinoApps/juice_battle/firmware/node/juicebattle/
  (juicebattle/ is a symlink directory created for arduino-cli. Already exists.)

Step 2: Upload
  arduino-cli upload --fqbn esp32:esp32:esp32c3 \
    --port /dev/ttyUSB0 \
    ~/ArduinoApps/juice_battle/firmware/node/juicebattle/

Step 3: Serial monitor (115200 baud). Confirm:
  [STAB] slope_threshold=XX.X g/s (sigma=X.XXg)   ← dynamic threshold active
  [INIT] min_pour_g=XX.Xg (3 × sigma=X.XXg)        ← noise filter active
  GAME_READY
  [COMMS] init complete: node_id=0 name=JB-0 sigma=X.XX
  [COMMS] tx msg=0x01 delta=0.0 sigma=X.XX seq=0    ← heartbeat
  (heartbeats every 2s)

Step 4: Place 500g weight. Confirm:
  [COMMS] tx msg=0x02  (POUR_ACTIVE, every 200ms during pour)
  [COMMS] tx msg=0x03  (POUR_SETTLED, one-shot)
  [POUR] 499.Xg dispensed   ← NOT "Ignored noise event"

Step 5: If compile errors in comms.cpp, check NimBLE 2.5.0 API:
  - setConnectableMode(BLE_GAP_CONN_MODE_NON) ← non-connectable
  - setPower(9) ← 9 dBm (not ESP_PWR_LVL_P9)
  - setManufacturerData(buf, 13) directly on NimBLEAdvertising
  - setName(name) directly on NimBLEAdvertising
```

---

## Boot sequence (locked)

```
1. ads1232_init()
2. cal_load_from_nvs()       ← hardware model, never changes
3. scale_capture_baseline()  ← whatever is on platform NOW
4. noise_measure(100)        ← σ under actual operating load
5. stability_init(sigma_g)   ← derives slope_threshold = fmaxf(15, 5×sigma)
6. stability_reset(baseline) ← sets s_baseline_g
7. g_min_pour_g = 3×sigma_g  ← noise artifact filter
8. comms_init(NODE_ID, sigma_g) ← BLE starts, first heartbeat sent
```

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

1. Orchestrator law: juicebattle.ino owns ZERO logic — wires modules only
2. NODE_ID lives only in config.h — the single difference between two node binaries
3. Never hardcode thresholds that depend on sigma_live
4. Any constant that depends on measured physical state must be computed at runtime
5. Hub = prefrontal cortex (accumulates, decides, scores). Node = amygdala (detects, reports).
6. Every C++ module returns {value, quality (GOOD/DEGRADED/FAILED), diagnosis}
7. delayMicroseconds(2) on every GPIO edge during bit-bang operations
8. No String class in modules — char arrays and snprintf only

---

## Real measured values (S003, verified on hardware)

```
Best calibration (NVS persistent):
  raw_zero  = 94690
  raw_500   = 148353
  raw_1000  = 201742
  raw_5000  = 630410
  confidence= 0.968   GOOD

S003 noise floor: sigma_g = 2.40g – 4.82g  (office, fan on)
S005 noise floor: sigma_g = 8.44g  (different session, higher ambient vibration)
Dynamic slope_threshold at S005 sigma: fmaxf(15, 5×8.44) = 42.2 g/s
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
| S006 | CODE DONE | Stability fixes + comms BLE layer (compile/verify pending) |
| S007 | PENDING | Hub BLE subscriber + game.py skeleton |
| S008 | PENDING | Dashboard + Socket.IO |
| S009 | PENDING | Full two-node integration test |

---

## Project folder structure

```
~/ArduinoApps/juice_battle/
├── docs/
│   ├── TODO.md                          ← active work list
│   ├── SESSIONS.md                      ← session records (append only)
│   ├── LEARNINGS_AND_INSIGHTS.md        ← L-001 through L-012
│   ├── HANDOFF_FINAL.md                 ← this file
│   ├── ARCHITECTURE.md
│   ├── HARDWARE_MANIFEST.md
│   ├── INTERFACE_CONTRACTS.md
│   └── juice_battle_project_bible.html
├── firmware/node/
│   ├── types.h, config.h
│   ├── ads1232.h, ads1232.cpp
│   ├── noise.h, noise.cpp
│   ├── cal.h, cal.cpp
│   ├── scale.h, scale.cpp
│   ├── stability.h, stability.cpp
│   ├── comms.h, comms.cpp       ← S006 new, unverified
│   ├── juicebattle.ino
│   └── juicebattle/             ← symlink dir for arduino-cli (gitignored)
└── hub/                         ← S007 onwards
```
