# CLAUDE.md — Juice Battle project state for Claude CLI sessions
# Read this at the start of every CLI session.

## Current position
Current position: S003 complete. Phase 1 firmware in progress.
cal.cpp + scale.cpp written and verified on hardware.
Next session S004: boot redesign (baseline replaces tare, noise under load).
Session after S005: stability.cpp.

Completed this session:
- Polarity bug found and fixed (negation in ads1232.cpp - TODO swap wires)
- cal.h / cal.cpp written, 3-point piecewise model verified
- 3 calibration runs completed. Best: Run1 confidence=0.968 sigma=2.54g
- Validation sweep: 4/4 PASS. Worst 1.64% at 200g, best 0.03% at 10kg
- scale.h / scale.cpp written, interactive scale verified on hardware
- Boot design corrected: baseline = current platform state (no jar removal)
- Noise must be measured under operating load, not empty platform

Locked values added this session:
- CAL_MAX_ACCEPTABLE_SPREAD = 0.08f (derived from real CZL601 nonlinearity)
- SCALE_NOISE_CLAMP_G = 6.0f
- Best cal NVS: raw_zero=94690 raw_500=148353 raw_1000=201742 raw_5000=630410
- Signal polarity: ads1232.cpp returns -raw_value (software fix, wire swap pending)
