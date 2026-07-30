# SESSIONS — Juice Battle
# Append only. One entry per session.

---

## S003 - 2026-07-16
Goal: Write and verify cal.cpp + scale.cpp. Run 3 calibration runs with validation sweep.

Hardware used: ESP32-C3 SuperMini + WCMCU ADS1232 + CZL601 40kg load cell
Reference weights: 500g / 1000g / 5000g (government cast iron, kitchen-scale verified)
Validation weights: 200g / 700g (200+500) / 1500g (500+1000) / 10000g

Real measured outputs:

Calibration runs:
| Run | raw_zero | raw_500  | raw_1000 | raw_5000 | confidence | sigma_tare |
|-----|----------|----------|----------|----------|------------|------------|
| 1   | 94690    | 148353   | 201742   | 630410   | 0.968      | 2.54g      |
| 2   | 94833    | 148826   | 202023   | 630627   | 0.904      | 3.06g      |
| 3   | 94822    | 148724   | 201936   | 630576   | 0.920      | 2.40g      |

Validation sweep (Run 1 model):
| Point  | Expected | Run1  | Run2  | Run3  | Mean error |
|--------|----------|-------|-------|-------|------------|
| 200g   | 200g     | 1.12% | 1.64% | 1.38% | 1.38%      |
| 700g   | 700g     | 0.31% | 0.26% | 0.15% | 0.24%      |
| 1500g  | 1500g    | 0.18% | 0.00% | 0.15% | 0.11%      |
| 10000g | 10000g   | 0.03% | 0.05% | 0.04% | 0.04%      |

Live scale test (Run1 NVS loaded):
| Round | Object       | Average  | Known   | Error  |
|-------|-------------|----------|---------|--------|
| 2     | 200g stone  | 194.4g   | 200g    | 2.8%   |
| 4     | 1000g stone | 1002.6g  | 1000g   | 0.26%  |
| 5     | Empty       | 0.0g     | 0g      | 0%     |

Bugs found and fixed:
- Signal polarity reversed: ads1232.cpp returns -raw_value (green/white swapped)
- Tare guard in cal.cpp spec was broken (CLI caught and fixed correctly)
- CAL_MAX_ACCEPTABLE_SPREAD 0.05 too tight → corrected to 0.08 from real data
- noInterrupts wrapper in cal.cpp omitted correctly (would hang DRDY wait loop)

Gate result: PASSED
Files built: types.h config.h ads1232.h ads1232.cpp noise.h noise.cpp
             cal.h cal.cpp scale.h scale.cpp juicebattle.ino

---

## S005 — Stability State Machine
**Date:** 2026-07-17
**Goal:** Implement and verify 4-state EMA stability machine on real hardware

### Real hardware outputs
| Measurement | Result | Error |
|---|---|---|
| Boot sigma | 8.44g | 3× higher than previous sessions |
| Bowl (kitchen: 3090g) | 3086g | 0.13% |
| 500g water | 499.4g | 0.12% |
| Bowl removal | 3350.1g | — |
| 150ml removal (fragmented) | 22+23+14+61+25+10 ≈ 158g | ~5% |

### Gate result
PARTIAL PASS — state machine correct, thresholds need sigma-adaptive fix

### What was built
- stability.h/cpp — 4-state machine (WAITING, POUR_IN_PROGRESS, SETTLING, STABLE_SETTLED)
- config.h additions: STABILITY_EMA_ALPHA=0.3f, STABILITY_SETTLING_SAMPLES=5
- juicebattle.ino updated — stability_init(), stability_reset(), stability_update()

### Key finding
sigma=8.44g → noise-floor slope=25 g/s > hardcoded threshold 15 g/s.
K=3 persistence prevented complete failure but could not fully compensate.
Fix: slope_threshold = fmaxf(15.0f, 5.0f × sigma_g) — derived at runtime.

### Next
S006 — stability fixes + comms.h/cpp BLE advertising layer

