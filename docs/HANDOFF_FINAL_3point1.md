# HANDOFF_FINAL — Juice Battle
# For: S004 (next chat session)
# Generated: 2026-07-16 end of S003

---

## Current position (one line)
Phase 1 firmware in progress — cal + scale DONE and verified.
S004: boot redesign (baseline replaces tare, noise under load).
S005: stability.cpp (after boot redesign confirmed).

---

## What Juice Battle is

Crowd-facing real-time juice pouring competition at market stalls.
Two glass jars of juice compete. Visitors pour into glasses. Volume poured = score.
Score displayed as glass COUNT only. Volume-based game — a glass counts when
weight delta ≥ glass_volume_g.

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

| Signal | ESP32-C3 GPIO | ADS1232 Pin | Note |
|---|---|---|---|
| SCLK | GPIO4 | SCLK | Clock output |
| DOUT | GPIO5 | DOUT/DRDY | Data + ready signal |
| PDWN | GPIO6 | PDWN | Power down (HIGH=active) |
| A0 | GPIO7 | A0 | Channel select (LOW=ch1) |
| GND | GND | SPEED | 10 SPS mode |
| 5V | 5V | REFP | Reference voltage |
| CLKIN | — | GND | Mandatory tie |

POLARITY BUG: green/white CZL601 wires are physically swapped at ADS1232 INNA+/INNA-.
Current fix: ads1232.cpp returns -raw_value (software negation).
TODO: swap wires physically and remove the negation when convenient.

---

## Toolchain

