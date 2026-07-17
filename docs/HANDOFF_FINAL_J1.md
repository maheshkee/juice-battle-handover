# HANDOFF_FINAL — Juice Battle
# For: S006 (next chat session)
# Generated: 2026-07-17 end of S005

---

## Current position (one line)
S005 complete. Stability state machine tested on hardware. S006 = stability fixes
(dynamic slope threshold + K_stop=8 + min_delta filter) + BLE comms layer (comms.h/cpp).

---

## What this product is
Crowd-facing real-time juice pouring competition. Two glass jars on load cells compete
for audience votes measured by weight. Visitors pour juice; each jar's score updates live
on a browser dashboard. Two ESP32-C3 nodes → BLE advertising → AQ3 hub (Debian Linux)
→ Socket.IO dashboard.

---

## Hardware

| Component | Detail |
|---|---|
| Hub | Arduino UNO Q, SKU ABX00162, hostname AQ3 |
| Node MCU | ESP32-C3 SuperMini |
| Load cell | CZL601 single-point 40kg |
| ADC | WCMCU ADS1232 24-bit breakout |
| BLE | Built-in ESP32-C3, NimBLE stack |

**Voltage discipline (non-negotiable):**
- ADS1232: AVDD=5V, DVDD=3.3V
- MCU GPIO headers: 3.3V logic
- UNO Q JCTL headers: 1.8V ONLY — 3.3V here = hardware damage

---

## Wiring (Node 1 — locked, verified S002)

| Signal | ESP32-C3 GPIO | ADS1232 Pin | Note |
|---|---|---|---|
| SCLK | GPIO4 | SCLK | |
| DOUT | GPIO5 | DOUT | |
| PDWN | GPIO6 | PDWN | |
| A0 | GPIO7 | A0 | Routes below all components |
| GND | GND | SPEED | Low = 10 SPS |
| 5V | 5V | REFP | Reference voltage |
| GND | GND | CLKIN | Mandatory tie — critical |

**Polarity bug (software-corrected, pending hardware fix):**
CZL601 green and white wires are physically swapped. Current fix: ads1232.cpp returns
`-raw_value`. Must swap wires physically during production hardware build.

---

## Calibration (verified S003, NVS persistent)

```
raw_zero  = 94690
raw_500   = 148353
raw_1000  = 201742
raw_5000  = 630410
confidence= 0.968  GOOD
cf_500    = 0.009317
cf_1000   = 0.009341
cf_5000   = 0.009333  (spread 1.2%)
```

3-point piecewise linear calibration. Survives power cycle via NVS.
Test: 1000g stone → 1002.6g avg (0.26% error). Validated.

---

## Firmware file status

| File | Status | Notes |
|---|---|---|
| types.h | DONE | |
| config.h | DONE — needs S006 fix | Remove STABILITY_SLOPE_THRESHOLD_GS, add STABILITY_K_STOP 8 |
| ads1232.h/cpp | DONE | Returns -raw_value (polarity fix) |
| noise.h/cpp | DONE | Welford algorithm |
| cal.h/cpp | DONE | 3-point piecewise, NVS |
| scale.h/cpp | DONE | Baseline capture, live delta, noise clamp |
| stability.h/cpp | DONE — needs S006 fix | Dynamic threshold, K_stop=8 |
| juicebattle.ino | DONE — needs S006 wire | comms_init(), min_delta filter |
| comms.h | NOT STARTED — S006 | |
| comms.cpp | NOT STARTED — S006 | |

---

## Boot sequence (locked S004)

```
1. cal_load_from_nvs()          — hardware model, never changes
2. scale_capture_baseline()     — whatever is on platform NOW = new zero
3. noise_measure()              — sigma under ACTUAL operating load
4. derive thresholds from sigma — slope_threshold, min_pour_g
5. GAME_READY → await hub
```

Any platform state is valid at boot. Operator does not need to lift jars.

---

## S005 test results (real hardware, 2026-07-17)

Session had elevated sigma (σ=8.44g vs normal ~3g). Cause: load cell mechanical
creep after high-load/unload cycle, temperature change, or platform seating shift.

| Measurement | Result | Error |
|---|---|---|
| Bowl weight (kitchen scale: 3090g) | 3086g | 0.13% |
| 500g water added | 499.4g | 0.12% |
| Bowl removed (~3350g) | 3350.1g | — |
| 150ml removal (fragmented) | 22+23+14+61+25+10 ≈ 158g | ~5% |

State machine: WAITING→POUR→SETTLING→SETTLED all transitions correct.
Zero false triggers in calm WAITING periods (K=3 persistence saved from full failure).
False triggers occurred because σ=8.44g → noise-floor slope=25 g/s > hardcoded 15 g/s.

**Root cause and fix (LOCKED):**

