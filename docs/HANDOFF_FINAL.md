# HANDOFF_FINAL — Juice Battle
# For: S008 prep (next chat session)
# Generated: 2026-07-20 end of S007

---

## Current position (one line)
S007 complete — GATT transport verified: hub connects to JB-0, HEARTBEAT flowing. S008 next: MSG_DIAG diagnostic message + storage.py SQLite layer.

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
| comms.h/cpp | DONE | NimBLE 2.5.0, GATT peripheral, NOTIFY char, 13-byte payload. Hardware verified S007. |
| juicebattle.ino | DONE | All modules wired. GATT comms integrated. Hardware verified S007. |

---

## Hub files — current state

| File | Status | Notes |
|---|---|---|
| config.py | DONE | All constants: BLE identity, TCP ports, msg types, game params |
| ble_scanner.py | DONE | GLib GATT central, connects JB-*/NOTIFY, TCP NDJSON server :7001, watchdog |
| transport.py | DONE | Docker consumer: TCP connect, NDJSON read, callback dispatch, auto-reconnect |
| juice-ble-scanner.service | DONE | systemd unit: Restart=always, User=arduino |
| setup.sh | DONE | One-time setup: apt python3-dbus, systemd enable+start |
| deploy.sh | DONE | Redeploy: systemctl restart |
| README.md | DONE | Operational runbook: monitoring, troubleshooting |
| storage.py | PENDING | S008 |
| game.py | PENDING | S009 |
| dashboard.py | PENDING | S010 |
| main.py | PENDING | S010 |

---

## S008 — what to build at next session

### Goal
Two independent deliverables. Build in order — verify each before starting the next.

---

### Deliverable 1: MSG_DIAG firmware diagnostic message

**Surgical addition to comms.h/cpp + juicebattle.ino. Do NOT touch other modules.**

Add `MSG_DIAG = 0x06` — fires every 5s from `STAB_WAITING` state.
Purpose: continuous node health telemetry to hub storage layer.

#### Payload extension (comms.h)
```c
#define COMMS_MSG_DIAG              0x06
#define COMMS_DIAG_INTERVAL_MS      5000

// MSG_DIAG payload — 13 bytes, same layout as all other messages:
// Byte 0:     version  = 0x01
// Byte 1:     msg_type = 0x06
// Byte 2:     node_id
// Bytes 3-6:  current_g   (float) — EMA weight on platform right now
// Bytes 7-10: sigma_g     (float) — stored at comms_init, static
// Bytes 11-12: seq_num    (uint16_t)
// NOTE: delta_g field (bytes 3-6) repurposed as current_g for DIAG only
// slope_g_per_s and error_flags fit by reuse of same 13-byte layout
```

Add to `comms.h`:
```c
void comms_send_diag(float current_g);
```

Add to `comms.cpp`:
```c
void comms_send_diag(float current_g) {
    _send_payload(COMMS_MSG_DIAG, current_g);
}
```

Add to `juicebattle.ino` in the `STAB_WAITING` block:
```c
static unsigned long s_diag_timer_ms = 0;
// inside if (sr.state == STAB_WAITING):
if (millis() - s_diag_timer_ms >= COMMS_DIAG_INTERVAL_MS) {
    s_diag_timer_ms = millis();
    comms_send_diag(sr.ema_g);
}
```

Add to `hub/config.py`:
```python
MSG_DIAG = 0x06
# MSG_NAMES dict: add MSG_DIAG: "DIAG"
```

**Verify**: journalctl shows `[DIAG] node=0` line every 5s in WAITING state.

---

### Deliverable 2: storage.py — SQLite persistence layer

**New file: `hub/storage.py`. No changes to existing hub files.**

#### Database: `hub/data/jb.db` (SQLite)

