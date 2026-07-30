# Juice Battle — Handoff S015 → S016
Date: 2026-07-30
Session: S015

## Current system state
- JB-0 (MAC 70:AF:09:32:F3:C2): connected, subscribed, node=0 ✓
- JB-1 (MAC 10:00:3B:CD:63:32): connected, subscribed, node=1 ✓
- Firmware: identical binary on both nodes, NODE_ID resolved from BT MAC
- Services: juice-ble-scanner + juice-battle running, boot-enabled
- Dashboard: http://AQ3:5000 — live, reset buttons working
- Active DB session: 79 (open, resumable)
- Git HEAD: 1653c40

## What works end-to-end (verified today)
- D01: hub restart restores glass_counts from DB — crowd-invisible ✓
- Per-node reset: operator resets one jar, other untouched, restart-safe ✓
- Stage 1: JB-1 data uninterrupted during JB-0 reconnect (23s test) ✓
- D03: 168 events flushed to reconnecting hub, partial state rebuilt ✓
- MAC-based NODE_ID: one binary, both nodes, correct identity ✓

## S016 opening sequence
1. Confirm both nodes: journalctl -u juice-ble-scanner -n 20 | grep subscri
2. Check session state: sqlite3 hub/data/jb.db
   "SELECT id, ended_at FROM sessions WHERE ended_at IS NULL;"
3. Then build Stage 3: BLE dropout pipeline

## S016 build queue (in order)

Stage 3: BLE dropout — NODE_DISCONNECTED/CONNECTED pipeline
  - ble_scanner.py: emit NODE_DISCONNECTED on BlueZ disconnect signal
  - ble_scanner.py: emit NODE_CONNECTED after successful subscription
  - transport.py: recognise and pass new event types
  - game.py: node_status='disconnected'/'reconnecting', partial_g reset
    on NODE_CONNECTED
  - dashboard.py: disconnected badge per jar card

Stage 4: D02 — full power loss recovery verification
  Scenario 1: hub-only restart (D01 handles — already verified)
  Scenario 2: node-only restart (partial_g reset on NODE_CONNECTED)
  Scenario 3: full power loss — both hub and nodes cut, restored

Stage 5: Startup BLE discovery
  - Trigger bluetoothctl scan programmatically at scanner startup
  - Eliminates manual 'sudo timeout 60 bluetoothctl scan on' workaround
  - Required for fully unsupervised operation

## Known gaps (documented, not bugs)
- D03 double-count: POUR_SETTLED in 5s TCP reconnect window counted by
  both DB restore and buffer replay. Low probability at stall.
- Startup BLE discovery: after bluetooth restart, manual scan on required.
  Workaround: sudo timeout 60 bluetoothctl scan on

## Key file locations
Hub:      ~/ArduinoApps/juice_battle/hub/
Firmware: ~/ArduinoApps/juice_battle/firmware/node/
DB:       ~/ArduinoApps/juice_battle/hub/data/jb.db
Services: juice-ble-scanner.service, juice-battle.service

## Hardware state
| | JB-0 | JB-1 |
|---|---|---|
| MAC | 70:AF:09:32:F3:C2 | 10:00:3B:CD:63:32 |
| NODE_ID | 0 (from MAC) | 1 (from MAC) |
| sigma_g | 3.416g | 3.819g |
| Power | USB adapter | USB adapter |
| Cal | NVS persisted | NVS persisted |
