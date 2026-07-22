# S011 - Pour Boundary Semantics Redesign
**Date:** 2026-07-22  
**Status:** CLOSED ✓

## What was built
Complete redesign of pour-boundary detection in game.py. Replaced fragile
fixed-window timing with event-driven boundary rules derived from physical
first principles.

## Production bug fixed
Boss demo: glass 4 missed. Root cause: events 40→41, gap 40→41 = 10.44s >
POUR_WINDOW_S=8.0. 91.49g discarded. 102.65g alone < 150g. No glass counted.
Fix: window extended to 20.0s AND residue-kill at glass-fire.

## Config constants added (all derived from GLASS_VOLUME_G)
- POUR_PRESERVE_FRAC = 1/3   - DELETED (see below)
- POUR_MAX_G_FRAC    = 3.0   - single delta > 3 glasses = anomaly
- BOUNCE_SETTLE_S    = 5.0   - suppress events after disturbance
- ANOMALY_SETTLE_S   = 30.0  - suppress events after jar removal

## game.py changes
1. Residue kill: if new_glasses > 0: partial = 0.0 (immediate, not deferred)
2. on_pour_active: unconditional discard when gap > POUR_WINDOW_S (no size test)
3. _boundary_check: unconditional discard (preserve rule deleted)
4. Disturbance detection: delta < -(GLASS_VOLUME_G × POUR_MAX_G_FRAC) →
   clear partial + set bounce_until + return
5. Bounce suppression: events arriving before bounce_until → suppressed
6. ANOMALY ceiling: delta > GLASS_VOLUME_G × POUR_MAX_G_FRAC → log, return,
   set settling_until, zero partial
7. Post-anomaly suppression: events before settling_until → suppressed
8. Noise filter log bug fixed (missing format arguments at line ~106)

## main.py change
transport.on_event(game_inst.on_pour_active, msg_filter='POUR_ACTIVE')
POUR_ACTIVE was flowing over TCP since day one, never subscribed.

## Adversarial tests passed
- Overshoot glass (190g) → partial=0.0 at fire ✓
- Multi-event accumulation (4 events, 283g) → 1 glass ✓
- Disturbance (-686g) → partial cleared, rebound suppressed, next pour clean ✓
- 4 consecutive glasses → counts 1,2,3,4 no carry-over ✓
- Jar anomaly (461g) → ANOMALY logged, not scored ✓

## Deferred
- Overflow bucket: S012a (storage.py schema, game.py routing, mass conservation)
- JB-1 bring-up: S012b (polarity, wiring, NODE_ID=1, three-point cal)
