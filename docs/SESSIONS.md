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