```sql
CREATE TABLE sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    ended_at    TEXT,
    node_count  INTEGER DEFAULT 0
);

CREATE TABLE pour_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER REFERENCES sessions(id),
    ts          TEXT NOT NULL,
    node_id     INTEGER NOT NULL,
    delta_g     REAL NOT NULL,
    sigma_g     REAL NOT NULL,
    seq         INTEGER NOT NULL
);

CREATE TABLE node_health (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    node_id     INTEGER NOT NULL,
    msg         TEXT NOT NULL,
    current_g   REAL,
    sigma_g     REAL,
    seq         INTEGER NOT NULL
);

CREATE TABLE error_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    source      TEXT NOT NULL,
    message     TEXT NOT NULL
);
```

#### storage.py interface (exact)
```python
class Storage:
    def __init__(self, db_path: str = "hub/data/jb.db"):
        ...  # CREATE TABLE IF NOT EXISTS on init

    def record_pour(self, session_id: int, ts: str, node_id: int,
                    delta_g: float, sigma_g: float, seq: int) -> None: ...

    def record_health(self, ts: str, node_id: int, msg: str,
                      current_g: float, sigma_g: float, seq: int) -> None: ...

    def record_error(self, ts: str, source: str, message: str) -> None: ...

    def open_session(self, node_count: int) -> int: ...  # returns session_id

    def close_session(self, session_id: int) -> None: ...
```

#### Wire transport.py callbacks → storage (test harness only, not game.py)
Create `hub/storage_test.py` — a standalone script that:
1. Instantiates `Transport` and `Storage`
2. Registers `on_event` callback that routes POUR_SETTLED → `record_pour`, DIAG/HEARTBEAT → `record_health`
3. Runs for 30s and prints row counts

**Verify**: After 30s, `sqlite3 hub/data/jb.db "SELECT COUNT(*) FROM node_health;"` shows non-zero.

---

### Volume mount prep (app.yaml)
No code change needed yet. Just note: when App Lab Docker config is created, `hub/data/` must be volume-mounted so `jb.db` persists across container restarts.

---

### Session start checklist for S008
1. Read this handoff fully
2. `systemctl status juice-ble-scanner` — should show active
3. `journalctl -u juice-ble-scanner -n 20` — should show HEARTBEAT every 2s
4. `nc localhost 7001` — should see `{"msg":"HEARTBEAT",...}` lines
5. Build MSG_DIAG (Deliverable 1), verify in journal, then proceed to storage.py

---

## BLE payload layout (13 bytes)

```
Byte  0:     version  = 0x01
Byte  1:     msg_type (0x01=HB, 0x02=ACTIVE, 0x03=SETTLED, 0x04=CAL, 0x05=SIGMA, 0x06=DIAG)
Byte  2:     node_id  (0 or 1)
Bytes 3–6:   delta_g  (float, little-endian) — for DIAG: repurposed as current_g
Bytes 7–10:  sigma_g  (float, little-endian, stored at comms_init)
Bytes 11–12: seq_num  (uint16_t, little-endian)

Device name: "JB-0" or "JB-1"
Transport: GATT peripheral, NOTIFY characteristic
UUID: 7b4c0f00-9aab-11ed-a8fc-0242ac120002
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
S007:        sigma_g = 4.0g   (confirmed in HEARTBEAT stream)
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
| S007 | DONE | GATT transport: scanner service, TCP NDJSON, HEARTBEAT verified 2026-07-20 |
| S008 | PENDING | MSG_DIAG firmware message + storage.py SQLite layer |
| S009 | PENDING | game.py: hub state machine, partial pour accumulation, glass counting |
| S010 | PENDING | Dashboard + Socket.IO |
| S011 | PENDING | Full two-node integration test |

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
│   ├── comms.h, comms.cpp              ← S007, GATT verified
│   └── juicebattle.ino
└── hub/
    ├── config.py                        ← S007 DONE
    ├── ble_scanner.py                   ← S007 DONE (systemd GATT central)
    ├── transport.py                     ← S007 DONE (Docker consumer)
    ├── juice-ble-scanner.service        ← S007 DONE
    ├── setup.sh                         ← S007 DONE
    ├── deploy.sh                        ← S007 DONE
    ├── README.md                        ← S007 DONE
    ├── data/                            ← S008: jb.db lives here
    ├── storage.py                       ← S008 next
    └── game.py                          ← S009 next
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
