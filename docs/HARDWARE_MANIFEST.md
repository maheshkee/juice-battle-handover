# HARDWARE MANIFEST — Juice Battle

All values must be marked: VERIFIED (tested on real hardware) or DERIVED (calculated/inferred).
Never carry values from a prior project without re-verification on this hardware.

---

## Unit inventory

| Component          | Qty | Status        | Notes                                  |
|--------------------|-----|---------------|----------------------------------------|
| Arduino UNO Q      | 1   | IN HAND       | SKU ABX00162 or ABX00173 — confirm     |
| ESP32-C3 SuperMini | 2   | IN HAND       | 3.3V GPIO, 2.4GHz WiFi only            |
| CZL601 load cell   | 2   | IN HAND       | Capacity: TBD — confirm per unit label |
| ADS1232 ADC board  | 2   | IN HAND       | TI ADS1232 — 24-bit, differential      |
| HX711 ADC board    | 2   | IN HAND       | NOT used in this project (confirmed ADS1232) |
| Display (TBD)      | 1   | TBD           | To be decided in Phase 0               |

---

## ADS1232 — Key Specs (DERIVED from datasheet)

| Parameter       | Value            | Source         |
|-----------------|------------------|----------------|
| Resolution      | 24-bit           | DERIVED        |
| Input type      | Differential     | DERIVED        |
| AVDD            | 2.7V – 5.25V     | DERIVED        |
| DVDD            | 2.7V – 5.25V     | DERIVED        |
| Planned AVDD    | 5V               | DERIVED        |
| Planned DVDD    | 3.3V             | DERIVED        |
| Data rate       | 10 SPS or 80 SPS (SPEED pin) | DERIVED |
| Interface       | SPI-like (custom, not standard SPI) | DERIVED |
| Key pins        | SCLK, DOUT, AIN1+, AIN1-, PWDN, DRDY/DOUT | DERIVED |
| DRDY behavior   | DOUT goes LOW when new data ready | DERIVED |

**Confirmed working pins on ESP32-C3: TBD — to be verified in Phase 1**

---

## CZL601 Load Cell — Key Specs (DERIVED)

| Parameter       | Value              | Source   |
|-----------------|--------------------|----------|
| Type            | Single-point       | DERIVED  |
| Excitation      | 5V or 10V          | DERIVED  |
| Output          | mV/V differential  | DERIVED  |
| Wires           | Red, Black, White, Green (or similar) | DERIVED |
| Rated capacity  | Confirm per unit — 5kg or 10kg | TBD — VERIFY |
| Overload        | Typically 120% of rated | DERIVED |

**Wire colour mapping: TBD — verify with multimeter in Phase 1**

---

## ESP32-C3 SuperMini — Key Specs (DERIVED)

| Parameter        | Value           | Source   |
|------------------|-----------------|----------|
| CPU              | RISC-V 32-bit, 160MHz | DERIVED |
| Flash            | 4MB             | DERIVED  |
| GPIO voltage     | 3.3V            | DERIVED  |
| WiFi             | 802.11b/g/n 2.4GHz only | DERIVED |
| Bluetooth        | BLE 5.0         | DERIVED  |
| USB              | USB-C (CH340 or native USB) | DERIVED |
| Supply           | 3.3V via 3V3 pin or 5V via 5V pin | DERIVED |

---

## Arduino UNO Q — Key Specs (VERIFIED from prior projects)

| Parameter          | Value                      | Source   |
|--------------------|----------------------------|----------|
| MPU                | QRB2210, 4x Cortex-A53     | VERIFIED |
| MCU                | STM32U585, Cortex-M33      | VERIFIED |
| OS (MPU)           | Debian Linux               | VERIFIED |
| RTOS (MCU)         | Zephyr with Arduino Core   | VERIFIED |
| MCU GPIO voltage   | 3.3V (A0, A1 NOT 5V tolerant) | VERIFIED |
| JCTL voltage       | 1.8V ONLY                  | VERIFIED |
| RAM (MPU)          | 2GB or 4GB                 | VERIFIED |
| Storage            | 16GB or 32GB eMMC          | VERIFIED |
| HX711 working pins | D7 (DT), D6 (SCK)         | VERIFIED from gas monitor |

---

## Pinout assignments (TBD — to be filled in Phase 1)

### ESP32-C3 → ADS1232

| ADS1232 Pin | ESP32-C3 GPIO | Status |
|-------------|---------------|--------|
| SCLK        | TBD           | TBD    |
| DOUT        | TBD           | TBD    |
| PWDN        | TBD           | TBD    |
| SPEED       | GND (10 SPS)  | DERIVED — verify |
| AVDD        | 5V            | TBD    |
| DVDD        | 3.3V          | TBD    |
| GND         | GND           | TBD    |

### UNO Q MCU → LEDs / status indicators

| Function          | MCU Pin | Status |
|-------------------|---------|--------|
| Game active LED   | TBD     | TBD    |
| Node A connected  | TBD     | TBD    |
| Node B connected  | TBD     | TBD    |

---

## Calibration factors (TBD — filled in Phase 1)

| Node   | Raw zero (tare) | Calibration factor | Reference weight | Status |
|--------|-----------------|---------------------|------------------|--------|
| Node A | TBD             | TBD                 | TBD              | TBD    |
| Node B | TBD             | TBD                 | TBD              | TBD    |
