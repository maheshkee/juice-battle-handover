#include "config.h"
#include "types.h"
#include "ads1232.h"
#include "noise.h"
#include "cal.h"
#include "scale.h"
#include "stability.h"
#include "comms.h"
#include "esp_mac.h"


// WHY: NODE_ID is resolved at boot from BT MAC — not compiled in.
// This means one identical binary works for both nodes forever.
uint8_t NODE_ID = 255;  // 255 = unresolved sentinel

// Orchestrator law: setup() and loop() wire modules only.
// No math, no thresholds, no state decisions live here.

// WHY globals: loop() needs g_cal and g_noise on every iteration.
// setup() initialises them once; loop() reads them continuously.
CalResult   g_cal;
NoiseResult g_noise;
float       g_min_pour_g = 0.0f;

static unsigned long s_heartbeat_timer_ms   = 0;
static unsigned long s_pour_active_timer_ms = 0;
static unsigned long s_diag_timer_ms        = 0;

void resolve_node_id() {
    // WHY: MAC is factory-burned into efuse — immutable, survives
    // any flash operation. Using ESP_MAC_BT matches the MAC
    // BlueZ sees during BLE advertising.
    static const struct {
        uint8_t mac[6];
        uint8_t node_id;
    } NODE_MAC_TABLE[] = {
        { {0x70, 0xAF, 0x09, 0x32, 0xF3, 0xC2}, 0 },  // JB-0
        { {0x10, 0x00, 0x3B, 0xCD, 0x63, 0x32}, 1 },  // JB-1
    };

    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_BT);

    for (size_t i = 0;
         i < sizeof(NODE_MAC_TABLE) / sizeof(NODE_MAC_TABLE[0]);
         i++) {
        if (memcmp(mac, NODE_MAC_TABLE[i].mac, 6) == 0) {
            NODE_ID = NODE_MAC_TABLE[i].node_id;
            Serial.printf("[BOOT] node_id=%d resolved from MAC\n",
                          NODE_ID);
            return;
        }
    }

    // MAC not in table — halt. Print MAC so operator can add it.
    while (true) {
        Serial.printf(
            "[BOOT] FATAL: unknown MAC %02X:%02X:%02X:%02X:%02X:%02X"
            " — add to NODE_MAC_TABLE and reflash\n",
            mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
        delay(5000);
    }
}

void setup() {
    Serial.begin(115200);
    // WHY: USB power adapter has no USB host — Serial never enumerates.
    // Wait max 3s for Serial (laptop/debug), then proceed regardless (production).
    { unsigned long _st = millis(); while (!Serial && (millis() - _st < 3000)) delay(10); }
    resolve_node_id();  // Must run before comms_begin() uses NODE_ID

    Serial.println("=== Juice Battle Node ===");

    // STEP 1: Init ADS1232 hardware
    ads1232_init();
    Serial.println("[BOOT] ADS1232 initialised.");

    // STEP 2: Load cal from NVS - hardware model, never changes between boots.
    // If no NVS data: run cal_run(), save, halt for power cycle to verify.
    // If NVS load fails quality check: halt with Serial message.
    bool loaded = cal_load_from_nvs(g_cal);
    if (loaded) {
        Serial.println("[CAL] Loaded from NVS:");
        Serial.printf("  raw_zero  = %d\n",   g_cal.raw_zero);
        Serial.printf("  raw_500   = %d\n",   g_cal.raw_500);
        Serial.printf("  raw_1000  = %d\n",   g_cal.raw_1000);
        Serial.printf("  raw_5000  = %d\n",   g_cal.raw_5000);
        Serial.printf("  confidence= %.3f\n", g_cal.confidence);
        Serial.printf("  quality   = %s\n",
            g_cal.quality == GOOD ? "GOOD" : "DEGRADED");
        Serial.printf("  diagnosis = %s\n",   g_cal.diagnosis);
    } else {
        Serial.println("[CAL] No stored calibration found. Starting cal_run()...");
        g_cal = cal_run();

        if (g_cal.quality == FAILED) {
            Serial.println("[CAL] FAILED - halting. See diagnosis above.");
            while (true) delay(1000);
        }

        cal_validate(g_cal);
        Serial.println("\n[CAL] Power cycle now to verify NVS persistence.");
        Serial.println("[CAL] On reboot, should print 'Loaded from NVS'.");
        while (true) delay(1000);
    }

    // STEP 3: Capture baseline - whatever is on platform NOW becomes zero.
    // WHY before noise: noise must be measured under operating load, not empty platform.
    // Empty platform at install → baseline ~0g. Full jar after reboot → baseline ~3000g.
    // Both are valid. No error condition exists here.
    ScaleResult baseline_result = scale_capture_baseline(g_cal);
    if (baseline_result.quality == FAILED) {
        Serial.printf("[SCALE] Baseline FAILED: %s\n", baseline_result.diagnosis);
        while (true) delay(1000);
    }
    Serial.print("[SCALE] Baseline captured: ");
    Serial.print(scale_get_baseline_g(), 1);
    Serial.println("g on platform");

    // STEP 4: Measure noise under current load.
    // WHY after baseline: load cell noise changes with mechanical load.
    // sigma measured here reflects actual game operating conditions.
    Serial.println("[NOISE] Measuring noise under current load...");
    g_noise = noise_measure(100);
    Serial.printf("[NOISE] sigma_g=%.2fg  quality=%s\n",
        g_noise.sigma_g,
        g_noise.quality == GOOD     ? "GOOD" :
        g_noise.quality == DEGRADED ? "DEGRADED" : "FAILED");

    if (g_noise.quality == FAILED) {
        Serial.println("[NOISE] FAILED - sigma > 10g - hardware fault. Halting.");
        while (true) delay(1000);
    }

    // STEP 5: Init stability engine with live sigma, then set baseline.
    // stability_init() derives thresholds from measured noise floor.
    // stability_reset() sets s_baseline_g = current absolute weight on platform.
    stability_init(g_noise.sigma_g);
    stability_reset(scale_get_baseline_g());
    Serial.println("[STAB] Stability engine initialised.");

    // STEP 6: Compute min pour threshold from live noise floor.
    // Pours below 3×sigma_g are indistinguishable from noise — discard silently.
    g_min_pour_g = 3.0f * g_noise.sigma_g;
    Serial.printf("[INIT] min_pour_g=%.1fg (3 × sigma=%.2fg)\n",
                  g_min_pour_g, g_noise.sigma_g);

    // STEP 7: Print GAME_READY summary, then start BLE comms.
    Serial.println("GAME_READY");
    Serial.print("  Baseline: "); Serial.print(scale_get_baseline_g(), 1); Serial.println("g");
    Serial.print("  Sigma   : "); Serial.print(g_noise.sigma_g, 2); Serial.println("g");

    comms_init(g_noise.sigma_g);


    pinMode(8, OUTPUT);
    digitalWrite(8, HIGH);  // off at boot (active-low)

}

