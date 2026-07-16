#pragma once
#include "types.h"
#include "cal.h"

struct ScaleResult {
    float   grams;        // tared weight in grams (relative to platform empty)
    float   raw_grams;    // absolute grams before tare subtraction
    int32_t raw;          // raw ADC value this reading
    Quality quality;      // GOOD / DEGRADED / FAILED
    char    diagnosis[64];
};

// Capture tare baseline at boot.
// Takes 20-sample block average (~2.5 seconds).
// Returns ScaleResult with grams=0 on success (tare defines zero).
// On failure: quality=FAILED with diagnosis. Do not proceed.
ScaleResult scale_tare(const CalResult& cal);

// Read current tared weight.
// Single ADC read → cal_to_grams → subtract tare_g → clamp noise.
// Non-blocking. Call from loop() at 2-10 Hz.
// tare_g: the raw_grams value from a prior scale_tare() call.
ScaleResult scale_read(const CalResult& cal, float tare_g);

// Print formatted reading to Serial. Debug/test only.
void scale_print(const ScaleResult& result);