```
noise-floor slope = alpha × sigma / dt = 0.3 × sigma / 0.1 = 3 × sigma_g

When sigma=8.44g → noise-floor slope = 25 g/s
Hardcoded threshold = 15 g/s  ← threshold was BELOW noise floor

Fix: slope_threshold = fmaxf(15.0f, 5.0f * sigma_g)
  sigma=3g → 15 g/s (normal operation, same as before)
  sigma=8g → 40 g/s (correctly above noise floor)
```

---

## Key engineering rules (non-negotiable)

1. **Orchestrator law:** juicebattle.ino owns zero logic — only wires modules
2. **NODE_ID** lives only in config.h — single difference between two node binaries
3. **Never hardcode thresholds that depend on sigma_live**
   Any constant that depends on measured physical conditions must be derived at runtime
4. **No WiFi credentials or secrets in source code**
5. **Every C++ module returns a result struct:** `{value, quality, diagnosis}`
6. **delayMicroseconds(2)** on every GPIO edge during bit-bang operations
7. **Hub = prefrontal cortex** (accumulates, decides, scores, persists game state)
   **Node = amygdala** (detects weight change, reports delta_g, nothing more)
8. **Atomic config writes** on hub — write to .tmp, then rename (power-cut safe)

---

## Architecture principle (locked S005)

```
Node reports: delta_g, sigma_g, node_id
Node never knows: score, glass_volume, game state, player identity

Hub decides: does this delta cross the glass threshold?
Hub accumulates: partial_accum += delta_g → when >= 150g → 1 glass counted
Hub owns: game state, history, dashboard, cheat detection, score persistence
Hub survives reboots: game state never stored on node
```

Fragmented pours (tap pause = multiple events) are correct and expected.
Hub accumulates fragments. 22+35+61+32 = 150g → hub counts 1 glass. Node doesn't care.

---

## S006 scope (exact next task)

**Three firmware fixes in stability.cpp (critical before any further testing):**

Fix 1 — Dynamic slope threshold:
```cpp
// In stability_init(float sigma_g):
s_slope_threshold = fmaxf(15.0f, 5.0f * sigma_g);
```

Fix 2 — K_stop = 8 (was 3):
```
#define STABILITY_K_STOP 8
```
Persistence counter for POUR_IN_PROGRESS→SETTLING transition.
800ms confirmation window prevents false settlement from tap pause.

Fix 3 — Minimum delta filter in juicebattle.ino:
```cpp
float g_min_pour_g = 3.0f * g_noise.sigma_g;
// After STABLE_SETTLED: if delta < g_min_pour_g → discard, reset, continue
```

**Then write comms.h/cpp — BLE advertising layer:**
- Non-connectable BLE advertising (hub scans passively, never connects)
- 13-byte manufacturer data payload: version + msg_type + node_id + delta_g + sigma_g + seq
- Message types: HEARTBEAT, POUR_ACTIVE, POUR_SETTLED, CAL_COMPLETE, SIGMA_ALERT
- Device name in advertising: "JB-0" or "JB-1" (NODE_ID from config.h)
- 100ms advertising interval

**Full S006 CLI prompt is ready** — it was generated at S005 close.
Use it directly with Claude CLI.

---

## Project structure (relevant paths)

```
~/ArduinoApps/juice_battle/
  firmware/node/juicebattle/    ← all node firmware
    ads1232.h/cpp
    noise.h/cpp
    cal.h/cpp
    scale.h/cpp
    stability.h/cpp
    comms.h/cpp                 ← S006 creates these
    config.h
    types.h
    juicebattle.ino
  docs/
    HANDOFF_FINAL.md            ← this file
    SESSIONS.md
    LEARNINGS_AND_INSIGHTS.md
    TODO.md                     ← created S005 close
    ARCHITECTURE.md
```

---

## SCP commands

Board → Laptop (firmware files):
```
scp arduino@AQ3:/home/arduino/ArduinoApps/juice_battle/firmware/node/* C:\Users\mahes\Documents\Arduino\juicebattle\
```

Laptop → Board (docs/handoff):
```
scp C:\Users\mahes\HANDOFF_FINAL.md arduino@AQ3:/home/arduino/ArduinoApps/juice_battle/docs/
```

---

## Pending hardware (production build)

- [ ] Swap CZL601 green/white wires physically (currently software-corrected)
- [ ] Second node: identical firmware, NODE_ID=1 in config.h

---

## Session start checklist for S006

```
1. Read this handoff fully
2. Confirm: cat ~/ArduinoApps/juice_battle/firmware/node/juicebattle/config.h
3. Confirm: cat ~/ArduinoApps/juice_battle/firmware/node/juicebattle/stability.h
4. Run the S006 CLI prompt
5. Verify serial output after upload
```
