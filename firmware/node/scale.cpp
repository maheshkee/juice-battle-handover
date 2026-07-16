#include "scale.h"
#include "ads1232.h"
#include "config.h"
#include "cal.h"
#include <Arduino.h>

// Noise clamp threshold - readings below this are treated as zero.
// Set to 2 × sigma_live. At sigma=3g, anything under 6g on empty
// platform is noise, not a real load. Prevents flicker at rest.
#define SCALE_NOISE_CLAMP_G   6.0f

ScaleResult scale_tare(const CalResult& cal) {
    ScaleResult result;

    // 20-sample block average - same pattern as cal.cpp block_average()
    // but inline here so scale.cpp has no dependency on cal internals.
    int32_t sum = 0;
    int valid   = 0;

    for (int i = 0; i < 20; i++) {
        int32_t r = ads1232_read_raw();
        if (r != -1) {
            sum += r;
            valid++;
        }
        delay(110);  // 10 SPS = 100ms per sample, 110ms = safe margin
    }

    // Require 90% valid reads - same standard as cal.cpp
    if (valid < 18) {
        result.quality    = FAILED;
        result.grams      = 0.0f;
        result.raw_grams  = 0.0f;
        result.raw = 0;
        snprintf(result.diagnosis, 64,
            "Tare failed: only %d/20 valid ADC reads", valid);
        return result;
    }

    int32_t tare_raw   = sum / valid;
    float   tare_grams = cal_to_grams(tare_raw, cal);

    result.raw = tare_raw;
    result.raw_grams  = tare_grams;
    result.grams      = 0.0f;  // tare defines zero by definition
    result.quality    = GOOD;
    snprintf(result.diagnosis, 64,
        "Tare OK. raw=%d grams=%.1f", tare_raw, tare_grams);

    return result;
}

ScaleResult scale_read(const CalResult& cal, float tare_g) {
    ScaleResult result;

    int32_t raw = ads1232_read_raw();

    if (raw == -1) {
        result.quality    = FAILED;
        result.grams      = 0.0f;
        result.raw_grams  = 0.0f;
        result.raw = -1;
        snprintf(result.diagnosis, 64, "ADC read error");
        return result;
    }

    float abs_grams   = cal_to_grams(raw, cal);
    float tared_grams = abs_grams - tare_g;

    // Clamp noise floor - small negative or tiny positive = platform empty
    if (fabsf(tared_grams) < SCALE_NOISE_CLAMP_G) {
        tared_grams = 0.0f;
    }

    result.raw = raw;
    result.raw_grams  = abs_grams;
    result.grams      = tared_grams;
    result.quality    = GOOD;
    snprintf(result.diagnosis, 64,
        "OK. raw=%d abs=%.1fg tared=%.1fg", raw, abs_grams, tared_grams);

    return result;
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
