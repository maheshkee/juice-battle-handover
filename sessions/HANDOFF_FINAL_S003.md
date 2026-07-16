# HANDOFF_FINAL — Juice Battle
# For: S003 (next chat session)
# Generated: 2026-07-16 end of S002

---

## Current position (one line)
Phase 1 firmware in progress — noise.cpp DONE (σ_live=6.23g GOOD), next is cal.cpp.

---

## What Juice Battle is

Crowd-facing real-time juice pouring competition at market stalls.
Two glass jars of juice compete. Visitors pour into glasses. Volume poured = score.
Score displayed as glass COUNT only (not grams, not ml).
Volume-based game — a glass counts when weight delta ≥ glass_volume_g.

---

## Hardware

| Component | Detail |
|---|---|
| Hub | Arduino UNO Q, hostname AQ3, Debian Linux (MPU) + Zephyr (MCU) |
| Nodes | Two ESP32-C3 SuperMini — one per jar |
| Load cell | CZL601 40kg single-point. 2mV/V sensitivity. |
| ADC | WCMCU ADS1232 breakout. Gain=128 hardware-set. 10 SPS. |
| Jar | 10L glass jar. Tare weight unknown — measured during calibration. |
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

---

## Toolchain

- Arduino IDE with Espressif esp32 package
- Board: ESP32C3 Dev Module
- Upload speed: 921600
- Sketch folder name MUST match .ino filename (Arduino IDE requirement)
- Current: `juicebattle/` folder → `juicebattle.ino`
- Files SCP'd to `C:\Users\mahes\Documents\Arduino\juicebattle\`
- Board files live at `~/ArduinoApps/juice_battle/firmware/node/`

---

## Real measured outputs (S002, do not re-derive, use these)

```
sigma_raw                    = 336.18 counts    VERIFIED on hardware
sigma_g (σ_live)             = 6.23g            QUALITY_GOOD
n_collected                  = 100/100
environment                  = office, ceiling fan on, empty wooden platform
adc_raw_zero                 ≈ -93500 counts    (unloaded, pre-tare)
nominal_counts_per_gram      = 54.0             (derived, pre-calibration estimate)

Derived thresholds (in config.h):
STABILITY_SPREAD_THRESHOLD_G = 25.0g   (4 × σ_live)
STABILITY_SLOPE_THRESHOLD_GS = 15.0    g/s
STABILITY_PERSISTENCE_K      = 3       samples (0.3s)
SNR                          = 3.9×    (pour signal vs slope noise)
```

---

## Firmware files — current state

| File | Status | Notes |
|---|---|---|
| types.h | DONE | Quality enum: GOOD/DEGRADED/FAILED |
| config.h | DONE | Pins, constants, measured thresholds |
| ads1232.h | DONE | HAL interface |
| ads1232.cpp | DONE | Bit-bang driver. Settling pulse mandatory. delayMicroseconds(2). |
| noise.h | DONE | NoiseResult struct + noise_measure() |
| noise.cpp | DONE | Welford online algorithm. VERIFIED σ=6.23g. |
| juicebattle.ino | In progress | Currently noise test harness. Will become orchestrator. |
| cal.h / cal.cpp | NOT STARTED | **NEXT** |
| stability.h/cpp | NOT STARTED | After cal |
| comms.h/cpp | Stub only | After stability |
| weight_engine.h/cpp | Stub only | After stability |

---

## Critical rules — never violate

1. **Settling pulse mandatory**: after 24th bit in ads1232_read_raw(), one extra SCLK HIGH/LOW with delayMicroseconds(2). Without it, next read catches DOUT transitioning → -1 corrupts Welford.
2. **delayMicroseconds(2) not (1)**: ESP32-C3 at 160MHz — 1µs at edge of reliability.
3. **noInterrupts()/interrupts()** wraps the 24-bit read — BLE/WiFi handlers corrupt timing.
4. **noise.cpp runs FIRST** — σ_live must be measured before any threshold is set.
5. **Orchestrator law**: juicebattle.ino owns zero logic — wires modules only.
6. **Result struct contract**: every module returns {value_g, sigma_g, quality, diagnosis}.
7. **Cal data in NVS**: survives power cycle.
8. **glass_volume_g operator-set**: never hardcoded. Hub sends it at start_game().
9. **Display = glass count only**: no grams, no ml to crowd.

---

## cal.cpp spec — what to build next session

### What cal.cpp does (four phases in order)

