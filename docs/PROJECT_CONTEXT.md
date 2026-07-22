# PROJECT CONTEXT — Juice Battle
# One-screen current state. Always replace. Never append.
# Last updated: Session S010 — 2026-07-21

## Where we are
Phase 2 — Hub (AQ3 Python). S010 closed. Full pipeline live.
Both services (juice-ble-scanner, juice-battle) boot-enabled on AQ3.
Browser scoreboard at http://AQ3:5000 verified by 4-pour audited experiment.

## What is working
- Node → BLE → ble_scanner.py → TCP :7001 → transport.py → game.py + storage.py
- dashboard.py: Flask-SocketIO, 500ms push, glass_count + partial_g to browser
- SQLite jb.db: pour_events, node_health, error_log, sessions tables
- socket.io.js v4.6.1 served locally from hub/static/ (no CDN dependency)

## Next action
S011 — second node (JB-1) flash + two-jar game, accumulator restore from DB on
startup (L-019), concurrent-pour edge cases. Authoritative doc: docs/HANDOFF_FINAL.md.
