# HANDOFF — S005 Stability State Machine
# Date: 2026-07-17

## Session goal
Implement and verify 4-state EMA stability state machine on real hardware.
Test against full protocol: bowl placement, 500g water, 150ml removal, mid-pour pause.

## Hardware used
ESP32-C3 SuperMini + CZL601 40kg load cell + WCMCU ADS1232 breakout

## Real measured outputs

| Measurement | Result | Error |
|---|---|---|
| Boot sigma (this session) | 8.44g | 3× higher than previous |
| Bowl weight (kitchen: 3090g) | 3086g | 0.13% |
| 500g water addition | 499.4g | 0.12% |
| Bowl removal | 3350.1g | — |
| 150ml removal (fragmented) | 158g total across 6 events | ~5% |

## Gate result
PARTIAL PASS

State machine transitions: all correct.
Accuracy: excellent (0.1–0.2% error).
False triggers: occurred because sigma=8.44g → noise-floor slope=25 g/s exceeded
hardcoded threshold of 15 g/s. K=3 persistence prevented full failure.

## What was built
- firmware/node/stability.h
- firmware/node/stability.cpp
- firmware/node/config.h (additions: EMA_ALPHA, SETTLING_SAMPLES)
- firmware/node/juicebattle.ino (stability wired in)

## Critical finding this session
noise-floor slope = 3 × sigma_g (derived from EMA physics).
Hardcoded 15 g/s threshold is wrong when sigma > 5g.
Fix: slope_threshold = fmaxf(15.0f, 5.0f × sigma_g) — derived at runtime every boot.

## Next session (S006)
Part A: Three stability fixes (dynamic threshold, K_stop=8, min_delta filter)
Part B: comms.h/cpp — NimBLE non-connectable BLE advertising layer
Part C: Wire comms into juicebattle.ino
Part D: Compile, upload, verify serial output