```
Phase 1 — TARE
  Guard: if current weight > TARE_MAX_GRAMS → FAILED (something on platform)
  Wait for STABLE (spread < STABILITY_SPREAD_THRESHOLD_G)
  Capture 50 block-averaged samples → raw_zero
  Compute σ_tare from the 50-sample window
  Return: {raw_zero, sigma_tare_g, quality, diagnosis}

Phase 2 — THREE REFERENCE WEIGHTS (100g, 250g, 500g)
  For each weight:
    Operator places weight
    Wait for STABLE
    Capture 50 block-averaged samples
    Store raw_100, raw_250, raw_500

Phase 3 — CONFIDENCE CHECK
  Compute three independent cal_factors:
    cf_100 = 100.0f / (raw_100 - raw_zero)
    cf_250 = 250.0f / (raw_250 - raw_zero)
    cf_500 = 500.0f / (raw_500 - raw_zero)
  residual_max = max(cf) - min(cf)
  confidence = 1.0 - (residual_max / cf_mean) / MAX_ACCEPTABLE_SPREAD
  If confidence < 0.85 → DEGRADED

Phase 4 — POUR VALIDATION
  Operator pours 200ml (200g) of water
  Node measures delta via piecewise linear model
  If |delta - 200| / 200 > 0.05 → FAILED

Phase 5 — STORE IN NVS
  Store raw_zero, raw_100, raw_250, raw_500
  Store confidence, sigma_g
```

### The piecewise linear conversion formula (this IS the calibration model)

```cpp
// Given any raw reading, returns grams
float cal_to_grams(int32_t raw) {
    float u  = (float)(raw - raw_zero);
    float u1 = (float)(raw_100 - raw_zero);
    float u2 = (float)(raw_250 - raw_zero);
    float u3 = (float)(raw_500 - raw_zero);

    if      (u <= u1) return (u / u1) * 100.0f;
    else if (u <= u2) return 100.0f + (u - u1) / (u2 - u1) * 150.0f;
    else              return 250.0f + (u - u2) / (u3 - u2) * 250.0f;
}
```

### CalResult struct (add to types.h or cal.h)

```cpp
struct CalResult {
    int32_t raw_zero;
    int32_t raw_100;
    int32_t raw_250;
    int32_t raw_500;
    float   confidence;      // 0.0–1.0
    float   residual_max_g;  // max spread between three cal_factors
    float   sigma_tare_g;    // noise at tare time
    Quality quality;
    char    diagnosis[64];
};
```

### What operator needs physically
- 100g reference weight (±2g accuracy — coins, postal weights, water in measured container)
- 250g reference weight
- 500g reference weight
- 200ml of water for pour validation

---

## State machine — full 10-state design

See `docs/juice_battle_state_machine.html` — open in browser, tap each state.

Key: dual-path detection.
- **Path A** (slope-based): slope < −15g/s for K=3 samples → POUR_IN_PROGRESS → SETTLING → STABLE_SETTLED
- **Path B** (baseline-jump): new stable baseline significantly lower than old, no slope trigger → STABLE_SETTLED directly. Handles push-down tap force masking.

---

## Architecture — all decisions locked

See `docs/juice_battle_project_bible.html` — complete reference. Do not re-discuss locked items.

---

## Project folder structure

```
~/ArduinoApps/juice_battle/
├── docs/
│   ├── juice_battle_project_bible.html    ← complete architecture reference
│   ├── juice_battle_state_machine.html    ← interactive state machine
│   ├── ARCHITECTURE.md
│   ├── HARDWARE_MANIFEST.md
│   ├── INTERFACE_CONTRACTS.md
│   ├── LEARNINGS_AND_INSIGHTS.md
│   └── RESEARCH.md
├── firmware/node/
│   ├── types.h, config.h
│   ├── ads1232.h, ads1232.cpp
│   ├── noise.h, noise.cpp
│   ├── juicebattle.ino
│   └── [cal, stability, comms — next sessions]
├── hub/
│   ├── main.py, game_engine.py, receiver.py
│   ├── dashboard.py, persona_engine.py
│   └── assets/index.html
├── sessions/
│   ├── S001_bootstrap.md
│   ├── S002_architecture_phase1.md
│   └── HANDOFF_FINAL.md
└── tests/
```

---

## Session start checklist

Before writing any code in S003:
- [ ] Read this handoff fully
- [ ] Open docs/juice_battle_state_machine.html in browser — keep open as reference
- [ ] Confirm reference weights are physically available: 100g, 250g, 500g
- [ ] Confirm juicebattle.ino on ESP32-C3 still passes noise test (σ_g < 10g)
- [ ] Confirm current firmware compiles clean

---

## Git status at end of S002

Last commit: `S002: ads1232 settling pulse fix, noise floor confirmed σ=6.23g GOOD`
All firmware and docs committed.