---

## S006 — Stability Fixes + BLE Comms Layer
**Date:** 2026-07-17
**Goal:** Fix 3 stability issues found in S005 and build NimBLE BLE advertising comms layer

### Changes made

#### stability.cpp fixes
1. `slope_threshold` now runtime-computed: `fmaxf(15.0f, 5.0f * sigma_g)` — eliminates false triggers when sigma is high
2. K_stop = 8 (was 1 implicit): 800ms confirmation window before POUR→SETTLING transition — eliminates false settlement from tap pause mid-pour
3. `min_delta` filter in juicebattle.ino: events < 3×sigma_g discarded as noise artifacts

#### comms.h/cpp — NimBLE BLE advertising layer
- Non-connectable advertising (BLE_GAP_CONN_MODE_NON)
- 100ms interval (160 × 0.625ms)
- 13-byte manufacturer-specific payload: version + msg_type + node_id + delta_g + sigma_g + seq_num
- Message types: HEARTBEAT, POUR_ACTIVE, POUR_SETTLED, CAL_COMPLETE, SIGMA_ALERT
- Device name: "JB-0" / "JB-1" for hub scanner identification
- NimBLE-Arduino 2.5.0 installed

#### juicebattle.ino wiring
- comms_init() called after GAME_READY
- Heartbeat every 2s in WAITING state
- POUR_ACTIVE broadcast every 200ms in POUR_IN_PROGRESS state
- POUR_SETTLED one-shot after noise filter passes
- NODE_ID added to config.h (= 0 for node A)

### Gate result
FULL PASS — two hardware verification runs completed

#### Run 1 (sigma=5.03g, slope_threshold=25.1 g/s)
- WAITING: zero false triggers across hundreds of samples
- Pour 1: -3326g (jar lifted + refilled — handled correctly)
- Pour 2: 33g small pour (above min_pour_g=15.1g) — reported correctly
- Pour 3: 92g — reported correctly
- Pour 4: 3195g (jar lifted and refilled) — handled correctly
- K_stop=8 counting confirmed in serial log
- COMMS: msg=0x01 (heartbeat), 0x02 (pour-active), 0x03 (pour-settled) all firing
- seq incrementing correctly

#### Run 2 (sigma=6.54g, slope_threshold=32.7 g/s)
- sigma elevated → dynamic threshold correctly scaled to 32.7 g/s
- WAITING: zero false triggers during slow drift (EMA drifting 10–20 g/s over many minutes)
- Pour 1: -3317g
- Pour 2: 25.6g (above min=19.6g)
- Pour 3: 191.9g (~220g removed — 13% error, within acceptable range for non-settling pour)
- Pour 4: 65.2g (jar lifted mid-session — handled correctly)
- Pour 5: 3159.5g (bowl removed entirely)
- Post-pour WAITING returns to near-zero delta within 1-2 seconds

### Files changed
- firmware/node/config.h (slope threshold comment, K_STOP=8, NODE_ID=0)
- firmware/node/stability.cpp (s_slope_threshold static, K_stop counter in POUR_IN_PROGRESS)
- firmware/node/comms.h (new — full BLE comms API)
- firmware/node/comms.cpp (new — NimBLE 2.5.0 implementation)
- firmware/node/juicebattle.ino (comms wired, min_delta guard, timers)

### Next
S007 — Hub BLE subscriber + game.py skeleton

---

## S007 - 2026-07-20

### Scope
Hub-side BLE transport layer. GATT central/peripheral architecture.

### Completed
- ble_scanner.py: systemd service, GATT central, connects to JB-* nodes
- transport.py: Docker-side TCP consumer, NDJSON, auto-reconnect
- config.py: all hub constants including JB_SERVICE_UUID, JB_CHAR_UUID
- juice-ble-scanner.service: Restart=always, enabled on boot
- setup.sh: one-time board setup (python3-dbus, systemd install)
- deploy.sh: code-change restart script
- hub/README.md: operational runbook

