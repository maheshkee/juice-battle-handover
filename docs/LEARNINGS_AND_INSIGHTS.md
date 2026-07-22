# LEARNINGS AND INSIGHTS — Juice Battle
# Append only. Format: L-NNN: [what we learned and why it matters]

## Session S001 — Bootstrap

L-001: The gas monitor bit-bang lesson (delayMicroseconds(1) on every GPIO edge) transfers
  directly to ADS1232 on ESP32-C3. The MCU is fast enough to violate the ADC's timing spec
  without explicit delays. Never assume a delay is unnecessary on a fast MCU.

L-002: The ADS1232 has a very different interface from HX711 despite both being 24-bit ADCs.
  HX711 has dedicated DOUT and SCK pins. ADS1232 shares DRDY with DOUT on a single pin.
  Always read the datasheet — do not assume two 24-bit ADCs work the same way.

L-003: The modular firmware architecture from the gas monitor project is worth carrying forward
  unchanged as a pattern. The value is not in the code itself but in the discipline:
  one module, one job, result struct with quality field. This prevents "blob" sketches.

## Session S002 — ADS1232 HAL + Noise Floor

## Tap force contamination (identified S002)
Hand force on push-down taps transfers vertically through the jar into the load cell.
Slope detection masked during pour. Two mitigations:
1. Hardware: prefer side-lever taps (horizontal force, invisible to load cell)
2. Software: baseline-jump detection (Path B) as fallback - volume correct, no real-time animation
Both mitigations are implemented in state_machine.cpp.

## Next: firmware stubs
- firmware/node/stability.h / stability.cpp
- comms.h / comms.cpp already stub

## Key rules confirmed this session
- ads1232 settling pulse (25th clock): MANDATORY. Without it, next read catches DOUT transitioning — all-1s → -1 corrupts Welford.
- delayMicroseconds(2) NOT delayMicroseconds(1) — ESP32-C3 timing margin.
- noInterrupts() / interrupts() block: mandatory for 24-bit read integrity.
- ADS1232_READ_ERROR = INT32_MIN sentinel. -1 is NOT an error (0xFFFFFF = valid negative value... actually it IS an error — add all-1s guard).
- noise.cpp must run BEFORE cal.cpp. σ_live sets all thresholds.

## Design decisions locked (S002)
- Display: glass COUNT only. No grams. No ml. Eliminates density + flickering.
- glass_volume_g: operator-set at game start. Default 150g (150ml glass). Never hardcoded.
- Detection: Path A (slope) + Path B (baseline-jump). Both mandatory.
- Tap force: push-down taps mask slope. Path B handles this. Prefer side-lever taps.
- Jar: 10L glass jar. Tare weight unknown — cal.cpp will measure it.
- Glass: 150ml per glass (operator-configurable).
- σ_live = 6.23g confirmed for this environment. Re-measure at deployment stall.

## Known issues / blockers
None. Clean state.

## Reference documents
- docs/juice_battle_project_bible.html — complete architecture + concepts + roadmap
- docs/juice_battle_state_machine.html — interactive 10-state machine explorer
- sessions/S002_architecture_phase1.md — full session record (create via CLI)

---

## L-001 - ADS1232 settling pulse mandatory
Date: 2026-07-16
Without one additional clock pulse after the 24th data bit, the next
ads1232_read_raw() call catches DOUT mid-transition (going HIGH after
conversion). All 24 bits read as 1 → value = 0xFFFFFF → sign-extended
to -1. -1 is not INT32_MIN so it passes the error guard and enters
Welford as a "valid" reading. With real readings near -93500 and -1
alternating, Welford correctly reports σ_raw ~ 43000 counts ~ 800g.
Fix: one settling pulse (SCLK HIGH/LOW with delayMicroseconds(2)) after
the 24th bit. Confirmed by adsrawcounttest.ino giving clean readings.
Verified: σ_raw dropped from 43364 → 336, σ_g from 803g → 6.23g.

## L-002 - delayMicroseconds(2) not (1) for ADS1232 on ESP32-C3
Date: 2026-07-16
ESP32-C3 at 160MHz: delayMicroseconds(1) is at the edge of reliability
due to function call overhead. delayMicroseconds(2) provides safe margin.
adsrawcounttest.ino (user-written, clean results) used delayMicroseconds(2)
throughout. Adopted as project standard for all ADS1232 GPIO edges.
Verified: all 250 raw readings in adsrawcounttest.ino valid with 2µs.

