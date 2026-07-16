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
