#include "config.h"
#include "types.h"
#include "ads1232.h"
#include "noise.h"
#include "cal.h"
#include "scale.h"

// Orchestrator law: setup() and loop() wire modules only.
// No math, no thresholds, no state decisions live here.

void setup() {
    Serial.begin(115200);
    while (!Serial) delay(10);

    Serial.println("=== Juice Battle Node ===");

    // Step 1: initialise ADS1232 hardware
    ads1232_init();
    Serial.println("[BOOT] ADS1232 initialised.");

    // Step 2: measure noise floor - must pass before calibration
    Serial.println("[NOISE] Measuring noise floor...");
    NoiseResult noise = noise_measure(100);
    Serial.printf("[NOISE] sigma_raw=%.2f  sigma_g=%.2fg  quality=%s\n",
        noise.sigma_raw,
        noise.sigma_g,
        noise.quality == GOOD     ? "GOOD" :
        noise.quality == DEGRADED ? "DEGRADED" : "FAILED");

    if (noise.quality == FAILED) {
        Serial.println("[NOISE] FAILED - halting. Fix hardware before calibration.");
        while (true) delay(1000);
    }

    // One-time write - Run 1 calibration (best of three runs, S003)
    // confidence=0.968, sigma_tare=2.54g, quality=GOOD
    // Remove this block after first successful boot confirms values loaded.
    {
        CalResult best;
        best.raw_zero     = 94690;
        best.raw_500      = 148353;
        best.raw_1000     = 201742;
        best.raw_5000     = 630410;
        best.confidence   = 0.968f;
        best.sigma_tare_g = 2.54f;
        best.quality      = GOOD;
        snprintf(best.diagnosis, 64, "Run1 S003. confidence=0.97 sigma=2.54g");
        cal_save_to_nvs(best);
        Serial.println("[CAL] Run 1 best-cal written to NVS.");
    }

    // Step 3: attempt to load calibration from NVS
    CalResult cal;
    bool loaded = cal_load_from_nvs(cal);

    if (loaded) {
        // Existing calibration found - print it and proceed
        Serial.println("[CAL] Loaded from NVS:");
        Serial.printf("  raw_zero  = %d\n",   cal.raw_zero);
        Serial.printf("  raw_500   = %d\n",   cal.raw_500);
        Serial.printf("  raw_1000  = %d\n",   cal.raw_1000);
        Serial.printf("  raw_5000  = %d\n",   cal.raw_5000);
        Serial.printf("  confidence= %.3f\n", cal.confidence);
        Serial.printf("  sigma_tare= %.2fg\n",cal.sigma_tare_g);
        Serial.printf("  quality   = %s\n",
            cal.quality == GOOD ? "GOOD" : "DEGRADED");
        Serial.printf("  diagnosis = %s\n",   cal.diagnosis);

    } else {
        // No stored calibration - run full sequence
        Serial.println("[CAL] No stored calibration found. Starting cal_run()...");
        cal = cal_run();

        Serial.println("\n[CAL] Result:");
        Serial.printf("  raw_zero  = %d\n",   cal.raw_zero);
        Serial.printf("  raw_500   = %d\n",   cal.raw_500);
        Serial.printf("  raw_1000  = %d\n",   cal.raw_1000);
        Serial.printf("  raw_5000  = %d\n",   cal.raw_5000);
        Serial.printf("  confidence= %.3f\n", cal.confidence);
        Serial.printf("  sigma_tare= %.2fg\n",cal.sigma_tare_g);
        Serial.printf("  quality   = %s\n",
            cal.quality == GOOD     ? "GOOD" :
            cal.quality == DEGRADED ? "DEGRADED" : "FAILED");
        Serial.printf("  diagnosis = %s\n",   cal.diagnosis);

        if (cal.quality == FAILED) {
            Serial.println("[CAL] FAILED - halting. See diagnosis above.");
            while (true) delay(1000);
        }

        // Run validation sweep before power cycle
        // Tests model accuracy at intermediate points not used in calibration
        cal_validate(cal);

        Serial.println("\n[CAL] Power cycle now to verify NVS persistence.");
        Serial.println("[CAL] On reboot, should print 'Loaded from NVS' instead of starting cal_run().");
        while (true) delay(1000); // halt - wait for power cycle
    }

    // Step 4: tare the scale
    Serial.println("\n[SCALE] Capturing tare - ensure platform is empty...");
    ScaleResult tare = scale_tare(cal);
    if (tare.quality == FAILED) {
        Serial.printf("[SCALE] Tare FAILED: %s\n", tare.diagnosis);
        while (true) delay(1000);
    }
    Serial.printf("[SCALE] %s\n", tare.diagnosis);
    float tare_g = tare.raw_grams;

    // Step 5: guided scale loop - one object at a time
    Serial.println("\n[SCALE] Interactive scale ready.");
    Serial.println("[SCALE] Each round: place object  Enter  readings  remove  repeat.");
    Serial.println("[SCALE] Send 'q' + Enter at any prompt to quit.\n");

    int round = 1;
    while (true) {

        // Refresh tare before each object - catches any platform drift
        ScaleResult fresh_tare = scale_tare(cal);
        if (fresh_tare.quality != FAILED) {
            tare_g = fresh_tare.raw_grams;
        }

        Serial.printf("--- Round %d ---\n", round);
        Serial.println("Place object on platform, press Enter when ready...");

        // Wait for Enter - check for 'q' to quit
        while (!Serial.available()) delay(10);
        String input = Serial.readStringUntil('\n');
        input.trim();
        if (input == "q" || input == "Q") {
            Serial.println("[SCALE] Exiting scale test.");
            break;
        }

        // 10 second settling countdown
        for (int i = 10; i > 0; i--) {
            Serial.printf("%d...", i);
            delay(1000);
        }
        Serial.println(" reading now.\n");

        // Take 10 readings over 5 seconds and print each
        float sum = 0.0f;
        int   count = 0;
        for (int i = 0; i < 10; i++) {
            ScaleResult r = scale_read(cal, tare_g);
            scale_print(r);
            if (r.quality == GOOD) {
                sum += r.grams;
                count++;
            }
            delay(500);
        }

        // Print average of the 10 readings
        if (count > 0) {
            Serial.printf("\n[SCALE] Average over %d readings: %.1fg\n", count, sum / count);
        }

        // Prompt removal
        Serial.println("\nRemove object, press Enter...");
        while (!Serial.available()) delay(10);
        input = Serial.readStringUntil('\n');
        input.trim();
        if (input == "q" || input == "Q") {
            Serial.println("[SCALE] Exiting scale test.");
            break;
        }

        // 5 second settle after removal
        for (int i = 5; i > 0; i--) {
            Serial.printf("%d...", i);
            delay(1000);
        }
        Serial.println(" done.\n");

        round++;
    }

    Serial.println("\n[BOOT] Setup complete. loop() idle - stability.cpp next session.");
}

void loop() {
    // Orchestrator law: loop owns zero logic until stability.cpp exists.
    // Nothing here until next module is ready.
    delay(1000);
}
