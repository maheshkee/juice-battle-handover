#include "comms.h"
#include <NimBLEDevice.h>
#include <algorithm>
#include "config.h"

static NimBLECharacteristic* s_char             = nullptr;
static uint16_t               g_seq             = 0;
static float                  g_sigma_g         = 0.0f;

class ServerCallbacks : public NimBLEServerCallbacks {
    void onConnect(NimBLEServer* pServer, NimBLEConnInfo& connInfo) override {
        Serial.printf("[COMMS] onConnect fired: peer=%s\n", connInfo.getAddress().toString().c_str());
        // WHY: reject any device that is not AQ3. Office BT devices steal the
        // node the moment it advertises. Application-layer MAC check is more
        // reliable than HCI filter policy on NimBLE.
        std::string peer = connInfo.getAddress().toString();
        std::string hub  = std::string(HUB_MAC);
        std::transform(peer.begin(), peer.end(), peer.begin(), ::tolower);
        std::transform(hub.begin(),  hub.end(),  hub.begin(),  ::tolower);
        if (peer != hub) {
            Serial.printf("[COMMS] rejected %s — not AQ3\n", peer.c_str());
            pServer->disconnect(connInfo.getConnHandle());
            NimBLEDevice::startAdvertising();  // onDisconnect may not fire when called from onConnect
            return;
        }
        Serial.printf("[COMMS] AQ3 connected: %s\n", peer.c_str());
    }

    void onDisconnect(NimBLEServer* pServer, NimBLEConnInfo& connInfo, int reason) override {
        // WHY: restart advertising immediately so hub can reconnect without node reboot
        NimBLEDevice::startAdvertising();
        Serial.println("[COMMS] Hub disconnected - restarting advertising");
    }
};

static ServerCallbacks s_server_callbacks;

static void _send_payload(uint8_t msg_type, float delta_g) {
    if (s_char == nullptr) return;
    if (NimBLEDevice::getServer()->getConnectedCount() == 0) return;

    uint8_t buf[13];
    buf[0] = COMMS_PAYLOAD_VERSION;
    buf[1] = msg_type;
    buf[2] = (uint8_t)NODE_ID;
    memcpy(buf + 3,  &delta_g,  4);   // little-endian float on ESP32
    memcpy(buf + 7,  &g_sigma_g, 4);
    memcpy(buf + 11, &g_seq,     2);
    g_seq++;

    s_char->setValue(buf, 13);
    bool ok = s_char->notify();

    Serial.printf("[COMMS] tx msg=0x%02X delta=%.1f sigma=%.2f seq=%u ok=%d\n",
                  msg_type, delta_g, g_sigma_g, (unsigned)(g_seq - 1), (int)ok);
}

void comms_init(float sigma_g) {
    g_sigma_g = sigma_g;
    g_seq     = 0;

    char node_name[8];
    snprintf(node_name, sizeof(node_name), "JB-%d", (int)NODE_ID);

    NimBLEDevice::init(node_name);

    NimBLEServer* server = NimBLEDevice::createServer();
    server->setCallbacks(&s_server_callbacks);

    NimBLEService* service = server->createService(JB_SERVICE_UUID);

    s_char = service->createCharacteristic(
        JB_CHAR_UUID,
        NIMBLE_PROPERTY::NOTIFY
    );

    service->start();

    NimBLEAdvertising* adv = NimBLEDevice::getAdvertising();
    adv->addServiceUUID(JB_SERVICE_UUID);
    adv->setName(node_name);
    adv->start();

    Serial.printf("[COMMS] GATT init: name=%s sigma=%.2f uuid=%s\n",
                  node_name, sigma_g, JB_SERVICE_UUID);
}

void comms_send_heartbeat(float delta_g) {
    _send_payload(COMMS_MSG_HEARTBEAT, delta_g);
}

void comms_send_pour_active(float delta_g) {
    _send_payload(COMMS_MSG_POUR_ACTIVE, delta_g);
}

void comms_send_pour_settled(float delta_g) {
    _send_payload(COMMS_MSG_POUR_SETTLED, delta_g);
}

void comms_send_cal_complete() {
    _send_payload(COMMS_MSG_CAL_COMPLETE, 0.0f);
}

void comms_send_sigma_alert() {
    _send_payload(COMMS_MSG_SIGMA_ALERT, 0.0f);
}

void comms_send_diag(float current_g, float slope_gs, uint8_t state, uint8_t quality) {
    if (s_char == nullptr) return;
    if (NimBLEDevice::getServer()->getConnectedCount() == 0) return;

    uint8_t buf[13];
    buf[0] = COMMS_PAYLOAD_VERSION;
    buf[1] = COMMS_MSG_DIAG;
    buf[2] = (uint8_t)NODE_ID;
    memcpy(buf + 3, &current_g, 4);
    memcpy(buf + 7, &slope_gs,  4);
    buf[11] = state;
    buf[12] = quality;

    s_char->setValue(buf, 13);
    bool ok = s_char->notify();

    Serial.printf("[COMMS] tx DIAG current=%.1f slope=%.3f state=%u quality=%u ok=%d\n",
                  current_g, slope_gs, (unsigned)state, (unsigned)quality, (int)ok);
}

