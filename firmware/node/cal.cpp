// firmware/node/cal.cpp
// Calibration module — Juice Battle node.
// 3-point piecewise linear calibration using 500g/1000g/5000g reference weights.
// Stores CalResult to ESP32 NVS via Preferences.h.
#include <Arduino.h>
#include <Preferences.h>
#include <math.h>
#include "cal.h"
#include "ads1232.h"
#include "config.h"
#include "types.h"

// Validation sweep - expected weights in grams, in placement order
// Operator places: 200g alone, 200+500=700g, 500+1000=1500g, 10000g alone
static const float CAL_VAL_WEIGHTS_G[CAL_VAL_COUNT] = {
    200.0f,
    700.0f,
    1500.0f,
    10000.0f
};

// Labels matching the array above - for Serial output
static const char* CAL_VAL_LABELS[CAL_VAL_COUNT] = {
    "200g stone alone",
    "200g + 500g stones",
    "500g + 1000g stones",
    "10kg stone alone"
};

// ---------------------------------------------------------------------------
// Private helpers
// ---------------------------------------------------------------------------

static int32_t block_average(int n) {
    int64_t sum = 0;
    int valid = 0;
    for (int i = 0; i < n; i++) {
        int32_t raw = ads1232_read_raw();
        if (raw != ADS1232_READ_ERROR) {
            sum += raw;
            valid++;
        }
        delay(110);
    }
    if (valid < (int)(n * 0.9f)) return -1;
    return (int32_t)(sum / valid);
}

static bool wait_for_stable(uint32_t timeout_ms) {
    int32_t window[CAL_STABILITY_WINDOW];
    memset(window, 0, sizeof(window));
    int head = 0, filled = 0, stable_count = 0;
    uint32_t start = millis(), last_dot = millis();
    float threshold = STABILITY_SPREAD_THRESHOLD_G * NOMINAL_COUNTS_PER_GRAM;

    while (millis() - start < timeout_ms) {
        int32_t raw = ads1232_read_raw();
        if (raw == ADS1232_READ_ERROR) { delay(110); continue; }

        window[head] = raw;
        head = (head + 1) % CAL_STABILITY_WINDOW;
        if (filled < CAL_STABILITY_WINDOW) filled++;

        if (millis() - last_dot >= 500) { Serial.print("."); last_dot = millis(); }

        if (filled == CAL_STABILITY_WINDOW) {
            int32_t wmin = window[0], wmax = window[0];
            for (int i = 1; i < CAL_STABILITY_WINDOW; i++) {
                if (window[i] < wmin) wmin = window[i];
                if (window[i] > wmax) wmax = window[i];
            }
            if ((float)(wmax - wmin) < threshold) {
                if (++stable_count >= 3) { Serial.println(); return true; }
            } else {
                stable_count = 0;
            }
        }
        delay(110);
    }
    Serial.println();
    return false;
}

