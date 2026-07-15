// firmware/node/noise.h
// Noise floor characterisation module.
// Measures σ of raw ADS1232 samples using Welford's online algorithm.
// Must be called BEFORE calibration — σ_live sets all detection thresholds.
// Returns σ in both raw ADC counts (σ_raw) and estimated grams (σ_g).
// σ_g uses ADS_NOMINAL_COUNTS_PER_GRAM from config.h — this is a pre-calibration
// estimate only. It will be superseded by the real cal model after cal.cpp runs.
#pragma once
#include <Arduino.h>
#include "types.h"

struct NoiseResult {
    float   sigma_raw;        // σ in raw ADC counts
    float   sigma_g;          // σ in grams (nominal estimate, pre-calibration)
    Quality quality;          // QUALITY_GOOD / DEGRADED / FAILED
    char    diagnosis[64];    // human-readable explanation
};

// Measure noise floor over n_samples ADS1232 readings.
// Blocks while collecting samples (~n_samples × 100ms at 10 SPS).
// Default n_samples = NOISE_SAMPLE_COUNT_DEFAULT (100 samples = ~10 seconds).
NoiseResult noise_measure(uint16_t n_samples = NOISE_SAMPLE_COUNT_DEFAULT);
