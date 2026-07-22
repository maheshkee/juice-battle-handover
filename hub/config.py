# Juice Battle Hub Configuration
# All constants live here. No hardcoding in other modules.

import pathlib

# Absolute path derived from config.py's own location - works regardless
# of which directory python3 is launched from.
DB_PATH = str(pathlib.Path(__file__).parent / 'data' / 'jb.db')

# BLE identity
DEVICE_PREFIX = "JB-"

# GATT UUIDs — must match firmware comms.h JB_SERVICE_UUID / JB_CHAR_UUID
JB_SERVICE_UUID = '7b4c0e00-9aab-11ed-a8fc-0242ac120002'
JB_CHAR_UUID    = '7b4c0f00-9aab-11ed-a8fc-0242ac120002'

# Legacy (advertising mode) — no longer used by ble_scanner.py
COMPANY_ID    = 0xFFFF

# Transport TCP server (scanner publishes here)
TRANSPORT_HOST = "0.0.0.0"
TRANSPORT_PORT = 7001

# Transport TCP client (Docker consumer connects here)
# 172.17.0.1 = Docker bridge gateway = the host from inside Docker
TRANSPORT_CLIENT_HOST = "172.17.0.1"
TRANSPORT_CLIENT_PORT = 7001
TRANSPORT_RECONNECT_S = 5   # seconds between reconnect attempts

# BLE watchdog - if no packets for this long, assume chip crashed
WATCHDOG_TIMEOUT_S = 30

# Payload protocol
PAYLOAD_VERSION  = 0x01
MSG_HEARTBEAT    = 0x01
MSG_POUR_ACTIVE  = 0x02
MSG_POUR_SETTLED = 0x03
MSG_CAL_COMPLETE = 0x04
MSG_SIGMA_ALERT  = 0x05
MSG_DIAG         = 0x06

MSG_NAMES = {
    MSG_HEARTBEAT:    "HEARTBEAT",
    MSG_POUR_ACTIVE:  "POUR_ACTIVE",
    MSG_POUR_SETTLED: "POUR_SETTLED",
    MSG_CAL_COMPLETE: "CAL_COMPLETE",
    MSG_SIGMA_ALERT:  "SIGMA_ALERT",
    MSG_DIAG:         "DIAG",
}

# Game parameters
GLASS_VOLUME_G = 150.0
MIN_DELTA_G    = 10.0

# --- Pour event thresholds (game.py) ---
# POUR_SIGMA_K: dimensionless multiplier - how many sigma_g = minimum real pour (3-sigma rule)
# POUR_MIN_G: fault-mode floor - fires only when sigma_g < 1.67g (node malfunction).
#   10.0 = POUR_SIGMA_K * min_observed_sigma (3.0 * 3.4g, S006-S008).
#   Fault mode should be stricter than normal, not permissive.
# POUR_WINDOW_S: events within this window accumulate (same glass, split settle);
#                gap > window = new visitor, discard stale partial
POUR_SIGMA_K  = 3.0
POUR_MIN_G    = 10.0
POUR_WINDOW_S = 20.0   # was 8.0 - extended for multi-settlement pours (max observed gap: 13.95s)

# POUR_PRESERVE_FRAC: on window expiry, partial >= GLASS_VOLUME_G * this fraction
#   is a pour-in-progress (main body landed, drip pending) - PRESERVE it.
#   Below = overshoot residue from a completed glass - discard is correct.
#   Derived from glass size, not hardcoded: residues observed 12.9-21.9g,
#   destroyed in-progress pour was 91.5g (boss demo). 1/3 glass = 50g separates cleanly.
POUR_PRESERVE_FRAC = 1/3

# POUR_MAX_G_FRAC: single settled delta > this many glasses is physically not a pour
#   (jar lifted off platform = ~5000g positive delta = 33 false glasses).
#   Log as anomaly, do not score.
POUR_MAX_G_FRAC = 3.0

BOUNCE_SETTLE_S  = 5.0    # suppress all events after large negative disturbance
ANOMALY_SETTLE_S = 30.0   # suppress all events after jar-removal anomaly

DASHBOARD_PORT = 5000
