# Juice Battle — Handoff S016 → S017
Date: 2026-07-30
Session: S016

## Current system state
- JB-0 (MAC 70:AF:09:32:F3:C2): connected, subscribed, node=0 ✓
- JB-1 (MAC 10:00:3B:CD:63:32): connected, subscribed, node=1 ✓
- Firmware: identical binary on both nodes, NODE_ID resolved from BT MAC at boot
- Services: juice-ble-scanner + juice-battle running, boot-enabled
- Dashboard: http://AQ3:5000 — live, reset buttons working, RECONNECTING badge working
- Active DB session: 79 (open, resumable)
- Glass counts at close: node=0: 1 glass, node=1: 4 glasses
- Git HEAD: commit after Stage 3 (S016)

## What works end-to-end (verified, do not re-litigate)
- D01: hub restart restores glass_counts from DB — crowd-invisible ✓
- Per-node manual reset: restart-safe via node_resets table + LEFT JOIN gate ✓
- _connect() threading: GLib loop never blocks during BLE reconnect ✓
- D03 ring buffer: deque(maxlen=200), 168 events flushed and replayed ✓
- MAC-based NODE_ID: one firmware binary, both nodes, correct identity ✓
- Stage 3 BLE dropout pipeline — verified this session:
  - USB pull JB-0 → NODE_DISCONNECTED emitted by scanner ✓
  - game.py receives → node_status[0]='disconnected' ✓
  - RECONNECTING... amber badge appears on JAR 0 within 500ms ✓
  - JB-0 boots, reconnects → NODE_CONNECTED fires ✓
  - game.py: partial_g[0] reset to 0.0, node_status[0]='connected' ✓
  - Badge clears automatically ✓
  - JB-1 uninterrupted throughout all of the above ✓

## Files changed in S016
- hub/ble_scanner.py: emit NODE_DISCONNECTED at top of disconnect handler;
  emit NODE_CONNECTED after subscription confirmed
- hub/game.py: _node_status dict alongside _partial_g; on_node_disconnected
  and on_node_connected handlers; ble_status key in get_state()
- hub/main.py: two new transport.on_event registrations wiring the handlers
- hub/dashboard.py: ble-badge-{n} pill per jar card; setBleStatus() function;
  badge toggled by 500ms _push_loop poll via ble_status in state payload

## S017 opening sequence
1. Confirm both nodes:
   journalctl -u juice-ble-scanner -n 20 | grep -E "subscri|NODE_"
2. Check session:
   sqlite3 hub/data/jb.db "SELECT id, ended_at FROM sessions WHERE ended_at IS NULL;"
3. Verify glass counts:
   sqlite3 hub/data/jb.db "SELECT node_id, SUM(glasses) FROM pour_events WHERE session_id=79 GROUP BY node_id;"
4. Then proceed to Stage 4 Scenario 2 completion (one pour test on JB-0)
5. Then Stage 4 Scenario 3 (full blackout simulation)
6. Then Stage 5 (startup BLE discovery)

## S017 build queue (in order)

### Stage 4: D02 full power loss verification

Scenario 1: hub-only restart → CLOSED in S015 (D01 handles it)

Scenario 2: node-only restart → IMPLICITLY VERIFIED in S016
  During Stage 3 badge test: USB pulled on JB-0, node rebooted, reconnected.
  partial_g reset confirmed. Badge cleared. JB-1 uninterrupted.
  STILL NEEDED: one explicit pour on JB-0 after reconnect to confirm scoring
  works end to end. Expected: count goes 1 → 2. Run this first thing S017.

Scenario 3: full blackout — hub AND nodes cut simultaneously → NOT YET RUN
  This tests something different from a service restart: when bluetooth itself
  restarts, the BlueZ device cache is gone. Scanner startup finds no cached
  devices and hangs waiting. This is the startup BLE discovery gap.
  
  Simulation sequence:
    sudo systemctl stop juice-battle juice-ble-scanner
    sudo systemctl restart bluetooth
    sleep 3
    # Pull both JB-0 and JB-1 USB adapters
    # Wait 5 seconds
    # Plug both back in, let them boot (~15s)
    sudo systemctl start juice-ble-scanner
    sleep 2
    sudo systemctl start juice-battle
    # Second terminal:
    journalctl -u juice-ble-scanner -u juice-battle -f
    # Required workaround until Stage 5:
    sudo timeout 60 bluetoothctl scan on
  
  Success criteria:
    - RESTORED session=79 glass_counts correct
    - NODE_CONNECTED for both nodes after scan
    - Dashboard clean, both badges clear
    - Pour on each jar scores correctly

### Stage 5: Startup BLE discovery
  Problem: after bluetooth restart (full power cycle), BlueZ cache is empty.
  Scanner finds no cached devices. Nodes are never discovered without manual:
    sudo timeout 60 bluetoothctl scan on
  This makes unsupervised stall operation impossible.
  
  Fix: trigger programmatic BLE scan in ble_scanner.py at startup.
  Options to evaluate:
    A) subprocess call to bluetoothctl scan on with timeout
    B) BlueZ D-Bus StartDiscovery directly on the adapter object
  Option B is cleaner (no subprocess, same D-Bus loop already running).
  Pattern already exists in ble_scanner.py's D-Bus setup — extend it.
  
  After Stage 5: Scenario 3 re-run without the manual scan step.
  Success: full power cycle, everything comes back unsupervised.

## Remaining blocking for live stall deployment
- Stage 4 Scenario 3 verification
- Stage 5: Startup BLE discovery (eliminates manual workaround)
- Physical display: browser kiosk mode on crowd-facing screen
- Hub power: confirmed non-laptop 5V source (USB-C PD adapter or similar)

## Known gaps (documented, carry forward)
- D03 double-count: POUR_SETTLED in 5s TCP reconnect window counted by
  both DB restore and buffer replay. Low probability at stall. Documented.
- Startup BLE discovery: manual scan required after bluetooth restart.
  Workaround: sudo timeout 60 bluetoothctl scan on. Fixed by Stage 5.

## Key file locations
Hub:      ~/ArduinoApps/juice_battle/hub/
Firmware: ~/ArduinoApps/juice_battle/firmware/node/
DB:       ~/ArduinoApps/juice_battle/hub/data/jb.db
Services: juice-ble-scanner.service, juice-battle.service
Deploy:   ~/ArduinoApps/juice_battle/deploy.sh

## Hardware state
| Node | MAC               | NODE_ID | sigma_g | Power       | Cal          |
|------|-------------------|---------|---------|-------------|--------------|
| JB-0 | 70:AF:09:32:F3:C2 | 0       | 3.416g  | USB adapter | NVS persisted|
| JB-1 | 10:00:3B:CD:63:32 | 1       | 3.819g  | USB adapter | NVS persisted|
