#pragma once
#include <Arduino.h>
#include "types.h"

// CalResult - output of the full calibration sequence.
// Stores the four raw ADC reference points that define the
// piecewise linear conversion model, plus quality metadata.
// All four raw values are stored in ESP32 NVS and survive power-off.
struct CalResult {
    int32_t raw_zero;       // ADC count at tare (empty platform)
    int32_t raw_500;        // ADC count with 500g reference weight
    int32_t raw_1000;       // ADC count with 1000g reference weight
    int32_t raw_5000;       // ADC count with 5000g reference weight
    float   confidence;     // 0.0-1.0: agreement between three independent cal_factors
    float   residual_max;   // max spread between the three cal_factors (raw)
    float   sigma_tare_g;   // noise floor measured during tare phase (grams)
    Quality quality;        // GOOD / DEGRADED / FAILED
    char    diagnosis[64];  // human-readable reason string
};

// Run the full calibration sequence.
// Blocks until complete or failed.
// Operator is guided via Serial prints at 115200 baud.
// On success: saves CalResult to NVS, returns GOOD or DEGRADED.
// On failure: returns FAILED with diagnosis string, does NOT write NVS.
CalResult cal_run();

// Convert a raw ADC reading to grams using the piecewise linear model.
// Requires a valid CalResult (quality != FAILED).
// Returns 0.0 for readings below raw_zero.
// Extrapolates linearly above raw_5000 (acceptable - load cell is 40kg rated).
float cal_to_grams(int32_t raw, const CalResult& cal);

// Load a previously stored CalResult from ESP32 NVS.
// Returns true if valid calibration found, false if NVS empty or flagged invalid.
bool cal_load_from_nvs(CalResult& out);

// Save CalResult to ESP32 NVS.
// Only call this after a successful cal_run() - cal_run() calls this internally.
// Exposed here so hub can trigger recalibration and explicit NVS write if needed.
void cal_save_to_nvs(const CalResult& cal);

// Run validation sweep using an already-built CalResult.
// Operator places reference weights in sequence.
// Prints expected vs measured vs error% for each point.
// Does not modify CalResult or NVS.
void cal_validate(const CalResult& cal);