// Countdown timer - prints N...N-1...N-2... then returns.
// Gives platform time to stop vibrating after weight placement
// before the stability algorithm starts evaluating.
static void settling_countdown(int seconds) {
    for (int i = seconds; i > 0; i--) {
        Serial.printf("%d...", i);
        delay(1000);
    }
    Serial.println(" go.");
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

CalResult cal_run() {
    CalResult result;
    memset(&result, 0, sizeof(result));

    // -------------------------------------------------------------------------
    // PHASE 1 - TARE
    // -------------------------------------------------------------------------
    Serial.println("CAL PHASE 1: TARE - ensure platform is empty, press Enter");
    while (!Serial.available()) delay(10);
    Serial.read();
    settling_countdown(CAL_SETTLING_COUNTDOWN_S);
    if (!wait_for_stable(10000)) {
        result.quality = FAILED;
        snprintf(result.diagnosis, 64, "TARE: platform not stable within 10s");
        return result;
    }

    int32_t raw_zero = block_average(CAL_BLOCK_SAMPLES);
    if (raw_zero == -1) {
        result.quality = FAILED;
        snprintf(result.diagnosis, 64, "TARE: ADC read errors during block average");
        return result;
    }

    // Tare guard: verify nothing was placed on platform during block average.
    // Checks delta from raw_zero — raw/NOMINAL would always fail due to zero-balance offset.
    {
        int32_t guard_raw = ads1232_read_raw();
        if (guard_raw != ADS1232_READ_ERROR) {
            float delta_g = fabsf((float)(guard_raw - raw_zero) / NOMINAL_COUNTS_PER_GRAM);
            if (delta_g > CAL_TARE_MAX_G) {
                result.quality = FAILED;
                snprintf(result.diagnosis, 64, "TARE: platform not empty (%.0fg detected)", delta_g);
                return result;
            }
        }
    }

    // Welford sigma_tare_g over 50 additional samples
    float wf_mean = 0.0f, wf_M2 = 0.0f;
    int wf_n = 0;
    for (int i = 0; i < 50; i++) {
        int32_t r = ads1232_read_raw();
        if (r == ADS1232_READ_ERROR) { delay(110); continue; }
        wf_n++;
        float delta = (float)r - wf_mean;
        wf_mean += delta / (float)wf_n;
        wf_M2   += delta * ((float)r - wf_mean);
        delay(110);
    }
    float sigma_tare_g = 0.0f;
    if (wf_n >= 2) sigma_tare_g = sqrtf(wf_M2 / (float)(wf_n - 1)) / NOMINAL_COUNTS_PER_GRAM;

    Serial.printf("TARE OK. raw_zero=%d  sigma_tare=%.2fg\n", raw_zero, sigma_tare_g);

    // -------------------------------------------------------------------------
    // PHASE 2 - THREE REFERENCE WEIGHTS
    // -------------------------------------------------------------------------
    const float ref_g[3]  = { CAL_REF_1_G, CAL_REF_2_G, CAL_REF_3_G };
    int32_t raw_refs[3]   = { 0, 0, 0 };

    for (int w = 0; w < 3; w++) {
        Serial.printf("CAL PHASE 2: Place %dg weight on platform, press Enter\n", (int)ref_g[w]);
        while (!Serial.available()) delay(10);
        Serial.read();
        settling_countdown(CAL_SETTLING_COUNTDOWN_S);
        if (!wait_for_stable(15000)) {
            result.quality = FAILED;
            snprintf(result.diagnosis, 64, "WEIGHT %dg: not stable within 15s", (int)ref_g[w]);
            return result;
        }

        int32_t raw_ref = block_average(CAL_BLOCK_SAMPLES);
        if (raw_ref == -1) {
            result.quality = FAILED;
            snprintf(result.diagnosis, 64, "WEIGHT %dg: ADC read errors", (int)ref_g[w]);
            return result;
        }
        if (raw_ref <= raw_zero) {
            result.quality = FAILED;
            snprintf(result.diagnosis, 64, "WEIGHT %dg: raw reading not above tare - check wiring", (int)ref_g[w]);
            return result;
        }

        Serial.printf("WEIGHT %dg OK. raw=%d  delta_counts=%d\n",
            (int)ref_g[w], raw_ref, raw_ref - raw_zero);
        raw_refs[w] = raw_ref;

        Serial.println("Remove weight, press Enter for next");
        while (!Serial.available()) delay(10);
        Serial.read();
        settling_countdown(CAL_REMOVAL_COUNTDOWN_S);
        wait_for_stable(10000);
    }

    int32_t raw_500  = raw_refs[0];
    int32_t raw_1000 = raw_refs[1];
    int32_t raw_5000 = raw_refs[2];

    // -------------------------------------------------------------------------
    // PHASE 3 - CONFIDENCE CHECK
    // -------------------------------------------------------------------------
    float cf_500  = CAL_REF_1_G / (float)(raw_500  - raw_zero);
    float cf_1000 = CAL_REF_2_G / (float)(raw_1000 - raw_zero);
    float cf_5000 = CAL_REF_3_G / (float)(raw_5000 - raw_zero);
    float cf_mean = (cf_500 + cf_1000 + cf_5000) / 3.0f;

    float cf_max = cf_500 > cf_1000 ? cf_500 : cf_1000;
    if (cf_5000 > cf_max) cf_max = cf_5000;
    float cf_min = cf_500 < cf_1000 ? cf_500 : cf_1000;
    if (cf_5000 < cf_min) cf_min = cf_5000;

    float residual_max = cf_max - cf_min;
    float confidence   = 1.0f - (residual_max / cf_mean) / CAL_MAX_ACCEPTABLE_SPREAD;
    if (confidence < 0.0f) confidence = 0.0f;
    if (confidence > 1.0f) confidence = 1.0f;

    Serial.printf("cf_500=%.6f  cf_1000=%.6f  cf_5000=%.6f\n", cf_500, cf_1000, cf_5000);
    Serial.printf("residual_max=%.6f  confidence=%.3f\n", residual_max, confidence);

    result.raw_zero     = raw_zero;
    result.raw_500      = raw_500;
    result.raw_1000     = raw_1000;
    result.raw_5000     = raw_5000;
    result.confidence   = confidence;
    result.residual_max = residual_max;
    result.sigma_tare_g = sigma_tare_g;

    if (confidence < CAL_CONFIDENCE_MIN) {
        result.quality = DEGRADED;
        snprintf(result.diagnosis, 64, "Low confidence %.2f - nonlinearity high", confidence);
    } else {
        result.quality = GOOD;
        snprintf(result.diagnosis, 64, "Cal OK. confidence=%.2f sigma_tare=%.2fg", confidence, sigma_tare_g);
    }

    // -------------------------------------------------------------------------
    // PHASE 4 - POUR VALIDATION - DEFERRED
    // Requires: actual glass jar on platform to simulate real operating load.
    // Real pours happen in segment 2-3 (1000g-5000g range on the curve).
    // A test pour on empty platform only validates segment 1 - wrong zone.
    // Implementation: place 5000g stone as base load, add 500g stone as delta,
    // verify |measured_delta - 500g| / 500g <= 0.05.
    // Add when jar is physically available.

    // -------------------------------------------------------------------------
    // PHASE 5 - NVS STORE
    // -------------------------------------------------------------------------
    if (result.quality == GOOD || result.quality == DEGRADED) {
        cal_save_to_nvs(result);
        Serial.println("CAL COMPLETE - saved to NVS");
        Serial.printf("Quality: %s\n", result.quality == GOOD ? "GOOD" : "DEGRADED");
        Serial.println("Power cycle the board. Cal must survive - verify with cal_load_from_nvs()");
    }

    return result;
}

// cal_validate() - runs a validation sweep after calibration.
// Operator places each weight in sequence.
// Board measures delta using the piecewise model and reports
// expected vs measured vs error% for each point.
// This tests model accuracy at intermediate points - not the
// reference points used to build the model.
// Does not modify CalResult or NVS.
void cal_validate(const CalResult& cal) {
    Serial.println("\n=== CAL VALIDATION SWEEP ===");
    Serial.println("Tests model accuracy at intermediate weights.");
    Serial.println("Watch the error% column - target < 5% per point.\n");

    // Capture fresh baseline before validation sweep starts
    Serial.println("Ensure platform is EMPTY, press Enter...");
    while (!Serial.available()) delay(10);
    Serial.read();
    settling_countdown(CAL_SETTLING_COUNTDOWN_S);

    if (!wait_for_stable(10000)) {
        Serial.println("[VALIDATE] Platform not stable - aborting sweep.");
        return;
    }

    int32_t baseline_raw = block_average(CAL_BLOCK_SAMPLES);
    if (baseline_raw == -1) {
        Serial.println("[VALIDATE] ADC read error during baseline - aborting.");
        return;
    }
    float baseline_g = cal_to_grams(baseline_raw, cal);
    Serial.printf("[VALIDATE] Baseline: raw=%d  grams=%.1f\n\n", baseline_raw, baseline_g);

    // Track overall pass/fail
    int passed = 0;
    int failed = 0;

    for (int i = 0; i < CAL_VAL_COUNT; i++) {
        float expected_g = CAL_VAL_WEIGHTS_G[i];

        Serial.printf("--- Point %d of %d ---\n", i + 1, CAL_VAL_COUNT);
        Serial.printf("Place %s on platform, press Enter...\n", CAL_VAL_LABELS[i]);

        while (!Serial.available()) delay(10);
        Serial.read();

        // Countdown - let vibration from placement die down
        settling_countdown(CAL_SETTLING_COUNTDOWN_S);

        if (!wait_for_stable(15000)) {
            Serial.printf("[VALIDATE] Point %d: not stable - skipping.\n\n", i + 1);
            failed++;
            continue;
        }

        int32_t loaded_raw = block_average(CAL_BLOCK_SAMPLES);
        if (loaded_raw == -1) {
            Serial.printf("[VALIDATE] Point %d: ADC error - skipping.\n\n", i + 1);
            failed++;
            continue;
        }

        // Convert both readings and compute delta
        // Using grams delta - not raw delta - so piecewise model applies correctly
        float loaded_g   = cal_to_grams(loaded_raw, cal);
        float measured_g = loaded_g - baseline_g;
        float error_pct  = fabsf(measured_g - expected_g) / expected_g * 100.0f;
        bool  point_pass = error_pct <= (CAL_VAL_TOLERANCE * 100.0f);

        Serial.printf("expected = %.1fg\n", expected_g);
        Serial.printf("measured = %.1fg\n", measured_g);
        Serial.printf("error    = %.2f%%  %s\n\n",
            error_pct,
            point_pass ? "PASS" : "FAIL");

        if (point_pass) passed++; else failed++;

        // Remove weight before next point
        Serial.println("Remove weight, press Enter...");
        while (!Serial.available()) delay(10);
        Serial.read();
        settling_countdown(CAL_REMOVAL_COUNTDOWN_S);
        wait_for_stable(10000);

        // Refresh baseline after each removal - platform may drift slightly
        baseline_raw = block_average(CAL_BLOCK_SAMPLES);
        if (baseline_raw != -1) {
            baseline_g = cal_to_grams(baseline_raw, cal);
        }
        Serial.println();
    }

    // Summary
    Serial.println("=== VALIDATION SUMMARY ===");
    Serial.printf("Passed: %d / %d\n", passed, CAL_VAL_COUNT);
    Serial.printf("Failed: %d / %d\n", failed, CAL_VAL_COUNT);
    Serial.println(passed == CAL_VAL_COUNT ? "Result: ALL PASS" : "Result: REVIEW FAILURES");
    Serial.println("===========================\n");
}

float cal_to_grams(int32_t raw, const CalResult& cal) {
    float u  = (float)(raw - cal.raw_zero);
    float u1 = (float)(cal.raw_500  - cal.raw_zero);
    float u2 = (float)(cal.raw_1000 - cal.raw_zero);
    float u3 = (float)(cal.raw_5000 - cal.raw_zero);

    if (u <= 0.0f) return 0.0f;
    if (u <= u1)   return (u / u1) * 500.0f;
    if (u <= u2)   return 500.0f  + (u - u1) / (u2 - u1) * 500.0f;
    else           return 1000.0f + (u - u2) / (u3 - u2) * 4000.0f;
}

bool cal_load_from_nvs(CalResult& out) {
    Preferences prefs;
    prefs.begin(NVS_NAMESPACE, true);
    bool valid = prefs.getBool(NVS_KEY_VALID, false);
    if (!valid) { prefs.end(); return false; }
    out.raw_zero     = prefs.getInt(NVS_KEY_RAW_ZERO, 0);
    out.raw_500      = prefs.getInt(NVS_KEY_RAW_500,  0);
    out.raw_1000     = prefs.getInt(NVS_KEY_RAW_1000, 0);
    out.raw_5000     = prefs.getInt(NVS_KEY_RAW_5000, 0);
    out.confidence   = prefs.getFloat(NVS_KEY_CONFIDENCE, 0.0f);
    out.sigma_tare_g = prefs.getFloat(NVS_KEY_SIGMA_TARE, 0.0f);
    out.quality      = GOOD;
    snprintf(out.diagnosis, 64, "Loaded from NVS. confidence=%.2f", out.confidence);
    prefs.end();
    return true;
}

void cal_save_to_nvs(const CalResult& cal) {
    Preferences prefs;
    prefs.begin(NVS_NAMESPACE, false);
    prefs.putInt(NVS_KEY_RAW_ZERO, cal.raw_zero);
    prefs.putInt(NVS_KEY_RAW_500,  cal.raw_500);
    prefs.putInt(NVS_KEY_RAW_1000, cal.raw_1000);
    prefs.putInt(NVS_KEY_RAW_5000, cal.raw_5000);
    prefs.putFloat(NVS_KEY_CONFIDENCE, cal.confidence);
    prefs.putFloat(NVS_KEY_SIGMA_TARE, cal.sigma_tare_g);
    prefs.putBool(NVS_KEY_VALID, true);
    prefs.end();
}
