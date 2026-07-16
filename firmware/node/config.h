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
#define STABILITY_SLOPE_THRESHOLD_GS    15.0f  // pour detection (g/s), ~3× slope noise
#define STABILITY_PERSISTENCE_K             3  // consecutive samples before POURING declared
