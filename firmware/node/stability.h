#pragma once
#include "types.h"
#include "scale.h"

// Four states the stability engine can be in.
// Each state exists for a precise physical reason - see comments in stability.cpp.
enum StabilityState {
    STAB_WAITING,           // idle, watching for pour start
    STAB_POUR_IN_PROGRESS,  // pour detected, watching for slope to drop
    STAB_SETTLING,          // slope dropped, waiting for EMA to catch up to reality
    STAB_STABLE_SETTLED     // EMA settled - delta_g is now valid to read
};

struct StabilityResult {
    StabilityState state;         // current state of the engine
    float          ema_g;         // current EMA output in grams
    float          slope_g_per_s; // current slope magnitude in g/s
    float          delta_g;       // weight removed since last baseline - ONLY valid in STAB_STABLE_SETTLED
    Quality        quality;       // GOOD / DEGRADED / FAILED
    char           diagnosis[64];
};

// Call once at boot after noise_measure() to give the engine its sigma.
// WHY: slope and spread thresholds are derived from sigma_live at runtime,
// not hardcoded - they adapt to actual operating noise floor.
void stability_init(float sigma_g);

// Call every loop iteration with the latest scale reading.
// WHY: stability owns the state machine. juicebattle.ino just feeds it
// readings and reads the result - zero logic in the orchestrator.
StabilityResult stability_update(const ScaleResult& reading);

// Reset state machine back to STAB_WAITING and capture new baseline.
// Called by juicebattle.ino after STAB_STABLE_SETTLED is processed.
void stability_reset(float new_baseline_g);
