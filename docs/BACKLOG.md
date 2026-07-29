# Juice Battle - Deferred Backlog

Items deferred from active sessions. Each item has a
root cause, a target session, and a note on dependencies.

---

## D01 - Accumulator restore from DB on restart
**Why deferred:** Needs schema + restore logic. Service
restart currently zeroes RAM accumulator - score resets
mid-crowd.
**Target:** S014
**Note:** Hub loses power mid-game → score must survive.
Linked to D02.

## D02 - Power loss recovery: hub/node restart sequence
**Why deferred:** Boot sequence problems must be solved
as a unit - partial seq gaps, node reboots while hub
is down.
**Target:** S014
**Note:** Linked to D01 and D03.

## D03 - Transport reconnect: events lost in 5s TCP backoff
**Why deferred:** Needs buffering or seq-gap detection.
**Target:** S014
**Note:** Linked to D02.

## D04 - Jar-absent UI indicator on dashboard
**Why deferred:** Needs ANOMALY events surfaced at
integration layer. Single Socket.IO push from game.py
when ANOMALY fires.
**Target:** S013
**Note:** Small - fold into integration session naturally.

## D05 - Node maintenance mode for safe jar refill
**Why deferred:** Needs firmware command + hub state
machine addition. Operator presses button → node pauses
scoring → refill → resume. Avoids ANOMALY/DISTURBANCE
events during refill.
**Target:** S015
**Note:** Until then, operator turns off node to refill.
Boot sequence must be fast first (D06).

## D06 - Boot sequence optimisation
**Why deferred:** Tare + sigma calibration adds ~15s per
restart. Crowd-invisible recovery requires fast boot.
**Target:** S015
**Note:** Prerequisite for D05 and D02 being seamless.

## D07 - LID_WEIGHT_G: measure physical lid, prevent false glass
**Why deferred:** Lid removal produces ~50g positive
delta - passes noise filter at low sigma, can fire false
glass. Need to measure actual lid mass first, then derive
config constant and filter rule.
**Target:** S015
**Note:** Measure lid on scale before implementing.

## D08 - JB-1 polarity: physical wire swap (green/white)
**Why deferred:** Software fix -raw_value is in place and
working. Do not swap physically until field testing
confirms software fix is stable across all calibration
points.
**Target:** S015-S016
**Note:** Never swap until field testing complete.

## D09 - Operator event ledger
**Why deferred:** Needs dashboard UI - event name, jar
fill amounts per node, session boundary markers,
conservation report per event.
**Target:** S016
**Details:** DB table: events(id, name, node0_fill_g,
node1_fill_g, start_ts, end_ts, notes). Dashboard:
pre-session setup form + live session header. Post-session
report: juice_loaded = scored + overflow + remaining
(operator weighs jar at end). Full physical audit trail
per stall event.

## D10 - Fix pour_events.ts NULL bug
**Why deferred:** log_pour() in storage.py never writes
the ts column - INSERT is missing the field. SQLite
silently stores NULL. Simple one-line fix but requires
verifying the INSERT statement and any callers.
**Target:** S013
**Note:** Blocks any time-bounded conservation query.
Prerequisite for D11.

## D11 - Conservation query: remove hardcoded UTC cutoff
**Why deferred:** Current workaround uses a hardcoded
timestamp string as session boundary. Once D10 is fixed,
query can use pour_events.ts properly with session_id
join.
**Target:** S013
**Note:** Depends on D10.

## D12 - cal.cpp: failure paths never Serial.print diagnosis before returning
**Why deferred:** Every early return in cal_run() sets result.diagnosis but never
Serial.prints it. "See diagnosis above" message is misleading — nothing is printed above.
The diagnosis only surfaces if juicebattle.ino explicitly prints result.diagnosis.
**Fix:** Add Serial.println(result.diagnosis) before every early return in cal_run().
**Priority:** Low — cosmetic/debug UX only, does not affect runtime behaviour.
**Target:** S015-S016

---
*Last updated: S012b - 2026-07-29*
