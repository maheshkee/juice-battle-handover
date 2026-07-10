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
