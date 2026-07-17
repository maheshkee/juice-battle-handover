# CLAUDE.md — Juice Battle
# Current position updated: S006 close / 2026-07-17

## Current position
Phase 1 — ESP32-C3 Firmware. S006 complete and hardware verified.
Phase 2 — Hub (AQ3 Python). S007 next: Hub BLE subscriber + game.py skeleton.

## What was just completed (S006)
- Dynamic slope threshold: fmaxf(15.0f, 5.0f × sigma_g) — eliminates false triggers at high sigma
- K_stop=8: 800ms confirmation window before POUR→SETTLING — eliminates false settlement
- min_delta filter: events < 3×sigma_g discarded as noise artifacts
- comms.h/cpp: NimBLE 2.5.0, non-connectable BLE, 13-byte payload
- juicebattle.ino: all modules wired, comms integrated
- Hardware verified: 2 runs, 9 pours total, zero false triggers, all BLE messages firing correctly
- New learnings: L-013 (EMA drift safe), L-014 (jar lift by slope alone), L-015 (git contamination)

## What is next (S007)
Hub BLE subscriber — scan for JB-0/JB-1 advertisements, parse 13-byte payload
game.py skeleton — process_pour_event(delta_g, sigma_g, node_id, hub_ts)
Hub state machine: WAITING_NODES → GAME_READY → GAME_RUNNING → GAME_PAUSED → GAME_OVER

## Locked rules (non-negotiable)
- Never hardcode thresholds that depend on sigma_live
- Orchestrator law: juicebattle.ino owns zero logic
- NODE_ID lives only in config.h
- Hub = brain (accumulates, decides, scores). Node = sensor (detects, reports).
- Every C++ module returns {value, quality, diagnosis}
- delayMicroseconds(2) on every GPIO edge

---

