---
# HANDOFF - Juice Battle
**Last session:** S013 - 2026-07-29
**Board:** AQ3 (arduino@AQ3), project at ~/ArduinoApps/juice_battle/
**Git:** gratiantechnologies/project13  HEAD: e077b64

---

## Current state - STABLE ✓

Full dual-node system verified end-to-end. Both nodes calibrated, BLE
active, concurrent pours working, conservation exact per node.

### Services
- juice-ble-scanner.service: active, boot-enabled
- juice-battle.service: active, boot-enabled, node_count=2, session_id=79
- Dashboard: http://AQ3:5000

### Node hardware state

| | JB-0 | JB-1 |
|---|---|---|
| NODE_ID | 0 | 1 |
| sigma_g (best boot) | 3.15g | 3.92g |
| slope_threshold | 15.8 g/s | 19.6 g/s |
| cal confidence | 0.968 GOOD | 0.823 DEGRADED |
| validation | 4/4 PASS | 4/4 PASS |
| NVS | persisted | persisted |
| Polarity fix | -raw_value | -raw_value + wire swap at ADS1232 |

### Hub modules — current state
- config.py: POUR_PRESERVE_FRAC deleted. All other constants unchanged.
- game.py: fully dual-node. All per-node state in dicts {0:...,1:...}.
  node_status ('ok'/'bounce'/'anomaly') exposed in get_state().
- storage.py: record_pour() writes ts correctly. overflow_events per-node.
- dashboard.py: badge CSS, badge HTML, node_status JS handler all present.
- main.py: game_inst.start(node_count=2)
- transport.py, ble_scanner.py: unchanged from S012b.

### S013 verification
- JB-0: 5 glasses, 1075.5g, conservation exact
- JB-1: 4 glasses, 898.4g, conservation exact (0.1g rounding)
- Concurrent pours: interleaved journal, zero cross-contamination
- D04: verified physically both nodes

---

## Known bugs — none active

D10 and D11 were phantom bugs. Closed in S013.

---

## Operational notes (critical)

**Boot sequence:**
1. Jars on platforms first
2. Power hub
3. Power nodes
Nodes tare at boot. Mid-session jar placement = ANOMALY.

**Lids:** Remove before game starts. Never during play.
After lid removal wait 6s (BOUNCE_SETTLE_S=5s) before pouring.

**Browser:** Hard refresh (Ctrl+Shift+R) after any HTML_TEMPLATE change.

---

## Next sessions

### S014 - Resilience
D01: Accumulator restore from DB on restart
D02: Power loss recovery — hub/node restart sequence
D03: Transport reconnect — events lost in 5s TCP backoff
BLE dropout mid-game: one node drops, other continues, dropped shows
disconnected state on dashboard.

### S015-S016
D05: Node maintenance mode for safe jar refill
D06: Boot sequence optimisation (~15s tare+sigma)
D07: LID_WEIGHT_G config constant
D08: JB-1 physical wire swap (deferred, software fix in place)
D12: cal.cpp diagnosis never printed on failure (cosmetic)

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
- Boot sequence: jars on platform BEFORE node power-on
