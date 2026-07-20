# CLAUDE.md — Juice Battle
# Current position updated: S007 close / 2026-07-20

## Current position
Phase 1 — ESP32-C3 Firmware. Complete and hardware verified (S006/S007).
Phase 2 — Hub (AQ3 Python). S007 complete and hardware verified. S008 next.

## What was just completed (S007)
- config.py: all hub constants (BLE identity, TCP ports, message types, game params)
- ble_scanner.py: GATT central, connects JB-*/NOTIFY, TCP NDJSON server :7001, watchdog
- transport.py: Docker-side TCP consumer, callback-based dispatch, auto-reconnect loop
- juice-ble-scanner.service: systemd unit, Restart=always, User=arduino
- setup.sh: one-time board setup (apt python3-dbus, systemd enable+start)
- deploy.sh: redeploy on code change
- hub/README.md: operational runbook
- comms.h/cpp rewritten: GATT peripheral (NimBLE), NOTIFY char, 13-byte binary payload
- Gate: PASSED — HEARTBEAT confirmed in journal, node=0, sigma=4.0g, seq incrementing

## What is next (S008)
Two deliverables — build in order:
1. MSG_DIAG=0x06 firmware message: surgical addition to comms.h/cpp + juicebattle.ino
   fires every 5s from STAB_WAITING, carries current_g (ema_g) in delta_g field
2. storage.py: SQLite jb.db, 4 tables (pour_events, node_health, error_log, sessions)
   + storage_test.py harness to verify writes via transport.py callbacks

## Locked rules (non-negotiable)
- Never hardcode thresholds that depend on sigma_live
- Orchestrator law: juicebattle.ino owns zero logic
- NODE_ID lives only in config.h
- Hub = brain (accumulates, decides, scores). Node = sensor (detects, reports).
- Every C++ module returns {value, quality, diagnosis}
- delayMicroseconds(2) on every GPIO edge

---

