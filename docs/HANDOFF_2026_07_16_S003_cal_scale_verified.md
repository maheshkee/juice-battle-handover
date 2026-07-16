# HANDOFF - S003 - cal + scale verified
Date: 2026-07-16

## Goal
Write and verify cal.cpp + scale.cpp. Run 3 calibration runs with full
validation sweep. Confirm NVS persistence. Build interactive scale module.

## Gate result: PASSED

## Files built this session
firmware/node/cal.h
firmware/node/cal.cpp
firmware/node/scale.h
firmware/node/scale.cpp
firmware/node/juicebattle.ino (updated - orchestrates all modules)
firmware/node/ads1232.cpp (polarity fix: returns -raw_value)
firmware/node/config.h (CAL_MAX_ACCEPTABLE_SPREAD=0.08, validation constants)

## Key bug found and fixed
Signal polarity reversed - green/white CZL601 wires swapped at ADS1232.
Fix: ads1232.cpp returns -raw_value.
TODO: swap wires physically and remove the negation.

## Best calibration (NVS loaded)
Run 1: confidence=0.968 sigma_tare=2.54g quality=GOOD
raw_zero=94690 raw_500=148353 raw_1000=201742 raw_5000=630410

## Next session: S004 - boot redesign
See HANDOFF_FINAL for full spec.
