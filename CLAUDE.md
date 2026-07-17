# CLAUDE.md — Juice Battle
# Current position updated: S005 close / 2026-07-17

## Current position
Phase 1 — ESP32-C3 Firmware. S005 complete.
S006 next: stability fixes (dynamic slope threshold, K_stop=8, min_delta filter) + comms.h/cpp BLE layer.

## What was just completed (S005)
- 4-state stability state machine implemented and verified on hardware
- Boot sequence redesigned: scale_capture_baseline(), noise under actual load
- Critical finding: hardcoded slope threshold fails when sigma is high
- Fix derived: slope_threshold = fmaxf(15.0f, 5.0f × sigma_g)
- Hub=prefrontal cortex / node=amygdala architecture principle locked
- TODO.md created with full pending work list

## What is next (S006)
Three stability.cpp fixes (dynamic threshold, K_stop=8, min_delta filter)
Write comms.h/cpp — NimBLE non-connectable advertising, 13-byte payload
Wire comms into juicebattle.ino

## Locked rules (non-negotiable)
- Never hardcode thresholds that depend on sigma_live
- Orchestrator law: juicebattle.ino owns zero logic
- NODE_ID lives only in config.h
- Hub = brain (accumulates, decides, scores). Node = sensor (detects, reports).
- Every C++ module returns {value, quality, diagnosis}
- delayMicroseconds(2) on every GPIO edge

---

