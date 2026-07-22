# HANDOFF - Juice Battle
**Last session:** S012a - 2026-07-22
**Board:** AQ3 (arduino@AQ3), project at ~/ArduinoApps/juice_battle/
**Git:** gratiantechnologies/project13, commit 5704c1b

---

## Current state - STABLE ✓

Single-node system (JB-0 only). Overflow bucket live and verified.
Conservation holds. Ready for S012b (JB-1 bring-up).
Fix D10 (pour_events.ts NULL) at start of S013.

### Services
- juice-ble-scanner.service: active, boot-enabled, HEARTBEAT from JB-0
- juice-battle.service: active, boot-enabled
- Dashboard: http://AQ3:5000, Socket.IO push every 500ms

### Hub modules (hub/)
- config.py - all constants
- game.py - pour state machine + overflow call sites (S012a)
- transport.py - TCP consumer, 5s reconnect, msg_filter dispatch
- ble_scanner.py - BLE GATT scanner, publishes to TCP :7001
- storage.py - SQLite jb.db: pour_events + overflow_events (S012a)
- dashboard.py - Flask + Socket.IO
- main.py - orchestrator, zero logic

### Config constants (hub/config.py)

| Constant | Value | Derivation |
|---|---|---|
| GLASS_VOLUME_G | 150.0 | product spec |
| POUR_SIGMA_K | 3.0 | 3-sigma noise gate |
| POUR_MIN_G | 10.0 | fault-mode floor |
| POUR_WINDOW_S | 20.0 | empirical (max gap 18.7s) |
| POUR_MAX_G_FRAC | 3.0 | jar-removal ceiling (×150g = 450g) |
| BOUNCE_SETTLE_S | 5.0 | disturbance rebound suppression |
| ANOMALY_SETTLE_S | 30.0 | post jar-removal settling |

---

## overflow_events schema (S012a)

```sql
CREATE TABLE overflow_events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             REAL    NOT NULL,
    node_id        INTEGER NOT NULL,
    seq            INTEGER,
    reason         TEXT    NOT NULL,
    grams          REAL    NOT NULL,
    window_open_ts REAL
);
```

### Overflow taxonomy (locked)

| reason | grams | conservation? | source |
|---|---|---|---|
| ANOMALY_DELTA | delta_g | NO - diagnostic | Step 5: jar removal reading |
| ANOMALY_CLR | partial | YES | Step 5: partial cleared by anomaly |
| DISTURBANCE_CLR | partial | YES | Step 4: partial cleared by disturbance |
| ABANDONED_WINDOW | partial | YES | Step 8: window expired in POUR_SETTLED |
| ABANDONED_BOUNDARY | partial | YES | POUR_ACTIVE: new visitor boundary |
| RESIDUE | partial remainder | YES | Step 10-11: overshoot after glass fire |

### Conservation equation

```
SUM(accumulated delta_g) = (glasses × 150g)
                          + ANOMALY_CLR + DISTURBANCE_CLR
                          + ABANDONED_WINDOW + ABANDONED_BOUNDARY
                          + RESIDUE
```

ANOMALY_DELTA excluded - sensor artifact, never accumulated.

### Conservation query (temporary - hardcoded boundary until D10 fixed)

```sql
WITH s012a_overflow AS (
    SELECT reason, grams FROM overflow_events
    WHERE node_id=0 AND reason!='ANOMALY_DELTA'
    AND ts > strftime('%s','2026-07-22 10:43:00')
),
s012a_pours AS (
    SELECT delta_g FROM pour_events
    WHERE session_id=59 AND node_id=0
)
SELECT
    ROUND((SELECT SUM(delta_g) FROM s012a_pours),2) AS total_accumulated_g,
    ROUND((SELECT SUM(grams) FROM s012a_overflow),2) AS overflow_accounting_g,
    ROUND((SELECT SUM(delta_g) FROM s012a_pours)
        -(SELECT SUM(grams) FROM s012a_overflow),2)  AS scored_g,
    ROUND(((SELECT SUM(delta_g) FROM s012a_pours)
        -(SELECT SUM(grams) FROM s012a_overflow))/150.0,4) AS glasses_implied;
```

