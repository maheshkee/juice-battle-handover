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
