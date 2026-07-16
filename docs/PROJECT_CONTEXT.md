# PROJECT CONTEXT — Juice Battle
# One-screen current state. Always replace. Never append.
# Last updated: Session S003 — cal + scale verified

## Where we are
Phase: Phase 1 firmware in progress.
Current chunk: Boot redesign (S004).
System state: cal.cpp + scale.cpp written and hardware-verified. NVS persistent.

## What is working
- ADS1232 HAL: ads1232_read_raw() confirmed stable at 10 SPS
- Noise floor: noise_measure() returns σ_g = 2.4–4.8g (GOOD) across 5 boots
- Calibration: cal_run() + 3 runs completed. Best confidence=0.968. NVS persistent.
- Piecewise model: cal_to_grams() validated 4 points. Worst error 1.64% at 200g.
- Scale: scale_tare() + scale_read() verified. Interactive test loop working.

## What was just done (S003)
- Found and fixed signal polarity bug (green/white CZL601 wires swapped)
- Wrote cal.h / cal.cpp: 3-point piecewise calibration, NVS persistence
- Ran 3 calibration runs, selected Run1 as best (confidence=0.968)
- Validation sweep: 4/4 PASS across 3 independent runs
- Wrote scale.h / scale.cpp: baseline capture, live read, noise clamp
- Redesigned boot flow: baseline = current platform state, not empty platform
- CAL_MAX_ACCEPTABLE_SPREAD corrected to 0.08 from real hardware measurement

## Module status
- types.h        DONE
- config.h       DONE (values locked from real hardware)
- ads1232.h/.cpp DONE (polarity fix applied, wire swap TODO)
- noise.h/.cpp   DONE
- cal.h/.cpp     DONE (verified on hardware, 3 runs)
- scale.h/.cpp   DONE (verified on hardware)
- stability.h/.cpp  NOT STARTED — S005
- comms.h/.cpp      STUB only

## Open questions
- RESOLVED: Does pour validation need real jar? YES — deferred to when jar available
- RESOLVED: Should tare require empty platform? NO — baseline = current state
- OPEN: Wire swap — green/white CZL601 at ADS1232 INNA+/INNA- (TODO in ads1232.cpp)
- OPEN: Noise re-measurement needed under operating load (full jar on platform)

## Next action
S004 — boot redesign implementation:
- Remove one-time NVS write block from juicebattle.ino
- Replace scale_tare() with baseline capture (platform loaded)
- Move noise measurement to after baseline (under operating load)
- Wire swap: swap green/white and remove negation in ads1232.cpp

## Hardware status
- All hardware wired and operational
- Calibration complete (NVS loaded)
- TODO: swap green/white CZL601 wires at ADS1232 INNA+/INNA-

## Key files to know
- docs/ARCHITECTURE.md — system design
- docs/INTERFACE_CONTRACTS.md — data schemas
- docs/HARDWARE_MANIFEST.md — hardware inventory
- docs/LEARNINGS_AND_INSIGHTS.md — bugs and lessons
- docs/RESEARCH.md — verified hardware behaviour
- sessions/HANDOFF_FINAL.md — full project roadmap