void loop() {

    ScaleResult     r  = scale_read(g_cal, g_noise.sigma_g);
    StabilityResult sr = stability_update(r);

    Serial.printf("[STAB] state=%d  ema=%7.1fg  slope=%5.1fg/s  delta=%7.1fg  %s\n",
        sr.state, sr.ema_g, sr.slope_g_per_s, sr.delta_g, sr.diagnosis);

    if (sr.state == STAB_WAITING) {
        if (millis() - s_heartbeat_timer_ms >= COMMS_HEARTBEAT_INTERVAL_MS) {
            s_heartbeat_timer_ms = millis();
            comms_send_heartbeat(0.0f);
        }
    }

    if (sr.state == STAB_POUR_IN_PROGRESS) {
        if (millis() - s_pour_active_timer_ms >= COMMS_POUR_ACTIVE_INTERVAL_MS) {
            s_pour_active_timer_ms = millis();
            comms_send_pour_active(sr.delta_g);
        }
    }

    if (sr.state == STAB_STABLE_SETTLED) {
        if (fabsf(sr.delta_g) < g_min_pour_g) {
            // Delta is below noise floor — noise artifact, not a real pour.
            Serial.printf("[POUR] Ignored noise event: %.1fg < min %.1fg\n",
                          sr.delta_g, g_min_pour_g);
            stability_reset(sr.ema_g);
        } else {
            comms_send_pour_settled(sr.delta_g);
            Serial.printf("[POUR] %.1fg dispensed\n", sr.delta_g);
            stability_reset(sr.ema_g);
        }
    }

    if (millis() - s_diag_timer_ms >= COMMS_DIAG_INTERVAL_MS) {
        s_diag_timer_ms = millis();
        comms_send_diag(
            sr.ema_g,
            sr.slope_g_per_s,
            (uint8_t)sr.state,
            (uint8_t)sr.quality
        );
    }

    // --- LED health indicator ---
    if (sr.quality == FAILED) {
        digitalWrite(8, HIGH);                                    // FAILED: off (dark = dead)
    } else if (sr.quality == DEGRADED) {
        digitalWrite(8, (millis() / 1000) % 2 == 0 ? LOW : HIGH); // slow blink 1s
    } else if (sr.state == STAB_POUR_IN_PROGRESS) {
        digitalWrite(8, (millis() / 200) % 2 == 0 ? LOW : HIGH);  // fast blink during pour
    } else {
        digitalWrite(8, LOW);                                     // GOOD + idle: steady on
    }

    delay(100);
}
