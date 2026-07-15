// firmware/node/ads1232.h
// ADS1232 hardware abstraction layer.
// Single responsibility: bit-bang read of one 24-bit signed ADC sample.
// Does NOT know about noise, calibration, or weight units.
// Pin assignments come from config.h.
#pragma once
#include <Arduino.h>
#include <stdint.h>

// Sentinel value returned on read error (DRDY timeout or hardware fault)
#define ADS1232_READ_ERROR   INT32_MIN

// Initialise GPIO pins and power up the ADS1232.
// Must be called once in setup() before any reads.
void ads1232_init(void);

// Power up the ADS1232 (PDWN HIGH). Blocks for ADS_WARMUP_MS.
void ads1232_power_up(void);

// Power down the ADS1232 (PDWN LOW). Use between measurements to save power.
void ads1232_power_down(void);

// Returns true if the ADS1232 DOUT pin is LOW (conversion ready).
bool ads1232_is_ready(void);

// Read one 24-bit signed sample via bit-bang.
// Blocks until DRDY goes low (up to ADS_READY_TIMEOUT_MS).
// Returns ADS1232_READ_ERROR if DRDY does not assert in time.
// Disables interrupts during the 24-bit read to prevent bit-stream corruption.
int32_t ads1232_read_raw(void);
