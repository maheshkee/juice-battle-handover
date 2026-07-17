#include "comms.h"
#include <NimBLEDevice.h>
#include "config.h"

static uint8_t            s_node_id = 0;
static uint16_t           s_seq_num = 0;
static NimBLEAdvertising* s_adv     = nullptr;

// Build the 13-byte payload and update BLE advertising manufacturer data.
// Hub BLE scanner on AQ3 reads manufacturer-specific data from advertising
// packets — no connection needed, purely passive scan.
// Stop, update manufacturer data, restart — standard NimBLE 2.x pattern.
static void _advertise(uint8_t msg_type, float delta_g, float sigma_g) {
    if (s_adv == nullptr) return;

    uint8_t buf[13];
    buf[0] = COMMS_PAYLOAD_VERSION;
    buf[1] = msg_type;
    buf[2] = s_node_id;
    memcpy(&buf[3],  &delta_g, 4);   // float → 4 bytes, little-endian on ESP32
    memcpy(&buf[7],  &sigma_g, 4);
    memcpy(&buf[11], &s_seq_num, 2);
    s_seq_num++;  // wraps at 65535, intentional

    s_adv->stop();
    s_adv->setManufacturerData(buf, 13);
    s_adv->start();

    Serial.printf("[COMMS] tx msg=0x%02X delta=%.1f sigma=%.2f seq=%u\n",
                  msg_type, delta_g, sigma_g, (unsigned)(s_seq_num - 1));
}

void comms_init(uint8_t node_id, float sigma_g) {
    s_node_id = node_id;
    s_seq_num = 0;

    char name[8];
    snprintf(name, sizeof(name), "JB-%d", (int)node_id);

    NimBLEDevice::init(name);
    // Set TX power to +9 dBm (maximum) for market stall range
    NimBLEDevice::setPower(9);

    s_adv = NimBLEDevice::getAdvertising();

    // Non-connectable advertising — hub scans passively, never connects
    s_adv->setConnectableMode(BLE_GAP_CONN_MODE_NON);

    // 100ms advertising interval: hub scanner sees new payloads within 100ms of events
    s_adv->setMinInterval(160);  // 160 × 0.625ms = 100ms
    s_adv->setMaxInterval(160);

    // Device name set once — identifies node without parsing payload
    // "JB-0" for NODE_ID=0, "JB-1" for NODE_ID=1
    s_adv->setName(name);

    // Send initial heartbeat to confirm BLE is up
    _advertise(COMMS_MSG_HEARTBEAT, 0.0f, sigma_g);

    Serial.printf("[COMMS] init complete: node_id=%u name=%s sigma=%.2f\n",
                  node_id, name, sigma_g);
}

void comms_send_heartbeat(float sigma_g) {
    _advertise(COMMS_MSG_HEARTBEAT, 0.0f, sigma_g);
}

void comms_send_pour_active(float delta_g, float sigma_g) {
    _advertise(COMMS_MSG_POUR_ACTIVE, delta_g, sigma_g);
}

void comms_send_pour_settled(float delta_g, float sigma_g) {
    _advertise(COMMS_MSG_POUR_SETTLED, delta_g, sigma_g);
}

void comms_send_cal_complete(float sigma_g) {
    _advertise(COMMS_MSG_CAL_COMPLETE, 0.0f, sigma_g);
}

void comms_send_sigma_alert(float sigma_g) {
    _advertise(COMMS_MSG_SIGMA_ALERT, 0.0f, sigma_g);
}
