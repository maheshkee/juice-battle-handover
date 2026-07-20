# SESSIONS — Juice Battle
# Append only. One entry per session.

---

## S003 - 2026-07-16
Goal: Write and verify cal.cpp + scale.cpp. Run 3 calibration runs with validation sweep.

Hardware used: ESP32-C3 SuperMini + WCMCU ADS1232 + CZL601 40kg load cell
Reference weights: 500g / 1000g / 5000g (government cast iron, kitchen-scale verified)
Validation weights: 200g / 700g (200+500) / 1500g (500+1000) / 10000g

Real measured outputs:

Calibration runs:
| Run | raw_zero | raw_500  | raw_1000 | raw_5000 | confidence | sigma_tare |
|-----|----------|----------|----------|----------|------------|------------|
| 1   | 94690    | 148353   | 201742   | 630410   | 0.968      | 2.54g      |
| 2   | 94833    | 148826   | 202023   | 630627   | 0.904      | 3.06g      |
| 3   | 94822    | 148724   | 201936   | 630576   | 0.920      | 2.40g      |

Validation sweep (Run 1 model):
| Point  | Expected | Run1  | Run2  | Run3  | Mean error |
|--------|----------|-------|-------|-------|------------|
| 200g   | 200g     | 1.12% | 1.64% | 1.38% | 1.38%      |
| 700g   | 700g     | 0.31% | 0.26% | 0.15% | 0.24%      |
| 1500g  | 1500g    | 0.18% | 0.00% | 0.15% | 0.11%      |
| 10000g | 10000g   | 0.03% | 0.05% | 0.04% | 0.04%      |

Live scale test (Run1 NVS loaded):
| Round | Object       | Average  | Known   | Error  |
|-------|-------------|----------|---------|--------|
| 2     | 200g stone  | 194.4g   | 200g    | 2.8%   |
| 4     | 1000g stone | 1002.6g  | 1000g   | 0.26%  |
| 5     | Empty       | 0.0g     | 0g      | 0%     |

Bugs found and fixed:
- Signal polarity reversed: ads1232.cpp returns -raw_value (green/white swapped)
- Tare guard in cal.cpp spec was broken (CLI caught and fixed correctly)
- CAL_MAX_ACCEPTABLE_SPREAD 0.05 too tight → corrected to 0.08 from real data
- noInterrupts wrapper in cal.cpp omitted correctly (would hang DRDY wait loop)

Gate result: PASSED
Files built: types.h config.h ads1232.h ads1232.cpp noise.h noise.cpp
             cal.h cal.cpp scale.h scale.cpp juicebattle.ino

---

## S005 — Stability State Machine
**Date:** 2026-07-17
**Goal:** Implement and verify 4-state EMA stability machine on real hardware

### Real hardware outputs
| Measurement | Result | Error |
|---|---|---|
| Boot sigma | 8.44g | 3× higher than previous sessions |
| Bowl (kitchen: 3090g) | 3086g | 0.13% |
| 500g water | 499.4g | 0.12% |
| Bowl removal | 3350.1g | — |
| 150ml removal (fragmented) | 22+23+14+61+25+10 ≈ 158g | ~5% |

### Gate result
PARTIAL PASS — state machine correct, thresholds need sigma-adaptive fix

### What was built
- stability.h/cpp — 4-state machine (WAITING, POUR_IN_PROGRESS, SETTLING, STABLE_SETTLED)
- config.h additions: STABILITY_EMA_ALPHA=0.3f, STABILITY_SETTLING_SAMPLES=5
- juicebattle.ino updated — stability_init(), stability_reset(), stability_update()

### Key finding
sigma=8.44g → noise-floor slope=25 g/s > hardcoded threshold 15 g/s.
K=3 persistence prevented complete failure but could not fully compensate.
Fix: slope_threshold = fmaxf(15.0f, 5.0f × sigma_g) — derived at runtime.

### Next
S006 — stability fixes + comms.h/cpp BLE advertising layer

---

## S006 — Stability Fixes + BLE Comms Layer
**Date:** 2026-07-17
**Goal:** Fix 3 stability issues found in S005 and build NimBLE BLE advertising comms layer

### Changes made

#### stability.cpp fixes
1. `slope_threshold` now runtime-computed: `fmaxf(15.0f, 5.0f * sigma_g)` — eliminates false triggers when sigma is high
2. K_stop = 8 (was 1 implicit): 800ms confirmation window before POUR→SETTLING transition — eliminates false settlement from tap pause mid-pour
3. `min_delta` filter in juicebattle.ino: events < 3×sigma_g discarded as noise artifacts

