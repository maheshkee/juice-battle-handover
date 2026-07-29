---
# HANDOFF - Juice Battle
**Last session:** S012b - 2026-07-29
**Board:** AQ3 (arduino@AQ3), project at ~/ArduinoApps/juice_battle/
**Git:** gratiantechnologies/project13

---

## Current state - STABLE ✓

Two-node hardware complete. JB-0 and JB-1 both calibrated, BLE active,
HEARTBEAT flowing to hub. TCP stream carries both nodes interleaved.
Hub game.py still single-node (node_count=1) — S013 enables dual-node.

### Services
- juice-ble-scanner.service: active, boot-enabled, HEARTBEAT from JB-0 and JB-1
- juice-battle.service: active, boot-enabled, 16h uptime, PID stable
- Dashboard: http://AQ3:5000

### Node hardware state

| | JB-0 | JB-1 |
|---|---|---|
| NODE_ID | 0 | 1 |
| Status | flashed, calibrated | flashed, calibrated |
| sigma_g (boot) | 5.006g | 5.435g |
| slope_threshold | 25.0 g/s | 27.2 g/s |
| cal confidence | 0.968 GOOD | 0.823 DEGRADED |
| validation | 4/4 PASS | 4/4 PASS |
| NVS | persisted | persisted |
| Polarity fix | -raw_value | -raw_value + wire swap at ADS1232 |

### JB-1 calibration values (NVS)
raw_zero=83691, raw_500=135137, raw_1000=185136, raw_5000=591869

### JB-1 polarity note
Green/white wires physically swapped at ADS1232 relative to JB-0.
Fix applied: physical wire swap (green↔white at AINP1+/AINN1*).
Firmware -raw_value negation retained — same as JB-0.
Both nodes now behave identically from firmware perspective.

### Hub modules (hub/) — unchanged from S012a
- config.py, game.py, transport.py, ble_scanner.py
- storage.py, dashboard.py, main.py
- node_count=1 still (game.py processes JB-0 only)

---

## Known bugs (fix at S013 start, in order)

### D10 - pour_events.ts is NULL on all rows
log_pour() in storage.py never writes ts field.
Fix: add ts=time.time() to INSERT in log_pour().
Blocks: time-bounded conservation queries, D11.

### D11 - Conservation query uses hardcoded UTC cutoff
Workaround until D10 fixed.
Fix: replace hardcoded timestamp with MIN(pour_events.ts) WHERE session_id=current.

### D12 - cal.cpp diagnosis never printed on failure
Every early return in cal_run() sets result.diagnosis but never Serial.prints it.
"See diagnosis above" message is misleading. Low priority — cosmetic only.
Target: S015-S016.

---

## Next sessions

### S013 - Integration (requires S012b complete ✓)
Start order is strict:
1. Fix D10: pour_events.ts NULL bug in log_pour()
2. Fix D11: conservation query cleanup
3. hub/config.py: node_count=2
4. D04: jar-absent UI indicator (amber/red on ANOMALY)
5. Verify dashboard renders both jars simultaneously
6. Concurrent pour test: both nodes pour at same time
7. Edge cases: simultaneous glass-fire both nodes, one node BLE dropout

### S014 - Resilience
D01: Accumulator restore from DB on restart
D02: Power loss recovery sequence
D03: Transport reconnect — events lost in 5s backoff

### S015-S016
D05: Node maintenance mode for safe jar refill
D06: Boot sequence optimisation
D07: LID_WEIGHT_G config constant
D08: JB-1 physical wire swap (deferred — software fix in place)
D12: cal.cpp diagnosis print fix

---

## Engineering rules (non-negotiable)
- Never hardcode thresholds depending on sigma_live
- NODE_ID only in config.h
- Orchestrator law: main.py owns zero logic
- Git: always cd to project root before git operations
- JCTL headers: 1.8V ONLY
- DB is source of truth, RAM accumulator is cache
- Logging visibility verified before any experiment
- Every partial zeroing must have log_overflow() or explicit comment
