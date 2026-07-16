// firmware/node/noise.cpp
// Noise floor measurement using Welford's online algorithm.
//
// WHY Welford: single-pass, O(1) memory, numerically stable.
// The naive (sum all samples, subtract mean) approach fails on embedded:
//   - Requires heap allocation for the sample array
//   - Suffers catastrophic cancellation (mean ~2,000,000 counts, tiny variance)
// Welford avoids both by tracking deviation from a RUNNING mean.
//
// WHY σ matters: it sets the slope detection threshold for pour events.
// Without σ_live measured in the real environment (with motor/music/people),
// every threshold in the state machine is a guess.
#include "noise.h"
#include "ads1232.h"
#include "config.h"
#include <math.h>

NoiseResult noise_measure(uint16_t n_samples) {
    NoiseResult result;
    result.sigma_raw = 0.0f;
    result.sigma_g   = 0.0f;
    result.quality   = FAILED;
    snprintf(result.diagnosis, sizeof(result.diagnosis), "not run");

    // Guard: need at least 2 samples to compute variance
    if (n_samples < NOISE_SAMPLE_COUNT_MIN) {
        snprintf(result.diagnosis, sizeof(result.diagnosis),
                 "n_samples %d < minimum %d", n_samples, NOISE_SAMPLE_COUNT_MIN);
        return result;
    }

    // ── Welford's online algorithm for running mean and variance ─────────────
    // No array. No heap. No catastrophic cancellation.
    uint32_t n_collected = 0;
    uint32_t n_errors    = 0;
    double   mean        = 0.0;  // double precision for accumulator stability
    double   M2          = 0.0;  // sum of squared deviations from running mean

    for (uint16_t i = 0; i < n_samples; i++) {
        int32_t raw = ads1232_read_raw();

        if (raw == ADS1232_READ_ERROR) {
            n_errors++;
            // Abort early if error rate is too high — hardware problem
            if ((float)n_errors / n_samples > NOISE_MAX_ERROR_RATE) {
                snprintf(result.diagnosis, sizeof(result.diagnosis),
                         "ADS1232 not responding: %lu/%u reads failed",
                         n_errors, n_samples);
                return result;
            }
            continue;  // skip failed sample, keep collecting
        }

        // Welford update step
        n_collected++;
        double x      = (double)raw;
        double delta  = x - mean;
        mean         += delta / (double)n_collected;
        double delta2 = x - mean;   // NOTE: mean has already been updated above
        M2           += delta * delta2;
    }

    // Need at least 2 valid samples to compute sample variance
    if (n_collected < 2) {
        snprintf(result.diagnosis, sizeof(result.diagnosis),
                 "only %lu valid samples collected (need >= 2)", n_collected);
        return result;
    }

    // Sample variance = M2 / (n-1), using (n-1) for unbiased estimate
    double variance  = M2 / (double)(n_collected - 1);
    float  sigma_raw = (float)sqrtf((float)variance);

    // Convert to grams using nominal cal factor (pre-calibration estimate)
    // This is an approximation — will be superseded after cal.cpp runs
    float sigma_g = sigma_raw / ADS_NOMINAL_COUNTS_PER_GRAM;

    result.sigma_raw = sigma_raw;
    result.sigma_g   = sigma_g;

    // ── Quality classification ───────────────────────────────────────────────
    // Thresholds from config.h, derived from pour detection SNR requirements.
    // See docs/LEARNINGS_AND_INSIGHTS.md for derivation.
    if (sigma_g < NOISE_SIGMA_G_GOOD) {
        result.quality = GOOD;
        snprintf(result.diagnosis, sizeof(result.diagnosis),
                 "good: sigma_raw=%.1f sigma_g=%.2fg n=%lu/%u",
                 sigma_raw, sigma_g, n_collected, n_samples);

    } else if (sigma_g < NOISE_SIGMA_G_DEGRADED) {
        result.quality = DEGRADED;
        snprintf(result.diagnosis, sizeof(result.diagnosis),
                 "noisy env: sigma_g=%.2fg (threshold=%.0fg) n=%lu"
                 " - increase N or improve mounting",
                 sigma_g, NOISE_SIGMA_G_GOOD, n_collected);

    } else {
        result.quality = FAILED;
        snprintf(result.diagnosis, sizeof(result.diagnosis),
                 "too noisy: sigma_g=%.2fg (max=%.0fg) n=%lu"
                 " - check load cell mounting and wiring",
                 sigma_g, NOISE_SIGMA_G_DEGRADED, n_collected);
    }

    return result;
}
