// firmware/node/config.h
// Central configuration for all Juice Battle node modules.
#pragma once

// ── ADS1232 pin assignments ──────────────────────────────────────────────────
#define ADS_PIN_SCLK        4    // GPIO4 — clock output to ADS1232
#define ADS_PIN_DOUT        5    // GPIO5 — data input from ADS1232 (also DRDY)
#define ADS_PIN_PDWN        6    // GPIO6 — power down control (HIGH=active)
#define ADS_PIN_A0          7    // GPIO7 — channel select (LOW=ch1, HIGH=ch2)

// ── ADS1232 operational constants ────────────────────────────────────────────
#define ADS_READY_TIMEOUT_MS     1100   // max wait for DRDY low (>1 conversion period at 10SPS)
#define ADS_WARMUP_MS             200   // wait after PDWN HIGH before first read
#define ADS_CHANNEL               LOW   // A0 LOW = channel 1 (our load cell)

// ── Nominal calibration factor (pre-calibration estimate only) ───────────────
// CZL601 40kg: 2mV/V × 5V / 40000g = 0.25µV/g
// ADS1232 gain=128, VREF=5V: LSB = 4.656nV → 53.7 counts/gram
// Used ONLY in noise.cpp to convert σ_raw to σ_g before real cal is available.
#define ADS_NOMINAL_COUNTS_PER_GRAM   54.0f

// ── Noise floor quality thresholds ───────────────────────────────────────────
// Derived from pour detection SNR requirements (200g pour ≈ 43 g/s slope):
//   GOOD:     σ_live < 10g  → SNR ≥ 2.5× achievable with N=6
//   DEGRADED: σ_live < 30g  → SNR requires larger N, slower detection
//   FAILED:   σ_live ≥ 30g  → cannot reliably detect 200g pours
#define NOISE_SIGMA_G_GOOD        10.0f
#define NOISE_SIGMA_G_DEGRADED    30.0f

// ── Noise measurement parameters ─────────────────────────────────────────────
#define NOISE_SAMPLE_COUNT_DEFAULT  100  // samples for σ measurement
#define NOISE_SAMPLE_COUNT_MIN        2  // minimum valid sample count
#define NOISE_MAX_ERROR_RATE       0.25f // if >25% of reads fail → FAILED

// ── Measured noise floor (from S002 noise test, office + fan, empty platform) ──
// σ_live = 6.23g. Update this after first deployment in real stall environment.
// All stability thresholds below are derived from this measurement.
#define MEASURED_SIGMA_LIVE_G            6.23f

// Derived thresholds - recalculate if MEASURED_SIGMA_LIVE_G changes
#define STABILITY_SPREAD_THRESHOLD_G    25.0f  // 4 × σ_live - stability gate

// slope_threshold is runtime-computed in stability_init() from sigma_g.
// Formula: fmaxf(15.0f, 5.0f * sigma_g)
// WHY: noise-floor slope ≈ alpha × sigma / dt = 0.3 × sigma / 0.1 = 3 × sigma_g
// Multiplier 5 gives 1.7× safety margin above noise floor.
// sigma=3g → 15 g/s (normal). sigma=8g → 40 g/s (noisy environment).
// Hardcoding 15 g/s failed because sigma=8.44g → noise-floor slope=25 g/s > 15.

#define STABILITY_PERSISTENCE_K             3  // consecutive samples before POURING declared
#define STABILITY_K_STOP                    8
// WHY: 8 consecutive samples below slope_threshold before declaring pour done.
// 8 × 100ms = 800ms confirmation window.
// Prevents false settlement from a tap pause mid-pour (K=3 was too fast).

// EMA smoothing factor. α=0.3 gives ~7 samples to converge (1/α).
// Higher α = faster response but more noise. Lower α = smoother but slower.
// At 10 SPS: α=0.3 → ~700ms lag. Acceptable for settle detection.
#define STABILITY_EMA_ALPHA            0.3f

// Samples to wait in SETTLING before accepting EMA as converged.
// At α=0.3: EMA reaches 95% of final value in ~9 samples (~900ms).
// 5 samples = conservative minimum; real convergence verified by slope drop.
#define STABILITY_SETTLING_SAMPLES         5

// ── Calibration reference weights (government-certified cast iron stones) ──────
#define CAL_REF_1_G              500.0f
#define CAL_REF_2_G             1000.0f
#define CAL_REF_3_G             5000.0f

// ── Calibration sampling ──────────────────────────────────────────────────────
#define CAL_BLOCK_SAMPLES           50    // samples per block average
#define CAL_STABILITY_WINDOW        10    // samples in sliding window for stable detection

// ── Tare guard - if platform reads more than this before tare, abort ──────────
#define CAL_TARE_MAX_G            100.0f

// ── Confidence thresholds ─────────────────────────────────────────────────────
#define CAL_CONFIDENCE_MIN         0.85f
#define CAL_MAX_ACCEPTABLE_SPREAD  0.08f  // 8% spread = zero confidence boundary
                                          // CZL601 shows ~1.2% natural nonlinearity - corrected by piecewise model
                                          // Threshold set empirically from S003 hardware measurement

// ── Nominal sensitivity estimate from S002 hardware measurement ───────────────
// Used ONLY during calibration before cal model exists
// Value: sigma_raw=336.18 at sigma_g=6.23 → approx 54 counts/gram
#define NOMINAL_COUNTS_PER_GRAM   54.0f

// ── NVS namespace and keys ────────────────────────────────────────────────────
#define NVS_NAMESPACE             "jb_cal"
#define NVS_KEY_RAW_ZERO          "raw_zero"
#define NVS_KEY_RAW_500           "raw_500"
#define NVS_KEY_RAW_1000          "raw_1000"
#define NVS_KEY_RAW_5000          "raw_5000"
#define NVS_KEY_CONFIDENCE        "confidence"
#define NVS_KEY_SIGMA_TARE        "sigma_tare"
#define NVS_KEY_VALID             "valid"

// ── Calibration UX timing ─────────────────────────────────────────────────────
#define CAL_SETTLING_COUNTDOWN_S     10    // countdown after weight placed before stability check
#define CAL_REMOVAL_COUNTDOWN_S       5    // countdown after weight removed before next phase

// ── Validation sweep weights (grams) - tested after cal completes ─────────────
// Using combination stones: 200 alone, 200+500, 500+1000, 10kg alone
#define CAL_VAL_COUNT                 4
#define CAL_VAL_TOLERANCE            0.05f  // 5% max acceptable error per point

// Validation expected weights - must match CAL_VAL_COUNT
// Stored as float array - defined in cal.cpp

// ── Scale baseline capture ────────────────────────────────────────────────────
// Samples averaged during baseline capture. 20 × 100ms = 2s boot time.
// sigma_avg = sigma / sqrt(20) ~ 4.5x noise reduction on baseline.
#define SCALE_BASELINE_SAMPLES          20

// Max spread (max-min) of baseline samples allowed before DEGRADED quality.
// Normal spread ~ sigma_g (2-5g). >20g means something moved during capture.
// DEGRADED does not halt - node continues with degraded baseline quality flag.
#define SCALE_BASELINE_MAX_SPREAD_G     20.0f

// ── Node identity ─────────────────────────────────────────────────────────────
// The ONLY value that differs between two node binaries.
// Node A (jar 0) = 0. Node B (jar 1) = 1.
#define NODE_ID  1
