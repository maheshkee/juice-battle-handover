#pragma once
#include <Arduino.h>

// ── Message types ─────────────────────────────────────────────────────────────
// HEARTBEAT    — node alive, broadcast every COMMS_HEARTBEAT_INTERVAL_MS
// POUR_ACTIVE  — node in POUR_IN_PROGRESS state, broadcast periodically
// POUR_SETTLED — one shot when STABLE_SETTLED fires (delta_g is valid)
// CAL_COMPLETE — one shot after successful calibration load/complete
// SIGMA_ALERT  — one shot at boot if sigma_g is dangerously high

#define COMMS_MSG_HEARTBEAT     0x01
#define COMMS_MSG_POUR_ACTIVE   0x02
#define COMMS_MSG_POUR_SETTLED  0x03
#define COMMS_MSG_CAL_COMPLETE  0x04
#define COMMS_MSG_SIGMA_ALERT   0x05

#define COMMS_PAYLOAD_VERSION         0x01
#define COMMS_HEARTBEAT_INTERVAL_MS   2000
#define COMMS_POUR_ACTIVE_INTERVAL_MS  200

// ── Payload layout — 13 bytes total ──────────────────────────────────────────
// Byte  0:     version  (COMMS_PAYLOAD_VERSION = 0x01)
// Byte  1:     msg_type (COMMS_MSG_*)
// Byte  2:     node_id  (NODE_ID from config.h, 0 or 1)
// Bytes 3–6:   delta_g  (float, little-endian via memcpy)
// Bytes 7–10:  sigma_g  (float, little-endian via memcpy)
// Bytes 11–12: seq_num  (uint16_t, little-endian, wraps naturally at 65535)
// Total = 13 bytes. Fits inside BLE advertising payload alongside device name.
// Use memcpy() for floats — never cast float* to byte*, alignment is undefined behaviour.

void comms_init(uint8_t node_id, float sigma_g);
void comms_send_heartbeat(float sigma_g);
void comms_send_pour_active(float delta_g, float sigma_g);
void comms_send_pour_settled(float delta_g, float sigma_g);
void comms_send_cal_complete(float sigma_g);
void comms_send_sigma_alert(float sigma_g);
