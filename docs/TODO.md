# Juice Battle — Active TODO

Last updated: S005 close / S006 prep

## Legend
- [ ] pending
- [x] done
- [~] deferred to production

---

## Hardware

- [ ] **SWAP CZL601 wires** — green and white are reversed on physical hardware.
      Current fix: `ads1232.cpp` returns `-raw_value` (software polarity correction).
      Do physical swap during production hardware build.
      Until then: software correction is in place and working.

---

## Firmware (Node — ESP32-C3)

- [x] **S006 Part A: Fix stability.cpp** — three critical fixes:
      1. Remove `#define STABILITY_SLOPE_THRESHOLD_GS 15.0f` from config.h
         Replace with runtime: `s_slope_threshold = fmaxf(15.0f, 5.0f * sigma_g)` in stability_init()
         Reason: sigma=8.44g → noise-floor slope=25 g/s which exceeded hardcoded 15 g/s threshold
      2. K_stop = 8 (was 3) — 0.8s confirmation before POUR_IN_PROGRESS→SETTLING transition
         Reduces false settlement from tap pause mid-pour
      3. Min delta filter in juicebattle.ino: ignore settled events where delta_g < 3×sigma_g
         Kills noise events (4.9g, 3.2g, etc) automatically

- [x] **S006 Part B: comms.h/cpp** — BLE advertising layer
      Node broadcasts payload via BLE advertising (connectionless, one-way)
      Message types: HEARTBEAT, POUR_ACTIVE, POUR_SETTLED, CAL_COMPLETE, SIGMA_ALERT
      Payload: version(1) + msg_type(1) + node_id(1) + delta_g(4) + sigma_g(4) + seq(2) = 13 bytes

- [x] **S006 Part C: Wire comms into juicebattle.ino**
      comms_init() after GAME_READY
      comms_send_heartbeat() on timer
      comms_send_pour_active() while state==POUR_IN_PROGRESS
      comms_send_pour_settled() when STABLE_SETTLED

- [~] **Second node** — identical firmware, only NODE_ID differs in config.h

---

## Hub (AQ3 Python)

- [ ] **game.py** — hub brain (mirrors gas-cylinder domain.py philosophy)
      pure Python, zero imports from BLE/DB/UI
      process_pour_event(delta_g, sigma_g, node_id, hub_ts) → game snapshot
      Hub owns: partial_accum per jar, glass count, game state, score, cheat detection

- [ ] **Hub game state machine**
      WAITING_NODES → GAME_READY → GAME_RUNNING → GAME_PAUSED → GAME_OVER
      Survives reboots: game score persists in config.json (atomic write pattern)

- [ ] **Partial pour accumulation**
      partial_accum[node_id] += delta_g
      when partial_accum >= glass_volume_g (150g) → count 1 glass, reset accum
      Hub accumulates fragments — node never sees glass_volume

- [x] **BLE subscriber on hub** (S007)
      ble_scanner.py: passive BLE scan, parse 13-byte payload, publish NDJSON over TCP :7001
      transport.py: Docker consumer, callback dispatch, auto-reconnect

- [ ] **Socket.IO dashboard push**
      On every game event: push snapshot to browser (reuse gas-cylinder pattern)

- [ ] **Cheat detection** (prefrontal cortex territory — hub only)
      Pattern: many small events in rapid succession from same node
      Pattern: delta_g spikes without corresponding pour sound (future sensor)

---

## Architecture Migrations (node → hub)

Per hub=prefrontal cortex / node=amygdala principle:
Node complexity must reduce over time. Logic that does not require real-time sensing belongs on hub.

- [ ] glass_volume threshold check → hub (node reports delta_g, hub decides if it's a glass)
- [ ] cheat pattern detection → hub
- [ ] game score → hub
- [ ] partial pour accumulation → hub (already planned)
- [ ] session history → hub

Node should only own:
- ADS1232 bit-bang read
- 3-point calibration
- Baseline capture
- Noise measurement
- EMA stability state machine
- BLE advertising of delta_g events

---

## Session Records

- [x] S001 — Bootstrap, directory structure
- [x] S002 — Hardware wiring complete
- [x] S003 — Calibration verified (confidence=0.968, 4-point, NVS persistent)
- [x] S004 — Boot redesign (scale_capture_baseline, noise under load, both boot paths verified)
- [x] S005 — Stability state machine (4-state EMA machine, tested on hardware)
- [x] S006 — stability fixes + comms.h/cpp BLE layer (hardware verified 2026-07-17)
- [x] S007 — Hub transport layer: BLE scanner, TCP NDJSON, consumer
- [ ] S008 — Dashboard + Socket.IO
- [ ] S009 — Full two-node integration test

---

## Key Engineering Rules (non-negotiable)

1. Orchestrator law: main.py and juicebattle.ino own ZERO logic — they only wire modules
2. NODE_ID lives only in config.h — the single difference between two node binaries
3. Never hardcode thresholds that depend on sigma_live (slope_threshold, min_delta, etc.)
4. Any constant that depends on measured physical state must be computed from measurement at runtime
5. No WiFi credentials or secrets in source code
6. No module imports another module directly on the Python side
7. Every C++ module returns a result struct: {value, quality (GOOD/DEGRADED/FAILED), diagnosis}
8. delayMicroseconds(2) on every GPIO edge during bit-bang operations
9. Hub = prefrontal cortex (accumulates, decides, scores). Node = amygdala (detects, reports).