#### comms.h/cpp — NimBLE BLE advertising layer
- Non-connectable advertising (BLE_GAP_CONN_MODE_NON)
- 100ms interval (160 × 0.625ms)
- 13-byte manufacturer-specific payload: version + msg_type + node_id + delta_g + sigma_g + seq_num
- Message types: HEARTBEAT, POUR_ACTIVE, POUR_SETTLED, CAL_COMPLETE, SIGMA_ALERT
- Device name: "JB-0" / "JB-1" for hub scanner identification
- NimBLE-Arduino 2.5.0 installed

#### juicebattle.ino wiring
- comms_init() called after GAME_READY
- Heartbeat every 2s in WAITING state
- POUR_ACTIVE broadcast every 200ms in POUR_IN_PROGRESS state
- POUR_SETTLED one-shot after noise filter passes
- NODE_ID added to config.h (= 0 for node A)

### Gate result
FULL PASS — two hardware verification runs completed

#### Run 1 (sigma=5.03g, slope_threshold=25.1 g/s)
- WAITING: zero false triggers across hundreds of samples
- Pour 1: -3326g (jar lifted + refilled — handled correctly)
- Pour 2: 33g small pour (above min_pour_g=15.1g) — reported correctly
- Pour 3: 92g — reported correctly
- Pour 4: 3195g (jar lifted and refilled) — handled correctly
- K_stop=8 counting confirmed in serial log
- COMMS: msg=0x01 (heartbeat), 0x02 (pour-active), 0x03 (pour-settled) all firing
- seq incrementing correctly

#### Run 2 (sigma=6.54g, slope_threshold=32.7 g/s)
- sigma elevated → dynamic threshold correctly scaled to 32.7 g/s
- WAITING: zero false triggers during slow drift (EMA drifting 10–20 g/s over many minutes)
- Pour 1: -3317g
- Pour 2: 25.6g (above min=19.6g)
- Pour 3: 191.9g (~220g removed — 13% error, within acceptable range for non-settling pour)
- Pour 4: 65.2g (jar lifted mid-session — handled correctly)
- Pour 5: 3159.5g (bowl removed entirely)
- Post-pour WAITING returns to near-zero delta within 1-2 seconds

### Files changed
- firmware/node/config.h (slope threshold comment, K_STOP=8, NODE_ID=0)
- firmware/node/stability.cpp (s_slope_threshold static, K_stop counter in POUR_IN_PROGRESS)
- firmware/node/comms.h (new — full BLE comms API)
- firmware/node/comms.cpp (new — NimBLE 2.5.0 implementation)
- firmware/node/juicebattle.ino (comms wired, min_delta guard, timers)

### Next
S007 — Hub BLE subscriber + game.py skeleton

---

## S007 — Hub Transport Layer (BLE Scanner + TCP Publisher + Consumer)
**Date:** 2026-07-20
**Goal:** AQ3 hub passively scans JB-0/JB-1 BLE advertisements, parses 13-byte payload, publishes NDJSON over TCP :7001

### Architecture delivered
- `ble_scanner.py`: GLib event-driven passive BLE scanner, D-Bus/BlueZ, TCP NDJSON server, watchdog
- `transport.py`: Docker-side TCP consumer with callback registration, auto-reconnect
- `config.py`: all constants (BLE identity, TCP ports, message types, game params)
- `juice-ble-scanner.service`: systemd unit (Restart=always, RestartSec=5, User=arduino)
- `setup.sh`: one-time board setup (apt install python3-dbus, systemd enable+start)
- `deploy.sh`: redeploy on code change (systemctl restart)

### Key implementation notes
- ManufacturerData values cast to `bytes()` before `struct.unpack` — dbus.Array is not bytes
- `int(key) == COMPANY_ID` — dbus.UInt16 needs explicit int cast
- DuplicateData=True in SetDiscoveryFilter — required to get every advertisement, not just first-seen
- TCP server multi-client: threading.Thread accept loop + shared list with Lock
- Dead clients removed silently on OSError — never crash scanner on client disconnect
- Watchdog: GLib.timeout_add_seconds(10) checks `time.monotonic()`, exits for systemd restart on silence

### BLE stack on AQ3
- bluetooth.service: active (14h uptime at session start)
- python3-gi (GLib): installed
- python3-dbus: NOT installed at session start — setup.sh installs it

### Gate result
PENDING — node must be advertising; `bash hub/setup.sh` required before first run

### Files created
- hub/config.py
- hub/ble_scanner.py
- hub/transport.py
- hub/juice-ble-scanner.service
- hub/setup.sh
- hub/deploy.sh

### Next
S008 — game.py skeleton: Hub state machine WAITING_NODES → GAME_READY → GAME_RUNNING → GAME_OVER, partial pour accumulation, glass counting
