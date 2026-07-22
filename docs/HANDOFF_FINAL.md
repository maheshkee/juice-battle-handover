# HANDOFF - Juice Battle
**Last session:** S011 - 2026-07-22  
**Board:** AQ3 (arduino@AQ3), project at ~/ArduinoApps/juice_battle/  
**Git:** gratiantechnologies/project13, 15 commits ahead of origin/main

---

## Current state - STABLE ✓

Single-node system (JB-0 only) fully operational. Pour-boundary semantics
redesigned and adversarially tested. Ready for S012a (overflow bucket) then
S012b (JB-1 bring-up) then S013 (integration).

### Services
- juice-ble-scanner.service: active, boot-enabled, HEARTBEAT flowing from JB-0
- juice-battle.service: active, boot-enabled, [game] logs visible in journalctl
- Dashboard: http://AQ3:5000, Socket.IO push every 500ms

### Hub modules (hub/)
- config.py - all constants, see table below
- game.py - pour state machine, fully redesigned S011
- transport.py - TCP consumer, 5s reconnect, msg_filter dispatch
- ble_scanner.py - BLE GATT scanner, publishes all message types to TCP :7001
- storage.py - SQLite pour_events (schema unchanged)
- dashboard.py - Flask + Socket.IO
- main.py - orchestrator, zero logic, wires: POUR_SETTLED + POUR_ACTIVE → game

### Config constants (hub/config.py)

| Constant | Value | Derivation |
|---|---|---|
| GLASS_VOLUME_G | 150.0 | product spec |
| POUR_SIGMA_K | 3.0 | 3-sigma noise gate |
| POUR_MIN_G | 10.0 | fault-mode floor |
| POUR_WINDOW_S | 20.0 | empirical (max observed gap 18.7s) |
| POUR_MAX_G_FRAC | 3.0 | jar-removal ceiling (×GLASS_VOLUME_G = 450g) |
| BOUNCE_SETTLE_S | 5.0 | disturbance rebound suppression window |
| ANOMALY_SETTLE_S | 30.0 | post jar-removal settling suppression |

POUR_PRESERVE_FRAC deleted - preserve rule caused false glasses, removed permanently.

---

## game.py state machine - current rules (in order of execution)

For each POUR_SETTLED event:
1. Dedup: reject if (node_id, seq) already seen
2. Bounce suppression: reject if now < bounce_until
3. Post-anomaly suppression: reject if now < settling_until
4. Disturbance: if delta < -(GLASS_VOLUME_G × POUR_MAX_G_FRAC):
   - clear partial, set bounce_until, log DISTURBANCE, return
5. ANOMALY ceiling: if delta > GLASS_VOLUME_G × POUR_MAX_G_FRAC:
   - log ANOMALY, set settling_until, zero partial, return
6. Sign filter: reject delta = 0
7. Noise filter: reject delta < max(POUR_MIN_G, POUR_SIGMA_K × sigma_g)
8. Window check (_boundary_check): if gap > POUR_WINDOW_S and partial > 0:
   - discard partial unconditionally, log "window expired"
9. Accumulate: partial += delta
10. Count: while partial >= GLASS_VOLUME_G: glasses++, partial -= GLASS_VOLUME_G
11. Residue kill: if new_glasses > 0: partial = 0.0
12. DB write, dashboard push

For POUR_ACTIVE:
- If gap > POUR_WINDOW_S and partial > 0: discard partial unconditionally
- Always refresh last_ts

---

## Key design decisions locked

**Per-person semantics:** glass count = servings to people, not cumulative volume.
A person pours, sees their glass counted. GLASS_VOLUME_G is the threshold per pour.

**Residue kill at glass-fire:** overshoot (e.g. 10g after 160g pour) belongs to
the visitor who just completed. Zeroed immediately. Cannot bleed into next visitor.

**POUR_ACTIVE = boundary detector:** fires only when slope detector sees real flow.
Slow drips never trigger it. POUR_ACTIVE after silence = new visitor starting.
Always discards stale partial. No size test.

**No preserve rule:** partial = 50g at expiry is indistinguishable from abandoned
pour. False glass risk > missed glass risk. Unconditional discard.

**Disturbance symmetry:** large negative delta clears partial AND suppresses rebound.
Bounce window = BOUNCE_SETTLE_S. Protects against hand slam, object placement.

**Jar removal defense:** delta > 450g → ANOMALY, not scored. Post-anomaly settling
window prevents oscillation artifacts from accumulating.

**Conservation of mass (deferred to S012a):**
total_juice = (glasses × GLASS_VOLUME_G) + overflow_g
Overflow bucket routes: RESIDUE, ABANDONED, DISTURBANCE, ANOMALY events.
Storage.py schema change required.

---

## Next sessions

### S012a - Overflow bucket (prerequisite: schema change)
- Add overflow_events table to storage.py
- Route discarded/anomaly grams from game.py to storage.log_overflow()
- Verify mass conservation: sum(pour_events.delta_g) = glasses×150 + overflow
- No UI change needed, logs only

### S012b - JB-1 bring-up
- Multimeter polarity check: CZL601 green/white on ADS1232 INNA+/INNA-
- If reversed: software fix is -raw_value in firmware (do NOT physically swap yet)
- NODE_ID=1 in config.h ONLY - identical binary otherwise
- Three-point calibration: 0g (tare), 100g, 250g, 500g reference weights
- Verify sigma_g stable, POUR_SETTLED events flowing to TCP :7001 with node=1
- Do not touch JB-0 config

### S013 - Integration (requires S012a + S012b complete)
- hub: node_count=2 in main.py game_inst.start()
- Verify dashboard renders both jars, no cross-talk
- Concurrent pour test: both nodes simultaneously
- Edge cases: simultaneous glass-fire both nodes, one node BLE dropout

---

## Known gaps (open)
- Accumulator restore from DB on restart (service restart = visible counter reset)
- Transport reconnect: events lost during 5s TCP backoff
- LID_WEIGHT_G config tag (deferred analytics sugar - measure physical lid first)

---

## Hardware state
- JB-0: NODE_ID=0, flashed, calibrated, sigma_g~6.84g, on platform, HEARTBEAT flowing
- JB-1: NOT YET FLASHED. Needs polarity check before power-on.
- AQ3: SSH arduino@AQ3, Debian Linux, Docker not in use for this project

## Engineering rules (non-negotiable)
- Never hardcode thresholds depending on sigma_live
- NODE_ID only in config.h
- Orchestrator law: main.py owns zero logic
- Git: always cd to project root before git operations
- JCTL headers: 1.8V ONLY
- DB is source of truth, RAM accumulator is cache
- Logging visibility verified before any experiment
