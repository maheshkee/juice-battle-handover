# Juice Battle Hub Configuration
# All constants live here. No hardcoding in other modules.

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
