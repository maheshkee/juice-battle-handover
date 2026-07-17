#pragma once
#include "types.h"
#include "cal.h"

struct ScaleResult {
    float   grams;        // delta from baseline in grams (positive = weight added)
    float   raw_grams;    // absolute grams before tare subtraction
    int32_t raw;          // raw ADC value this reading
    Quality quality;      // GOOD / DEGRADED / FAILED
    char    diagnosis[64];
};

// WHY "capture_baseline" not "tare":
// Tare requires empty platform - operator must remove jar on every reboot.
// capture_baseline accepts whatever is on platform as the new zero.
// Empty at install = fine. Full 10L jar after power cut = fine.
// No jar removal ever needed in production.
ScaleResult scale_capture_baseline(const CalResult& cal);

// Returns the internally stored baseline_g - read-only accessor.
// Lets juicebattle.ino print baseline without exposing internal state.
float scale_get_baseline_g();

// Read current delta from baseline in grams.
// Single ADC read → cal_to_grams → subtract baseline_g → clamp noise floor.
// Non-blocking. Call from loop() at 10 Hz.
// sigma_g: live noise floor from noise_measure() - used as clamp threshold.
ScaleResult scale_read(const CalResult& cal, float sigma_g);

// Print formatted reading to Serial. Debug/test only.
void scale_print(const ScaleResult& result);