## L-003 - σ_live is the single number that sets all detection thresholds
Date: 2026-07-16
Every threshold in the system derives from one measurement: σ_live.
Spread threshold = 4 × σ. Slope noise floor = σ × √2 × SPS / M.
Slope threshold = 1.5 × slope noise. Persistence K from SNR requirement.
If σ_live changes (noisier environment), all thresholds recalculate.
This is why noise.cpp runs first — before cal, before stability, before
anything else. σ_live = 6.23g confirmed for office environment.
At deployment stall, re-measure σ_live and update config.h derived values.

## L-004 - Tap force contaminates slope detection on push-down taps
Date: 2026-07-16
A visitor's hand on a push-down tap transfers vertical force through the
jar into the load cell. The cell reads: (jar weight - juice leaving) +
hand force. Net result: slope may appear flat or positive during an active
pour. Path A (slope detection) misses the pour. Fix: Path B (baseline-jump
detection) runs in parallel — catches the weight difference after the
visitor walks away. Volume accuracy is identical in both paths. Only
difference: Path A enables real-time "pouring" animation, Path B cannot.
Hardware mitigation: side-lever taps (horizontal pivot) transfer force
laterally, not vertically. Load cell is blind to horizontal force.
Prefer side-lever taps at all stall deployments.

## L-005 - Welford online algorithm preferred over sum-of-squares for embedded σ
Date: 2026-07-16
Naive variance: collect all N samples, compute mean, sum squared deviations.
Problems: (1) requires N×4 bytes heap allocation, (2) catastrophic
cancellation when mean ~ 2,000,000 counts and variance is tiny.
Welford: single pass, O(1) memory, numerically stable. Tracks deviation
from a RUNNING mean, not a precomputed mean. Eliminates both problems.
Used in noise.cpp. Correct algorithm for all future σ computations in
this firmware.

## L-006 - Glass count only: eliminates density and flickering simultaneously
Date: 2026-07-16
Problem: displaying grams requires density to convert to ml (juice ≠ water).
Displaying EMA weight causes σ flickering visible to crowd. Both solved
by displaying only glass count (integer). Count only increments when a
whole glass_volume_g delta is confirmed. No conversion. No flicker.
Development mode still shows raw EMA weight — flicker there is diagnostic
(proves sensor alive). Single flag in dashboard switches modes.

---

## Session S003 — Cal + Scale verified

## L-007 - Signal polarity is invisible to noise measurement
Date: 2026-07-16

WHY: Noise is variance - it is symmetric around the mean. A reversed signal
has the same variance as a correct signal. noise.cpp passed with σ=6.23g even
with green/white wires swapped because Welford computes spread, not direction.
Only calibration catches polarity errors because it checks whether a known weight
makes the reading increase or decrease.

Rule derived: Never assume noise test = full hardware validation.
Noise GOOD confirms ADC is alive. It does not confirm signal direction.

Verified: Hardware showed raw_500 ≈ raw_zero with weight on platform.
Fixed by returning -raw_value in ads1232.cpp.

## L-008 - Load cell nonlinearity physics
Date: 2026-07-16

WHY: cf_100 > cf_500 (lower sensitivity at low loads) because at small deflections,
constant-magnitude effects (mounting friction, epoxy compliance, residual pre-stress)
represent a larger fraction of total signal. At high loads, beam deflection dominates
and these effects become negligible fractions. The CZL601 shows ~1.2% nonlinearity
across 0-5000g range - real, measurable, correctable with piecewise model.

Rule derived: Single-point calibration is wrong everywhere except the calibration point.
Three-point piecewise linear corrects nonlinearity without polynomial complexity.

Verified: cf_500=0.009317, cf_1000=0.009341, cf_5000=0.009333 - monotonic increase
then slight drop, consistent across 3 independent runs.

## L-009 - Confidence score tests internal consistency, not external truth
Date: 2026-07-16

WHY: Confidence measures agreement between three cal_factors. Any systematic error
that shifts all three reference readings by the same amount (e.g. bad raw_zero from
a hidden object under the platform during tare) will not appear in confidence -
all three cal_factors shift identically and still agree perfectly. Confidence can
be 0.99 while the model is systematically wrong everywhere.

Rule derived: Confidence = necessary but not sufficient. Pour validation with a
known weight is required as the external ground truth check. Confidence alone
cannot detect bad raw_zero.

Verified: Designed pour validation to use 5000g base load + 500g delta stone
to test operating segment (1000-5000g) not empty-platform segment.

## L-010 - Boot baseline must capture current platform state
Date: 2026-07-16

WHY: In production, the jar never leaves the platform. Power loss is a normal event.
Requiring an empty platform for tare means the operator must remove a full 10L jar
on every reboot - unacceptable. The correct design: capture whatever is currently
on the platform as the new baseline. All deltas are measured from that point forward.
The hub owns game state - the node just needs a reference point to measure changes from.