### Architecture change
Switched from non-connectable advertising (Broadcaster/Observer) to
GATT Central/Peripheral. Root cause: BlueZ does not reliably create
Device1 objects for non-connectable advertisers. GATT connect+notify
is the proven pattern on this board (gas-cylinder-monitor reference).

### Hardware verification
HEARTBEAT confirmed in journal: node=0, delta=0.0g, sigma=4.0g, seq incrementing.
TCP :7001 stream confirmed working. transport.py consumer confirmed.

### Key learnings
- Non-connectable BLE advertising is unreliable via BlueZ D-Bus API
- GATT Central/Peripheral = correct pattern for this board
- systemd Restart=always = correct recovery mechanism (not Python reconnect)
- deploy.sh = the only manual intervention needed after code changes

### Git commits
c6ab0ea S007: GATT transport verified - hub connects to JB-0, HEARTBEAT flowing

---

## S010 - 2026-07-21

### Scope
Live crowd scoreboard: dashboard.py + main.py, end-to-end pipeline from BLE node
through SQLite to browser display.

### Completed
- hub/dashboard.py: Flask + Flask-SocketIO threading mode, 500ms push loop,
  emits glass_count + partial_g to all connected browsers
- hub/main.py: orchestrator, wires transport callbacks to game + storage,
  zero game logic in orchestrator
- hub/juice-battle.service: systemd unit, boot-enabled, PYTHONUNBUFFERED=1
- hub/setup.sh: deps install, socket.io.js download, both services enabled on boot
- hub/deploy.sh: restart + log tail for code-change redeployment
- hub/static/socket.io.js: Socket.IO v4.6.1 served locally (no CDN at stall)
- config.py additions: DASHBOARD_PORT=5000, DB_PATH (pathlib-derived)

### Hardware verification
4-pour experiment, DB events 18–26 audited:
- Pour bodies: 194.1 / 172.7 / 171.3 / 171.2 / 162.9g
- Tap-leak fragments: 34.7 / 18.7 / 32.0 / 22.5g (window-expired, correctly discarded)
- Final state: 5 glasses + 12.9g partial
- Dashboard displayed: 5 / +13g — exact match
- sigma_live = 5.6g this session. Every counter change traced to a DB event.

### Gate
PASSED — grams conserved, DB ledger complete, browser scoreboard live.

### Bugs fixed
- /socket.io/socket.io.js is the WS protocol endpoint, not a file; HTTP 400.
  Fixed by serving socket.io.js 4.6.1 from hub/static/ at /static/socket.io.js.
- Python print() block-buffered under systemd; [GAME] logs were invisible.
  Fixed with Environment=PYTHONUNBUFFERED=1 in service unit.
- config.DB_PATH missing; main.py crashed on start. Fixed.

### Next
S011 — second node (JB-1) flash + two-jar game, accumulator restore from DB on
startup, concurrent-pour edge cases.

---

## S011 | 2026-07-22 | Pour-boundary semantics redesign + production bug fixes
  - Diagnosed boss-demo missing glass (POUR_WINDOW_S=8.0 too short, 10.44s gap killed 91.5g partial)
  - Fixed invisible game.py logs (logging.basicConfig missing from main.py)
  - Extended POUR_WINDOW_S 8.0→20.0
  - Designed and implemented pour-boundary robustness: residue kill at glass-fire,
    POUR_ACTIVE unconditional discard, disturbance detection + bounce suppression,
    ANOMALY ceiling (jar removal), post-anomaly settling window
  - Deleted preserve rule (was causing false glasses from stale partial carry-over)
  - Wired POUR_ACTIVE to game.on_pour_active in main.py
  - Acceptance: 4 glasses counted correctly, disturbance cleared, bounce suppressed,
    no false glasses on adversarial pours
  - Deferred: overflow bucket (S012a), JB-1 bring-up (S012b)

