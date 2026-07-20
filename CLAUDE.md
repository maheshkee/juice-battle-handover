# CLAUDE.md — Juice Battle
# Current position updated: S007 close / 2026-07-20

## Current position
Phase 1 — ESP32-C3 Firmware. Complete and hardware verified (S006).
Phase 2 — Hub (AQ3 Python). S007 complete. S008 next: game.py skeleton.

## What was just completed (S007)
- config.py: all hub constants (BLE identity, TCP ports, message types, game params)
- ble_scanner.py: GLib event-driven passive BLE scanner, TCP NDJSON server :7001, watchdog
- transport.py: Docker-side TCP consumer, callback-based dispatch, auto-reconnect loop
- juice-ble-scanner.service: systemd unit, Restart=always, User=arduino
- setup.sh: one-time board setup (apt python3-dbus, systemd enable+start)
- deploy.sh: redeploy on code change
- Gate: PENDING — requires `bash hub/setup.sh` and node advertising to verify

## What is next (S008)
game.py — hub brain. process_pour_event(delta_g, sigma_g, node_id, hub_ts) → GameSnapshot
Hub state machine: WAITING_NODES → GAME_READY → GAME_RUNNING → GAME_PAUSED → GAME_OVER
Partial pour accumulation: partial_accum[node] += delta_g; count glass when >= 150g

## Locked rules (non-negotiable)
- Never hardcode thresholds that depend on sigma_live
- Orchestrator law: juicebattle.ino owns zero logic
- NODE_ID lives only in config.h
- Hub = brain (accumulates, decides, scores). Node = sensor (detects, reports).
- Every C++ module returns {value, quality, diagnosis}
- delayMicroseconds(2) on every GPIO edge

---

