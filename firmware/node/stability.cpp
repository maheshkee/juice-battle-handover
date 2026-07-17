#include "stability.h"
#include "config.h"
#include <Arduino.h>

static StabilityState s_state           = STAB_WAITING;
static float          s_ema_g           = 0.0f;
static float          s_prev_ema_g      = 0.0f;
static float          s_sigma_g         = 0.0f;
static float          s_baseline_g      = 0.0f;
static float          s_slope_threshold = 15.0f;
static int            s_persistence     = 0;
static int            s_settling_count  = 0;
static bool           s_ema_seeded      = false;

void stability_init(float sigma_g) {
    s_sigma_g        = sigma_g;
    // Derive slope threshold from measured noise floor — never hardcode.
    // noise-floor slope ≈ 3 × sigma_g; multiplier 5 gives 1.7× safety margin.
    s_slope_threshold = fmaxf(15.0f, 5.0f * sigma_g);
    Serial.printf("[STAB] slope_threshold=%.1f g/s (sigma=%.2fg)\n",
                  s_slope_threshold, sigma_g);
    s_state          = STAB_WAITING;
    s_ema_g          = 0.0f;
    s_prev_ema_g     = 0.0f;
    s_persistence    = 0;
    s_settling_count = 0;
    s_ema_seeded     = false;
}

StabilityResult stability_update(const ScaleResult& reading) {
    StabilityResult result;

    if (reading.quality == FAILED) {
        result.state         = s_state;
        result.ema_g         = s_ema_g;
        result.slope_g_per_s = 0.0f;
        result.delta_g       = 0.0f;
        result.quality       = FAILED;
        snprintf(result.diagnosis, 64, "ADC read failed - holding state");
        return result;
    }

    result.quality = reading.quality;

    // EMA update. Seeded on first call to avoid false slope spike at boot
    // (s_ema_g=0 vs actual weight e.g. 12000g would produce slope=120000 g/s).
    // Frozen in STAB_STABLE_SETTLED - EMA value is captured result, not live.
    if (s_state != STAB_STABLE_SETTLED) {
        if (!s_ema_seeded) {
            s_ema_g      = reading.raw_grams;
            s_prev_ema_g = reading.raw_grams;
            s_ema_seeded = true;
        } else {
            s_prev_ema_g = s_ema_g;
            s_ema_g = STABILITY_EMA_ALPHA * reading.raw_grams
                    + (1.0f - STABILITY_EMA_ALPHA) * s_ema_g;
        }
    }

    // Slope in g/s. Loop period is 100ms = 0.1s.
    float diff  = s_ema_g - s_prev_ema_g;
    float slope = (diff < 0.0f ? -diff : diff) / 0.1f;

    switch (s_state) {

        case STAB_WAITING:
            if (slope > s_slope_threshold) {
                s_persistence++;
                if (s_persistence >= STABILITY_PERSISTENCE_K) {
                    s_state       = STAB_POUR_IN_PROGRESS;
                    s_persistence = 0;
                    snprintf(result.diagnosis, 64,
                        "pour start detected slope=%.1fg/s", slope);
                    break;
                }
            } else {
                s_persistence = 0;
            }
            snprintf(result.diagnosis, 64,
                "watching. ema=%.1fg slope=%.1fg/s", s_ema_g, slope);
            break;

        case STAB_POUR_IN_PROGRESS:
            if (slope <= s_slope_threshold) {
                s_persistence++;
                if (s_persistence >= STABILITY_K_STOP) {
                    s_state          = STAB_SETTLING;
                    s_settling_count = 0;
                    s_persistence    = 0;
                    snprintf(result.diagnosis, 64, "pour stopped - entering SETTLING");
                } else {
                    snprintf(result.diagnosis, 64,
                        "pour stopping? count=%d/%d", s_persistence, STABILITY_K_STOP);
                }
            } else {
                s_persistence = 0;
                snprintf(result.diagnosis, 64,
                    "pouring. ema=%.1fg slope=%.1fg/s", s_ema_g, slope);
            }
            break;

        case STAB_SETTLING:
            s_settling_count++;
            if (s_settling_count >= STABILITY_SETTLING_SAMPLES) {
                s_state = STAB_STABLE_SETTLED;
                snprintf(result.diagnosis, 64, "settled - delta ready");
            } else {
                snprintf(result.diagnosis, 64,
                    "settling. count=%d/%d",
                    s_settling_count, STABILITY_SETTLING_SAMPLES);
            }
            break;

        case STAB_STABLE_SETTLED:
            snprintf(result.diagnosis, 64,
                "settled. delta=%.1fg", s_baseline_g - s_ema_g);
            break;
    }

    result.state         = s_state;
    result.ema_g         = s_ema_g;
    result.slope_g_per_s = slope;
    result.delta_g       = s_baseline_g - s_ema_g;

    return result;
}

void stability_reset(float new_baseline_g) {
    s_baseline_g     = new_baseline_g;
    s_state          = STAB_WAITING;
    s_persistence    = 0;
    s_settling_count = 0;
    // s_ema_g intentionally NOT reset - EMA continues from settled value.
    // This avoids a false slope spike on the next call since the settled weight
    // already matches new_baseline_g at the moment of reset.
}