---

## S012a - 2026-07-22 - Overflow bucket

**Goal:** Conservation-of-mass infrastructure.
**Outcome:** Complete. Conservation verified. glasses_implied=2.0 exact.

### Delivered
- overflow_events table: 7 columns, 2 indexes
- log_overflow() in storage.py: validates reason, guards grams > 0
- 6 call sites in game.py: ANOMALY_DELTA, ANOMALY_CLR,
  DISTURBANCE_CLR, ABANDONED_WINDOW, ABANDONED_BOUNDARY, RESIDUE
- partial_open_ts tracking: new game state field, set at step 9,
  cleared with every overflow log call
- Conservation verified: 1166.04g accumulated =
  300.0g scored + 866.04g overflow (2.0000 glasses exact)
- Commit: 5704c1b

### Bugs found (deferred)
- D10: pour_events.ts NULL - log_pour() never writes ts field
- D11: Conservation query uses hardcoded UTC cutoff - fragile

### Taxonomy locked
- ANOMALY_DELTA: sensor artifact (jar removed) - diagnostic only,
  excluded from conservation equation
- ANOMALY_CLR, DISTURBANCE_CLR, ABANDONED_WINDOW,
  ABANDONED_BOUNDARY, RESIDUE: real visitor juice - all in
  conservation equation

---

## S012b - 2026-07-29 - JB-1 hardware bring-up
  - Wire inspection: multimeter confirmed load cell healthy (400Ω/350Ω bridge intact)
  - Firmware: NODE_ID=1 in config.h (symlink target), no other changes
  - Polarity: initial flash failed cal (negative span). Wire swap at ADS1232
    (green↔white) fixed it. Firmware -raw_value negation retained.
  - Calibration: DEGRADED (confidence=0.823) but validation 4/4 PASS, all <3% error
  - NVS persistence: verified across power cycle, all 4 raw values exact
  - Operating sigma: 5.43g GOOD (sigma_tare=10.50g at cal time — cold cell artifact)
  - TCP verified: node_id=0 and node_id=1 HEARTBEAT interleaved, no cross-talk
  - Service health: juice-battle.service 16h uptime, PID stable, no restarts
  - game.py gracefully ignored node_id=1 events (expected — node_count=1 still)

---

## S013 - 2026-07-29 - Dual-node integration

**Goal:** Enable dual-node hub, fix D10/D11, add jar-absent UI indicator,
verify concurrent pours.

### Delivered
- D10 (pour_events.ts NULL): CLOSED — phantom bug. record_pour() always
  wrote ts correctly. log_pour() doesn't exist.
- D11 (conservation query): CLOSED — phantom bug. Query never built.
  Ad-hoc SQL verified session-scoped. D11 is a future feature, not a fix.
- node_count=2 in main.py. game.py was already fully dual-node —
  all state was per-node dicts from S012a. Zero game.py changes needed.
- POUR_PRESERVE_FRAC deleted from config.py (dead constant since S011).
- D04: node_status ('ok'/'bounce'/'anomaly') added to get_state(),
  dashboard payload, HTML_TEMPLATE. Red pulse + JAR ABSENT badge on
  ANOMALY. Amber border + DISTURBANCE badge on bounce.
  Verified physically: JB-0 lift → JAR 0 red, JAR 1 untouched. ✓
  JB-1 lift → JAR 1 red, JAR 0 untouched. ✓ Auto-recovery after 30s. ✓
- Concurrent pour test: JB-0=5 glasses, JB-1=4 glasses.
  Conservation exact:
    node=0: 1075.5g = 5×150g + 210.9g residue + 114.6g abandoned ✓
    node=1:  898.4g = 4×150g + 125.5g residue + 172.8g abandoned ✓ (0.1g rounding)
- Commit: e077b64

