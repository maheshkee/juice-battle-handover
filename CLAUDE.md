# CLAUDE.md — Juice Battle
# Current position updated: S010 close / 2026-07-21

## Current position
Phase 1 — ESP32-C3 Firmware. Complete and hardware verified (S006/S007).
Phase 2 — Hub (AQ3 Python). S010 complete and hardware verified. S011 next.

## What was just completed (S010)
- hub/dashboard.py: Flask + Flask-SocketIO threading mode, 500ms push loop
- hub/main.py: orchestrator, wires transport → game + storage, zero logic
- hub/juice-battle.service: systemd unit, boot-enabled, PYTHONUNBUFFERED=1
- hub/setup.sh: socket.io.js download added, both services boot-enabled
- hub/static/socket.io.js: Socket.IO v4.6.1 served locally (no CDN)
- config.py: DASHBOARD_PORT=5000, DB_PATH added
- Gate: PASSED — 4-pour experiment, DB events 18–26 audited, 5 glasses +13g exact match

## What is next (S011)
- Second node (JB-1): flash firmware, assign NODE_ID=1
- Two-jar game: concurrent-pour edge cases, per-node scoring
- Accumulator restore from DB on startup (see L-019)
- Replay-from-seq on transport reconnect (see L-020)

## Locked rules (non-negotiable)
- Never hardcode thresholds that depend on sigma_live
- Orchestrator law: juicebattle.ino owns zero logic
- NODE_ID lives only in config.h
- Hub = brain (accumulates, decides, scores). Node = sensor (detects, reports).
- Every C++ module returns {value, quality, diagnosis}
- delayMicroseconds(2) on every GPIO edge

---

