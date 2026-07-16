# RESEARCH — Juice Battle
# Hardware discoveries, datasheet findings, confirmed behaviour.
# Mark every entry: VERIFIED (real hardware) or DERIVED (calculated/inferred).

## ADS1232

R-001 [DERIVED] ADS1232 uses a serial interface where DRDY and DOUT share the same pin.
  Data is ready when DOUT goes LOW. Begin clocking on the falling edge.
  Source: ADS1232 datasheet, section 8.3.

R-002 [DERIVED] ADS1232 SPEED pin: GND = 10 SPS, VDD = 80 SPS.
  For juice dispensing at a stall, 10 SPS is sufficient and reduces noise.
  Source: ADS1232 datasheet, Table 1.

R-003 [DERIVED] ADS1232 has internal PGA (programmable gain): 1, 2, 64, 128.
  For load cells, gain 128 is standard. Controlled by number of extra SCLK pulses after data read.
  Source: ADS1232 datasheet, section 8.3.1.

## CZL601 Load Cell

R-004 [DERIVED] CZL601 is a single-point bending beam load cell with 4 wires.
  Typical wiring: Red = E+, Black = E-, White = S+, Green = S- (verify per unit).
  Source: CZL601 product specification.

## ESP32-C3 bit-bang timing

R-005 [DERIVED] ESP32-C3 runs at 160MHz. At this speed, GPIO transitions can outrun the ADS1232's
  minimum pulse width requirement. Must add delayMicroseconds(1) after every GPIO edge.
  This is the same lesson learned with HX711 on STM32U585 at 160MHz.
  Source: Learned from gas monitor project (HX711 on UNO Q MCU).

---

## 2026-07-16 - ADS1232 + ESP32-C3 SuperMini confirmed working

### Pins confirmed
```
ADS_PIN_SCLK = GPIO4
ADS_PIN_DOUT = GPIO5  (also DRDY)
ADS_PIN_PDWN = GPIO6
ADS_PIN_A0   = GPIO7  (LOW = channel 1 = our load cell)
```

### Protocol confirmed working [VERIFIED]
- DRDY: DOUT goes LOW when conversion ready. Stays LOW until 24 clocks received.
- Read 24 bits: SCLK HIGH (2µs) → sample DOUT → SCLK LOW (2µs) × 24
- Settling pulse: one extra SCLK HIGH/LOW after 24th bit — MANDATORY
- noInterrupts() / interrupts() wrapping the 24-bit read — MANDATORY
- Warmup: PDWN LOW (10ms) → HIGH → delay(100ms) before first read
- Operating mode: 10 SPS (SPEED pin = GND), gain = 128 (hardware on WCMCU module)

### Raw output confirmed [VERIFIED]
- Unloaded zero balance: ~ -93,500 counts (expected — CZL601 has ±1% FS zero offset)
- No saturation values (0x7FFFFF or 0x800000) — wiring correct
- Nominal counts/gram: 54 (derived: 2mV/V × 5V / 40000g / 4.656nV per count)

### Noise floor confirmed [VERIFIED]
- σ_raw = 336.18 counts (100-sample Welford, office fan on, empty platform)
- σ_g   = 6.23g          QUALITY_GOOD (threshold: GOOD < 10g)

### Arduino IDE setup for ESP32-C3 SuperMini
- Board: ESP32C3 Dev Module (via Espressif esp32 package)
- Upload speed: 921600
- Baud monitor: 115200
- Sketch folder name MUST match .ino filename — enforced by Arduino IDE.
- Current: juicebattle/ folder → juicebattle.ino

### Bugs confirmed and fixed [VERIFIED]
- delay(20) in diagnostic loop: causes 120ms/iteration vs 100ms ADC cycle → phase
  drift → catches DOUT mid-transition → reads all-1s (-1 value) every ~5th read.
  Fix: remove delay() from polling loops. Let ads1232_read_raw() pace itself via DRDY.
- Missing settling pulse: -1 enters Welford as valid → σ = 800g. Fix: add 25th clock.

---

## 2026-07-16 - S003 hardware findings

### CZL601 + ADS1232 calibration confirmed on hardware

Signal polarity:
- Green/white CZL601 excitation wires were physically swapped at ADS1232 INNA+/INNA-
- Effect: raw counts decrease when weight added (should increase)
- Software fix: ads1232.cpp returns -raw_value
- TODO: swap wires physically and remove negation
- Noise measurement is unaffected by polarity (variance is symmetric)

Confirmed cal constants (Run 1, best of 3 runs):
- raw_zero  = 94690  (unloaded, polarity-corrected)
- raw_500   = 148353 (delta = 53663 counts for 500g)
- raw_1000  = 201742 (delta = 107052 counts for 1000g)
- raw_5000  = 630410 (delta = 535720 counts for 5000g)
- Nominal sensitivity: ~54 counts/gram (segment average)
- confidence = 0.968 (GOOD with CAL_MAX_ACCEPTABLE_SPREAD=0.08)

Confirmed nonlinearity:
- cf_500  = 0.009317 g/count
- cf_1000 = 0.009341 g/count
- cf_5000 = 0.009333 g/count
- Spread: ~1.2% of mean - consistent across 3 independent runs

Validation accuracy (4-point sweep):
- 200g:   worst case 1.64% error (low-end nonlinearity, expected)
- 700g:   worst case 0.31% error
- 1500g:  worst case 0.18% error
- 10000g: worst case 0.05% error

Noise floor (S003, office, ceiling fan on):
- sigma_g range: 2.40g - 4.82g across 5 boot cycles
- All readings GOOD (< 10g threshold)

NVS confirmed persistent across power cycle:
- Preferences.h on ESP32 Arduino core works correctly
- Keys: jb_cal namespace, raw_zero/raw_500/raw_1000/raw_5000/confidence/sigma_tare/valid

Change Log: 2026-07-16 | S003 | cal + scale verified | CZL601 polarity bug found