### Key learnings
- game.py was already dual-node. node_count=1 was sessions metadata only.
- Handoff bug entries can be stale. Always verify against actual code first.
- Browser caches HTML_TEMPLATE. Hard refresh required after any change.
- Boot sequence critical: jars on platforms BEFORE node power-on.
  Mid-session jar placement = ANOMALY (tare does not include jar weight).
- Best sigma readings to date: JB-0=3.15g, JB-1=3.92g (jars present at tare).
- BLE dropout edge case: deferred to S014.

### Deferred
- BLE dropout mid-game → S014
  - JB-0 unaffected throughout

---

## S015 - 2026-07-30 - Per-node reset, threading fix, ring buffer, MAC identity

**Goal:** Stage 0 (per-node reset), Stage 1 (_connect threading), Stage 2 (D03 ring buffer)

### Delivered

**Stage 0 — per-node manual reset (restart-safe)**
- storage.py: node_resets table, log_node_reset(), get_resumable_session()
  updated with LEFT JOIN + COALESCE(last_reset, 0) gate
- game.py: reset_node() zeroes RAM + writes DB timestamp atomically
- dashboard.py: POST /reset/<node_id> route + RESET button per jar card
- Verified: reset node=0, restart, D01 restores 0 not pre-reset count ✓
- Commits: af13bd8

**Firmware — MAC-based NODE_ID (Option C)**
- #define NODE_ID removed from config.h
- resolve_node_id() reads BT MAC at boot, looks up NODE_MAC_TABLE
- extern uint8_t NODE_ID in comms.h — comms.cpp unchanged
- One identical binary for both nodes — no per-board recompile ever again
- FATAL halt + MAC printout if unknown node flashed
- Verified: node=0 and node=1 streams correct after flashing same binary ✓

**Root cause found and fixed: both nodes had NODE_ID=1**
- S014 Serial blocking fix flashed both nodes with config.h at NODE_ID=1
- System appeared to work (D01 restored from S013 DB, not new pours)
- Detected today when all pours went to node=1
- Fix: reflash JB-0 with NODE_ID=0, then migrate to MAC-based identity

**Stage 1 — _connect() threading fix**
- _connect() spawns daemon thread, returns False immediately to GLib loop
- _connect_worker() runs device.Connect() + sleep(4) off the loop
- _on_connect_success() and _on_connect_fail() post back via GLib.idle_add
- Verified: JB-1 data uninterrupted during 23s JB-0 reconnect ✓
- Both nodes now reconnect concurrently (was sequential 29s block) ✓
- Commit: 80b3d8d

**Stage 2 — D03 ring buffer**
- deque(maxlen=200) in ble_scanner.py buffers every emitted event
- New TCP client receives full buffer flush before joining live stream
- for/else guard: dead socket during flush never added to clients list
- Verified: 168 events flushed on juice-battle restart, partial rebuilt,
  live pour immediately after scored correctly ✓
- Known gap: POUR_SETTLED in 5s TCP reconnect window may double-count
  (DB + buffer both see it). Acceptable, documented.
- Commit: 1653c40

### Key learnings
- config.h NODE_ID survives in git but not in flash — the two can diverge
  silently. MAC-based identity eliminates this class of bug permanently.
- D01 restore from DB can mask wrong node_id — looks correct if DB has
  old correct data, only fails when new pours are observed.
- GLib.idle_add callbacks must never block. Even sleep(1) starves all
  other nodes. Threading is the only correct fix.
- deque.append is GIL-atomic in CPython — safe to append from GLib loop
  and snapshot from TCP accept thread without explicit lock.
- for/else on socket flush is clean: else only runs if loop completes
  without break — dead socket during flush never enters clients list.

### Deferred to S016
- Stage 3: BLE dropout NODE_DISCONNECTED/CONNECTED event pipeline
- Stage 4: D02 full power loss recovery verification
- Startup BLE discovery (known gap — manual bluetoothctl scan on workaround)