Rule derived: Tare ≠ empty platform. Baseline = current platform state.
These are only identical during initial installation.

## L-011 - Noise must be measured under operating load
Date: 2026-07-16

WHY: Noise is a property of the signal chain under its actual operating conditions.
The load cell beam under 3000g is deflected - the strain gauge is in its operating zone.
Noise measured here is what stability.cpp will actually see during pour detection.
Noise measured on an empty platform is a different mechanical state and gives
thresholds that may be wrong when the jar is loaded.

Rule derived: Measure σ_live after baseline is captured, with the current platform
load in place. This is more accurate and requires no special setup condition.

## L-012 - CAL_MAX_ACCEPTABLE_SPREAD must be derived from real hardware
Date: 2026-07-16

WHY: The threshold separating GOOD from DEGRADED confidence cannot be chosen
theoretically. It depends on the specific load cell's nonlinearity. The CZL601
showed ~1.2% natural nonlinearity (residual_max/cf_mean) across 3 runs.
Setting CAL_MAX_ACCEPTABLE_SPREAD=0.05 (5% boundary) made confidence=0.763
on a perfectly good calibration. Correct value derived from measurement: 0.08.

Rule derived: Hardware thresholds must be derived from real measurements,
not assumed from datasheets or intuition. Always measure first, threshold second.

Verified: confidence=0.968 with CAL_MAX_ACCEPTABLE_SPREAD=0.08 on Run1.

---

## L-009 — Noise-floor slope scales with sigma, not with hardware
**Date:** 2026-07-17

**WHY from first principles:**
EMA update equation: EMA_new = alpha × sample + (1-alpha) × EMA_old
Change per step from pure noise: delta_EMA ≈ alpha × noise_sample
With alpha=0.3, dt=0.1s: noise-floor slope = 0.3 × sigma / 0.1 = 3 × sigma_g

When sigma=3g → noise-floor slope ≈ 9 g/s → threshold 15 g/s = 1.7× above noise ✓
When sigma=8.44g → noise-floor slope ≈ 25 g/s → threshold 15 g/s = 0.6× noise ✗

A hardcoded threshold that works at sigma=3g will fail at sigma=8.44g.
The threshold is not a property of the hardware. It is a property of the current
noise floor. Therefore it must be derived from the measured noise floor at boot.

**Rule:** slope_threshold = fmaxf(15.0f, 5.0f × sigma_g)
Multiplier 5 gives 1.7× safety margin above noise floor at any sigma value.

**Verified:** Hardware test 2026-07-17. sigma=8.44g caused false triggers at
threshold=15 g/s. Formula predicts correct threshold of 42 g/s for that session.

---

## L-010 — Physical constants vs measured constants: never confuse them
**Date:** 2026-07-17

**The rule:**
Physical constants (glass_volume=150ml, K_stop=8, speed of light) → hardcode fine.
Measured constants (sigma_g, baseline_g, slope_threshold) → compute at runtime, always.

**Why it matters:**
sigma_g changes between boots due to: load cell mechanical state after high-load/unload
cycles, temperature change, platform seating shift. Any threshold derived from sigma_g
must be recomputed from the current sigma measurement every boot.

Hardcoding a threshold that depends on sigma is the same error as hardcoding a calibration
factor without measuring it. The hardware is not the same every time you turn it on.

**General principle:** if it depends on the physical state of your specific hardware in
its specific environment at this moment — measure it, don't assume it.
This is why boot runs 5 steps instead of 1. Every step measures something that could
have changed since last time.

---

## L-011 — Hub = prefrontal cortex, node = amygdala
**Date:** 2026-07-17

**The model:**
Amygdala (node): fast, reactive, stateless beyond its detection cycle.
Senses the environment, detects change, fires an event. No reasoning.
Does not ask "what does this mean?" Only asks "did something happen?"

Prefrontal cortex (hub): slow, deliberate, contextual, persistent.
Receives raw signals, applies knowledge, decides meaning, stores history.

**Juice Battle mapping:**
Node reports: delta_g (what changed), sigma_g (measurement quality), node_id.
Node never knows: score, glass_volume, game state, player identity, history.

Hub decides: does this delta cross the glass threshold?
Hub accumulates: partial_accum += delta_g; when >= 150g → 1 glass counted.
Hub owns: game state, score, history, dashboard, cheat detection.
Hub survives reboots: node cannot know what happened before its last boot.