---

## game.py state machine - current rules

### New state field (S012a)

```python
self.partial_open_ts = None  # set when partial 0→nonzero (step 9)
                              # cleared with every overflow log call
```

### Overflow call sites (in execution order)

| Step | Call | Guard | seq | window_open_ts |
|---|---|---|---|---|
| Step 4 | DISTURBANCE_CLR | partial > 0 | current seq | partial_open_ts |
| Step 5 | ANOMALY_DELTA | always | current seq | None |
| Step 5 | ANOMALY_CLR | partial > 0 | current seq | partial_open_ts |
| Step 8 | ABANDONED_WINDOW | partial > 0 | current seq | partial_open_ts |
| Step 9 | set partial_open_ts | partial == 0 | - | - |
| Step 10-11 | RESIDUE | partial > 0 after count | current seq | partial_open_ts |
| POUR_ACTIVE | ABANDONED_BOUNDARY | partial > 0 | None | partial_open_ts |

### POUR_SETTLED rules (unchanged from S011)

1. Dedup: reject if (node_id, seq) seen
2. Bounce suppression: reject if now < bounce_until
3. Post-anomaly suppression: reject if now < settling_until
4. Disturbance: delta < -450g → DISTURBANCE_CLR + clear partial, return
5. ANOMALY: delta > 450g → ANOMALY_DELTA + ANOMALY_CLR + clear partial, return
6. Sign filter: reject delta = 0
7. Noise filter: reject delta < max(POUR_MIN_G, POUR_SIGMA_K × sigma_g)
8. Window check: gap > POUR_WINDOW_S and partial > 0 → ABANDONED_WINDOW + discard
9. Accumulate: if partial==0: set partial_open_ts; partial += delta
10. Count: while partial >= 150g: glasses++, partial -= 150g
11. Residue kill: if new_glasses > 0: RESIDUE log + partial = 0

---

## Known bugs (fix at S013 start)

### D10 - pour_events.ts is NULL on all rows
log_pour() in storage.py never writes the ts field.
INSERT statement is missing the ts column assignment.
Fix: add ts=time.time() to the INSERT in log_pour().
Blocks: time-bounded conservation queries, D11.

### D11 - Conservation query uses hardcoded UTC cutoff
Workaround until D10 fixed. Once ts is populated,
replace hardcoded '2026-07-22 10:43:00' with
MIN(pour_events.ts) WHERE session_id = current_session.

---

## Next sessions

### S012b - JB-1 bring-up (hardware, no hub changes)
- Multimeter polarity check: CZL601 green/white on ADS1232 INNA+/INNA-
- If reversed: software fix is -raw_value in firmware (do NOT physically swap)
- NODE_ID=1 in config.h ONLY - identical binary otherwise
- Three-point calibration: 0g tare, 100g, 250g, 500g reference weights
- Verify sigma_g stable, POUR_SETTLED events with node=1 on TCP :7001
- Do not touch JB-0 config

### S013 - Integration (requires S012b complete)
- Fix D10 first: pour_events.ts NULL bug in log_pour()
- Fix D11: conservation query cleanup
- hub: node_count=2 in game instance
- D04: jar-absent UI indicator (amber/red when ANOMALY fires)
- Verify dashboard renders both jars, no cross-talk
- Concurrent pour test: both nodes simultaneously
- Edge cases: simultaneous glass-fire both nodes, one node BLE dropout

---

## Hardware state
- JB-0: NODE_ID=0, flashed, calibrated, sigma_g~6.84g, HEARTBEAT flowing
- JB-1: NOT YET FLASHED. Needs polarity check before power-on.
- AQ3: SSH arduino@AQ3, Debian Linux, Docker not in use

## Engineering rules (non-negotiable)
- Never hardcode thresholds depending on sigma_live
- NODE_ID only in config.h
- Orchestrator law: main.py owns zero logic
- Git: always cd to project root before git operations
- JCTL headers: 1.8V ONLY
- DB is source of truth, RAM accumulator is cache
- Logging visibility verified before any experiment
- Every partial zeroing must have a log_overflow() call or
  explicit comment (game start only exception)
