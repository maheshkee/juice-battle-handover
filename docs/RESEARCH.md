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