**Consequence for fragmented pours:**
A 150ml pour fragmented into 22+35+61+32g across 4 events is correct behaviour
from the hub's perspective. Hub accumulates fragments. Total = 150g = 1 glass.
The node did its job correctly by reporting each settled event accurately.

**Architecture law derived from this:**
Node complexity must migrate to hub over time. Any logic that does not require
real-time sensing (accumulation, threshold decisions, game scoring, cheat detection)
belongs on the hub. Node's only job is to be the best possible sensor.

---

## L-012 — Atomic config writes prevent state corruption on power loss
**Date:** 2026-07-17

**Observed in gas-cylinder-monitor hub (domain.py _atomic_write_config):**
Write to config.json.tmp, then os.rename(tmp, config_path).
rename() is atomic on Linux — either the old file survives or the new one does.
A power cut during write cannot produce a half-written config.

**Why this matters for Juice Battle hub:**
Game score and session state persist in config.json on the hub.
If power cuts during a write, a corrupted config means lost game state.
Juice Battle hub must implement the same atomic write pattern.

**Rule:** Every config write on the hub goes through:
  1. Write complete new content to config.json.tmp
  2. fsync() to flush kernel buffer to disk
  3. os.rename('config.json.tmp', 'config.json')
  Never write directly to config.json.

---

## L-013 — EMA drift from slow liquid loss stays below slope_threshold
**Date:** 2026-07-17

**Observed:** EMA drifting 10–20 g/s over many minutes during Run 2 (sigma=6.54g,
slope_threshold=32.7 g/s). Zero false POUR_IN_PROGRESS triggers.

**Why:** Slow condensation or minor leak produces a gradual baseline drift.
EMA tracks this drift slowly — each step is alpha × (tiny loss) ≈ 0.3 × ~0.01g = 0.003g.
The resulting instantaneous slope stays well below threshold even over many minutes.

**Confirmed:** Dynamic threshold formula fmaxf(15, 5×sigma) provides correct margin
against slow environmental drift at any measured sigma value.
A hardcoded 15 g/s threshold would also survive slow drift — the margin is substantial —
but would fail at the sudden pour transition, as S005 demonstrated.

---

## L-014 — Jar lift produces slope=2900+ g/s; node cannot distinguish from pour by slope alone
**Date:** 2026-07-17

**Observed:** Jar removed from platform during Run 1 produced slope >2900 g/s.
State machine entered POUR_IN_PROGRESS correctly. Reported delta_g = negative (mass leaving).

**Why it matters:** A pour and a jar-lift are both fast negative-slope events.
The node cannot distinguish them using slope alone. delta_g sign (negative = jar lift,
positive = added liquid) is the only discriminating signal, but a fast pour also shows
negative delta when liquid exits the jar into a glass.

**Rule:** Hub must interpret delta sign in context: extreme magnitude (>2000g) most likely
jar-lift or full removal, not a pour. Node's job is only to report the event accurately.
Hub applies the domain knowledge.

---

## L-015 — Repo contamination risk when git add -A runs from wrong working directory
**Date:** 2026-07-17

**What happened (S006):** CLI ran `git add -A` from a parent directory instead of the
project root. All sibling directories under ~/ArduinoApps/ were staged and committed
into the juice_battle repo (S006 contamination commit, fixed by aa01bf7).

**Root cause:** `git add -A` stages everything reachable from the current directory.
If the shell is one level up, entire sibling projects get included.

**Mitigation:**
1. Always `cd` explicitly to the project root before any git operation in CLI prompts.
2. Check `git status` output before committing — if unexpected paths appear, abort.
3. Never use `git add -A` or `git add .` from a directory that is not the project root.
4. Prefer `git add <explicit-file-list>` for safety.

---

## L-016 — Flask-SocketIO /socket.io/ path is a protocol endpoint, not a static file server
**Date:** 2026-07-21

**What happened (S010):** Browser requested `/socket.io/socket.io.js` — the path
Flask-SocketIO mounts for Engine.IO handshakes. Serving a JS file there creates
a malformed handshake = HTTP 400. Client JS must be served from a separate static path.

**Protocol pairing rule:** flask-socketio 5.x requires Socket.IO JS client 4.x.
Download the matching client JS and serve it from a static route (e.g. `/static/`).
Never rely on CDN at a stall — download during setup, serve locally.

---

## L-017 — Python print() is block-buffered when stdout is not a TTY
**Date:** 2026-07-21

**What happened (S010):** Under systemd, `[GAME]` log lines never appeared in
`journalctl` while Werkzeug lines (stderr, line-buffered) appeared immediately.
Looked like game logic was not running; it was running but output was buffered.

