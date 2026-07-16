# S002 - Architecture Complete + Phase 1 Start
# Date: 2026-07-16
# Duration: Full session

## Goal
Lock all architecture decisions. Design calibration system, state machine, game mechanics.
Start Phase 1 firmware. Verify ADS1232 hardware. Confirm noise floor.

## Outcomes

### Architecture (Phase 0 - COMPLETE)
- All decisions locked - see docs/juice_battle_project_bible.html
- Five measurement concepts established as design basis
- Calibration: 3-point piecewise linear, confidence score, pour validation gate
- State machine: 10 states, dual-path detection, volume-based game
- Game: glass count only display, operator-set glass_volume_g, Path A + B

### Hardware verified
- ADS1232 alive. DRDY toggling correctly at 10 SPS.
- Raw counts: -93500 range (zero balance offset - expected, tare handles it)
- Settling pulse bug: without 25th clock pulse, next read catches DOUT transitioning → all-1s → -1 enters Welford → σ = 800g (confirmed)
- Fix: add settling pulse after 24th bit in ads1232_read_raw()
- delayMicroseconds(2) confirmed reliable. delayMicroseconds(1) at edge of reliability.

### Noise floor measured
```
sigma_raw    = 336.18 counts
sigma_g      = 6.23g     QUALITY_GOOD (threshold: GOOD < 10g)
n_collected  = 100/100   (no read errors after settling pulse fix)
environment  = office, ceiling fan on, empty wooden platform
```

### Derived thresholds (from σ_live = 6.23g)
```
STABILITY_SPREAD_THRESHOLD_G   = 25.0g   (4 × σ)
STABILITY_SLOPE_THRESHOLD_GS   = 15.0    (g/s, ~1.5× slope noise floor)
STABILITY_PERSISTENCE_K        = 3       (samples, 0.3s)
SNR                            = 3.9×    (pour 43g/s / slope noise 11g/s)
```

## Files created
- types.h, config.h, ads1232.h, ads1232.cpp, noise.h, noise.cpp, juicebattle.ino
- docs/juice_battle_project_bible.html
- docs/juice_battle_state_machine.html

## Gate result
- Phase 0: COMPLETE
- Phase 1 / noise.cpp: PASSED (σ_live = 6.23g GOOD)

## Next session
Build cal.cpp. Need 100g / 250g / 500g reference weights physically present.