- Arduino IDE with Espressif esp32 package
- Board: ESP32C3 Dev Module
- Upload speed: 921600
- Sketch folder: juicebattle/ → juicebattle.ino
- SCP board→laptop: scp arduino@AQ3:/home/arduino/ArduinoApps/juice_battle/firmware/node/* C:\Users\mahes\Documents\Arduino\juicebattle\
- SCP laptop→board: scp C:\Users\mahes\<file> arduino@AQ3:/home/arduino/ArduinoApps/juice_battle/docs/

---

## Firmware files — current state

| File | Status | Notes |
|---|---|---|
| types.h | DONE | Quality enum: GOOD/DEGRADED/FAILED (unprefixed) |
| config.h | DONE | All pins, constants, measured thresholds |
| ads1232.h | DONE | HAL interface |
| ads1232.cpp | DONE | Bit-bang. Settling pulse. delayMicroseconds(2). Returns -raw_value (polarity fix). |
| noise.h | DONE | NoiseResult struct + noise_measure() |
| noise.cpp | DONE | Welford algorithm. |
| cal.h | DONE | CalResult struct + 4 function declarations |
| cal.cpp | DONE | 3-point piecewise cal. NVS persistent. Verified. |
| scale.h | DONE | ScaleResult struct + 3 function declarations |
| scale.cpp | DONE | Baseline capture + live read + noise clamp. Verified. |
| juicebattle.ino | DONE | Orchestrator. Wires all modules. |
| stability.h/cpp | NOT STARTED | S005 |
| comms.h/cpp | NOT STARTED | After stability |
| weight_engine.h/cpp | NOT STARTED | After stability |

---

## Real measured outputs (S003, verified on hardware)

```
Best calibration (Run 1 of 3):
  raw_zero  = 94690
  raw_500   = 148353
  raw_1000  = 201742
  raw_5000  = 630410
  confidence= 0.968   GOOD
  sigma_tare= 2.54g

Calibration nonlinearity:
  cf_500  = 0.009317 g/count
  cf_1000 = 0.009341 g/count
  cf_5000 = 0.009333 g/count
  spread  = 1.2% of mean (corrected by piecewise model)

Validation sweep (4 points, 3 runs):
  200g:   worst 1.64%  (low-end nonlinearity — expected, understood)
  700g:   worst 0.31%
  1500g:  worst 0.18%
  10000g: worst 0.05%
  All 4 points PASS across all 3 runs.

Live scale (NVS loaded):
  1000g stone: 1002.6g average (0.26% error)
  Empty platform: 0.0g (noise clamp working)

Noise floor range across S003 boots:
  sigma_g = 2.40g – 4.82g  (all GOOD, office, fan on)
```

---

## Critical rules — never violate

1. Settling pulse mandatory in ads1232_read_raw() — without it next read corrupts Welford.
2. delayMicroseconds(2) not (1) — ESP32-C3 at 160MHz, 1µs unreliable.
3. noInterrupts() only around 24-bit read loop, NOT around the full DRDY wait.
4. Orchestrator law: juicebattle.ino owns zero logic — wires modules only.
5. Result struct contract: every module returns {value, quality, diagnosis}.
6. Cal data in NVS — survives power cycle. Verified working.
7. No String class in modules — char arrays and snprintf only.
8. CAL_MAX_ACCEPTABLE_SPREAD = 0.08f — derived from real CZL601 data. Do not change.

---

## S004 spec — boot redesign

### The problem with current boot design
scale_tare() requires empty platform. In production the jar never leaves the
platform. Power loss + reboot = operator must remove full 10L jar. Unacceptable.

Also: noise is currently measured before baseline on an empty platform.
Noise should be measured under operating load — that is what stability.cpp sees.

### The correct design (decisions locked)

```
Wrong: tare = empty platform reading
Right: baseline = current platform state (jar, juice, whatever is on it)

Wrong: noise measured before baseline on empty platform
Right: noise measured AFTER baseline with current load in place

Wrong: platform-loaded-at-boot = error condition
Right: platform-loaded-at-boot = normal production condition
```

### New boot sequence (implement in S004)

```
1. cal_load_from_nvs()              ← hardware model, never changes
2. scale_capture_baseline()         ← whatever is on platform RIGHT NOW
                                       empty at install, loaded in production
3. noise_measure()                  ← σ under actual operating conditions
4. derive thresholds from σ_live    ← stability.cpp uses these
5. GAME_READY → await hub
```

### Code changes required for S004

CHANGE 1 — Rename in scale.h + scale.cpp:
  scale_tare() → scale_capture_baseline()
  ScaleResult field: result.grams stays 0.0 (baseline defines zero by definition)
  Remove: platform-loaded guard check (if it exists — it should not after today)

CHANGE 2 — In juicebattle.ino reorder:
  Move noise_measure() to AFTER scale_capture_baseline()
  Remove force_recal block (already removed)
  Remove one-time NVS write block (remove after first boot confirms)

CHANGE 3 — In config.h:
  Remove SCALE_TARE_LOADED_THRESHOLD_G if added — not needed anymore

CHANGE 4 — In juicebattle.ino, handle loaded-platform boot gracefully:
  No error. No wait. Just capture baseline and continue.
  Print: "[SCALE] Baseline captured: Xg on platform" so operator can see state.

### What does NOT change
- scale_read() is identical — it still subtracts baseline_g
- cal_to_grams() is identical
- NVS structure is identical
- All module contracts identical

---

## Piecewise linear formula (the calibration model)

```cpp
float cal_to_grams(int32_t raw, const CalResult& cal) {
    float u  = (float)(raw - cal.raw_zero);
    float u1 = (float)(cal.raw_500  - cal.raw_zero);  // = 53663
    float u2 = (float)(cal.raw_1000 - cal.raw_zero);  // = 107052
    float u3 = (float)(cal.raw_5000 - cal.raw_zero);  // = 535720

    if (u <= 0.0f)   return 0.0f;
    if (u <= u1)     return (u / u1) * 500.0f;
    if (u <= u2)     return 500.0f  + (u - u1) / (u2 - u1) * 500.0f;
    else             return 1000.0f + (u - u2) / (u3 - u2) * 4000.0f;
}
```

---

## State machine — full 10-state design

See docs/juice_battle_state_machine.html — open in browser.

After S004 boot redesign, the node enters GAME_READY with:
- baseline_g = current platform weight (may be 0 or 3000+)
- sigma_live = noise measured under that load
- All thresholds derived from sigma_live

---

## S005 spec — stability.cpp (after S004 confirmed)

stability.cpp owns:
- EMA filter on scale_read() output
- Slope calculation (g/s) from EMA over time
- Persistence counter (K samples below slope threshold)
- Pour start detection: WAITING_FOR_POUR → POUR_IN_PROGRESS
- Settlement detection: slope returns to ~0, spread < sigma threshold
- Baseline update after settlement

Inputs: ScaleResult stream from scale_read()
Output: StabilityResult {state, slope_g_per_s, ema_g, quality, diagnosis}

Key constants (from S002 hardware measurement):
- STABILITY_SPREAD_THRESHOLD_G = 25.0g  (4 × sigma_live)
- STABILITY_SLOPE_THRESHOLD_GS = 15.0   g/s
- STABILITY_PERSISTENCE_K      = 3      samples (0.3s at 10 SPS)

---

## Session start checklist S004

Before writing any code:
- [ ] Read this handoff fully
- [ ] Confirm juicebattle.ino compiles clean on current laptop copy
- [ ] Note: one-time NVS write block may still be in juicebattle.ino — remove it
- [ ] Confirm NVS loads correctly on fresh boot (should show confidence=0.968)
- [ ] Rename scale_tare → scale_capture_baseline across all files
- [ ] Reorder boot sequence in juicebattle.ino
- [ ] Flash, test with jar on platform at boot, confirm no error
- [ ] Flash, test with empty platform at boot, confirm no error
- [ ] Both paths must work identically

---

## Project folder structure

```
~/ArduinoApps/juice_battle/
├── docs/
│   ├── juice_battle_project_bible.html
│   ├── juice_battle_state_machine.html
│   ├── ARCHITECTURE.md
│   ├── HARDWARE_MANIFEST.md
│   ├── INTERFACE_CONTRACTS.md
│   ├── LEARNINGS_AND_INSIGHTS.md
│   ├── RESEARCH.md
│   ├── SESSIONS.md
│   ├── CLAUDE.md
│   ├── PROJECT_CONTEXT.md
│   └── HANDOFF_2026_07_16_S003_cal_scale_verified.md
├── firmware/node/
│   ├── types.h, config.h
│   ├── ads1232.h, ads1232.cpp   (polarity fix applied)
│   ├── noise.h, noise.cpp
│   ├── cal.h, cal.cpp
│   ├── scale.h, scale.cpp
│   └── juicebattle.ino
├── hub/
│   ├── main.py, game_engine.py, receiver.py
│   ├── dashboard.py, persona_engine.py
│   └── assets/index.html
└── sessions/
    ├── S001_bootstrap.md
    ├── S002_architecture_phase1.md
    ├── S003_cal_scale_verified.md
    └── HANDOFF_FINAL.md
```

---

## Git status at end of S003

Last commit: S003: cal + scale verified, polarity fix, 3-run validation complete
All firmware and docs committed.
