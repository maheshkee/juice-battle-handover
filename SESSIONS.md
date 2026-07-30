## S014 — 2026-07-30
**Goal:** D01 accumulator restore on hub restart

**Completed:**
- config.py: RESUME_SESSION = True added
- storage.py: _migrate() — idempotent ALTER TABLE pour_events ADD COLUMN glasses_counted INTEGER DEFAULT 0
- storage.py: get_resumable_session() — queries open session, SUMs glasses_counted per node
- storage.py: record_pour() — now persists glasses_counted param
- game.py: start() — state initialisation moved BEFORE resume block (ordering bug fixed)
- game.py: start() — restores _glass_count from DB when RESUME_SESSION=True and open session exists
- game.py: record_pour() call — passes glasses_counted=new_glasses
- dashboard.py: emit imported from flask_socketio
- dashboard.py: _on_browser_connect handler — pushes state immediately on browser connect
- firmware/node/juicebattle.ino: while(!Serial) blocking boot fixed — 3s timeout, then proceeds regardless
- VERIFIED: both nodes boot from USB power adapter without laptop
- VERIFIED: RESTORED session=79 glass_counts={0:1, 1:0} in logs and dashboard
- VERIFIED: JAR 0 shows 1 immediately after restart — no flash to zero

**Bugs found and fixed this session:**
- while(!Serial) in firmware blocked forever with no USB host — nodes never booted from adapter
- game.start() state initialisation ran AFTER restore, wiping restored glass_count
- ble_scanner.py _connect() blocks GLib loop (device.Connect() + time.sleep(4)) — documented, fix deferred to S015 pre-Stage 3

**Pending next session (S015):**
- Per-node manual reset (Option B: node_resets table in DB, restart-safe)
- D03: ring buffer in ble_scanner.py for TCP disconnect window
- BLE dropout: NODE_DISCONNECTED/CONNECTED event pipeline (4 files)
- D02: power loss recovery end-to-end verification
- ble_scanner.py: move _connect() blocking work to thread (pre-Stage 3 prerequisite)
- ble_scanner.py: startup discovery phase (bluetoothctl scan at boot)

**Gate:** PASSED — D01 fully implemented and verified, firmware production-ready