**Rule:** Add `Environment=PYTHONUNBUFFERED=1` to every Python systemd service unit.
Logging visibility is a precondition for any hardware experiment. A service whose
logs cannot be seen is unfalsifiable.

---

## L-018 — Tap-pour fragmentation signature
**Date:** 2026-07-21

**What happened (S010):** Every tap press-and-release emits two distinct scale events:
a small fragment (18–35g, the press-leak) and a main body (160–195g), settling
15–56s apart. With POUR_WINDOW_S=8.0 every inter-fragment gap exceeded the window,
so ~226g was correctly-by-design discarded across the 4-pour experiment.

**Open design question for S011:** Fragment size itself may be the discriminator —
leak fragments are consistently small; a size threshold may be more robust than time
alone. Window tension: too short splits one visitor's pour, too long merges two visitors.

---

## L-019 — RAM accumulator is a cache, DB is the truth
**Date:** 2026-07-21

**What happened (S010):** game.start() zeroes glass_count and partial_g. A service
restart mid-game wipes the RAM state while pour_events history survives in SQLite.

**Rule for S011:** On startup, rebuild accumulator from
`SELECT SUM(delta_g) FROM pour_events WHERE session_id = current_session`
so a service restart is invisible to the crowd scoreboard.

---

## L-020 — Transport reconnect gap can drop events
**Date:** 2026-07-21

**Observation:** ble_scanner.py pushes NDJSON into TCP :7001. During the 5s reconnect
backoff in transport.py, any POUR_SETTLED emitted by the scanner has no listener and
is silently lost.

**Mitigation direction:** Sequence numbers already exist in HEARTBEAT payloads.
Extend replay-from-seq to POUR_SETTLED on reconnect so the hub can request missed
events rather than discarding them.

---

## S011

### POUR_ACTIVE semantics: boundary detector, not keep-alive
POUR_ACTIVE fires when the slope detector sees real flow - only genuine pours
trigger it. A slow drip never reaches slope threshold. Therefore POUR_ACTIVE
after gap > window = definitionally a new visitor's first flow event.
Treating it as a keep-alive (original mistake) caused new visitor's POUR_ACTIVE
to resurrect previous visitor's stale partial. Rule: POUR_ACTIVE always discards
stale partial unconditionally. No size test.

### Preserve rule causes the exact bug it was meant to prevent
A partial = 50g at window expiry could be either "main body landed, drip pending"
OR "person poured 80g and walked away." No observable signal distinguishes them.
Preserving it causes false glasses when next visitor pours less than 150g.
The only correct rule: delete partial at every boundary. The one-glass worst-case
from discarding a real in-progress pour is recoverable; false glasses at a stall
are not. Preserve rule deleted permanently.

### Residue must die at glass-fire, not at window expiry
Overshoot residue (e.g. 10g after 160g pour) belongs to the visitor who just
completed. Deferring discard to window-expiry allowed residue to compound across
visitors. Fix: if new_glasses > 0: partial = 0.0 immediately.

### Disturbance symmetry: negative spike clears partial AND suppresses rebound
A platform disturbance (hand slam, object placed) produces a large negative delta
followed by a symmetric positive rebound 1-3 seconds later. Sign rule kills the
negative. Rebound is positive, above noise gate, below anomaly ceiling → false
accumulation. Fix: large negative delta (below -(GLASS_VOLUME_G × POUR_MAX_G_FRAC))
clears partial AND sets bounce_until = now + BOUNCE_SETTLE_S. All events arriving
before bounce_until are suppressed regardless of sign or magnitude.

### Post-anomaly settling window required after jar removal
ANOMALY (delta > 450g) correctly refuses to score jar lift. But platform
oscillates for several seconds after jar is returned - settling artifacts
accumulate as juice. Fix: ANOMALY sets settling_until = now + ANOMALY_SETTLE_S
and zeros partial. All events before settling_until suppressed.

### Two-terminal discipline: watch logs AND dashboard simultaneously
Logs tell you what the algorithm decided. Dashboard tells you what the crowd sees.
Running both simultaneously during adversarial testing caught false glasses that
the logs alone would have required more arithmetic to detect.

### Conservation of mass - the auditable invariant
total_juice_dispensed = (glass_count × GLASS_VOLUME_G) + overflow_g
Every gram that passes the noise gate must land somewhere in the ledger.
Currently residues and abandoned partials are silently discarded - not auditable.
Overflow bucket (S012a) implements this invariant with tagged routing:
RESIDUE, ABANDONED, ANOMALY, DISTURBANCE. Enables mass-conservation spot-check
against physical jar weight at any moment.
