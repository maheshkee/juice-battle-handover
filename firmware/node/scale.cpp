#include "scale.h"
#include "ads1232.h"
#include "config.h"
#include "cal.h"
#include <Arduino.h>

// Noise clamp threshold - readings below this are treated as zero.
// Set to 2 × sigma_live. At sigma=3g, anything under 6g on empty
// platform is noise, not a real load. Prevents flicker at rest.
#define SCALE_NOISE_CLAMP_G   6.0f

// WHY module-level static: baseline_g must survive across loop() calls.
// Only scale_capture_baseline() writes it. scale_read() and scale_get_baseline_g() read it.
// Not exposed in the header - callers use the accessor.
static float baseline_g = 0.0f;

ScaleResult scale_capture_baseline(const CalResult& cal) {
    ScaleResult result;

    // 20-sample block average - same pattern as cal.cpp block_average()
    // but inline here so scale.cpp has no dependency on cal internals.
    int32_t sum = 0;
    int valid   = 0;

    for (int i = 0; i < 20; i++) {
        int32_t r = ads1232_read_raw();
        if (r != ADS1232_READ_ERROR) {
            sum += r;
            valid++;
        }
        delay(110);  // 10 SPS = 100ms per sample, 110ms = safe margin
    }

    // Require 90% valid reads - same standard as cal.cpp
    if (valid < 18) {
        result.quality   = FAILED;
        result.grams     = 0.0f;
        result.raw_grams = 0.0f;
        result.raw       = 0;
        snprintf(result.diagnosis, 64,
            "Baseline failed: only %d/20 valid ADC reads", valid);
        return result;
    }

    int32_t baseline_raw = sum / valid;
    float   baseline_abs = cal_to_grams(baseline_raw, cal);

    // WHY write module static here: this is the only place baseline_g is set.
    // All subsequent scale_read() calls subtract this value to get delta.
    baseline_g = baseline_abs;

    result.raw       = baseline_raw;
    result.raw_grams = baseline_abs;
    // value_g = 0.0 by definition.
    // Baseline IS the new zero. Delta from baseline at capture time is always zero.
    result.grams     = 0.0f;
    result.quality   = GOOD;
    snprintf(result.diagnosis, 64,
        "Baseline captured. raw=%d grams=%.1f", baseline_raw, baseline_abs);

    return result;
}

ScaleResult scale_read(const CalResult& cal, float sigma_g) {
    ScaleResult result;

    int32_t raw = ads1232_read_raw();

    if (raw == ADS1232_READ_ERROR) {
        result.quality   = FAILED;
        result.grams     = 0.0f;
        result.raw_grams = 0.0f;
        result.raw       = -1;
        snprintf(result.diagnosis, 64, "ADC read error");
        return result;
    }

    float abs_grams = cal_to_grams(raw, cal);
    float delta_g   = abs_grams - baseline_g;

    // WHY two-step clamp: abs check first, then restore sign.
    // |delta| < sigma → zero (noise, not real weight change).
    // |delta| >= sigma → keep original signed delta (remove adds positive, pour adds negative).
    float abs_delta = (delta_g < 0.0f) ? -delta_g : delta_g;
    if (abs_delta < sigma_g) {
        delta_g = 0.0f;
    }
    // else: delta_g already has correct sign, leave it.

    result.raw       = raw;
    result.raw_grams = abs_grams;
    result.grams     = delta_g;
    result.quality   = GOOD;
    snprintf(result.diagnosis, 64,
        "OK. raw=%d abs=%.1fg delta=%.1fg", raw, abs_grams, delta_g);

    return result;
}

float scale_get_baseline_g() {
    // Read-only accessor. baseline_g is private to this module.
    return baseline_g;
}

void scale_print(const ScaleResult& result) {
    if (result.quality == FAILED) {
        Serial.printf("[SCALE] FAILED: %s\n", result.diagnosis);
        return;
    }
    Serial.printf("[SCALE] %7.1fg  (raw=%d  abs=%.1fg)\n",
        result.grams,
        result.raw,
        result.raw_grams);
}
