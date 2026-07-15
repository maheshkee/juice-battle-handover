// firmware/node/node.ino
// Orchestrator — zero logic. Only wires modules.
// TEMPORARY: noise test mode to verify ADS1232 + noise.cpp before building further.
#include "config.h"
#include "types.h"
#include "ads1232.h"
#include "noise.h"

void setup() {
    Serial.begin(115200);
    delay(2000);  // wait for Serial monitor

    Serial.println("=== Juice Battle Node — Noise Test ===");

    ads1232_init();

    Serial.println("Collecting 100 samples (~10s at 10 SPS)...");
    Serial.println("Run this TWICE: once quiet, once with motor/music running.");

    NoiseResult r = noise_measure(100);

    Serial.printf("sigma_raw = %.2f counts\n", r.sigma_raw);
    Serial.printf("sigma_g   = %.3f g\n",      r.sigma_g);
    Serial.printf("quality   = %s\n",
        r.quality == QUALITY_GOOD     ? "GOOD" :
        r.quality == QUALITY_DEGRADED ? "DEGRADED" : "FAILED");
    Serial.printf("diagnosis = %s\n", r.diagnosis);
}

void loop() {
    // nothing — run once
}
