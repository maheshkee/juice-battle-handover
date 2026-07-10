# INTERFACE CONTRACTS — Juice Battle
# Status: STUB — to be completed in Phase 0

All data boundaries between components are defined here.
Contract first, code second — always.

---

## 1. ESP32 Node → UNO Q Hub (WiFi / MQTT)

### Topic
```
juice_battle/node/{node_id}/weight
```

### Payload (JSON, sent on every reading and on every pour event)
```json
{
  "node_id":    0,
  "weight_g":   842.5,
  "is_pour":    true,
  "pour_g":     187.3,
  "quality":    "GOOD",
  "timestamp":  "2026-07-10T14:32:00"
}
```

### Field rules
- `node_id`: integer, 0 = Jar A, 1 = Jar B. Never hardcoded anywhere except `config.h`.
- `weight_g`: float, grams. Always post-tare, post-calibration. Never raw ADC counts.
- `is_pour`: bool. True only when pour event is confirmed (threshold + duration).
- `pour_g`: float. Delta weight since pour started. 0.0 when `is_pour` is false.
- `quality`: string enum. `GOOD` / `DEGRADED` / `FAILED`. Hub must check this before acting.
- `timestamp`: ISO 8601 string from ESP32 internal clock (or milliseconds since boot if no RTC).

### Heartbeat
Node sends every 1 second regardless of pour. Hub considers node offline if no message for 5 seconds.

---

## 2. Python Internal — Module API

### Rule
No module imports another module directly.
All coordination goes through `main.py`.
Every module exposes exactly: `start_service()` and `handle_cmd(cmd: str)`.

```
Module              Owns                                    Exposes
────────────────────────────────────────────────────────────────────────────────
receiver.py         MQTT listener for both nodes            start_service()
                    Node connection state                   handle_cmd(cmd: str)
                    Raw payload parsing                     on_weight_cb (set by main)

game_engine.py      Pour event confirmation                 start_service()
                    Volume calculation (g → ml)             handle_cmd(cmd: str)
                    Score tracking per node                 on_pour_cb (set by main)
                    Game state machine                      get_game_state() → dict
                    SQLite persistence

persona_engine.py   Emotion state per persona               start_service()
                    Battle narrative event generation       handle_cmd(cmd: str)
                    Persona state → UI event translation    on_score_update_cb (set by main)

dashboard.py        Socket.IO bridge to browser             start_service()
                    UI event formatting                     handle_cmd(cmd: str)
                    send_game_event(event: dict)
```

---

## 3. Python → Browser (Socket.IO, port 7000)

### Python pushes (ui.send_message pattern)

```python
ui.send_message("score_update", {
    "node_id": 0,
    "persona": "mango_warrior",
    "score": 1240,
    "rival_score": 980,
    "pour_ml": 180,
    "timestamp": "..."
})

ui.send_message("persona_event", {
    "node_id": 0,
    "emotion": "celebrating",
    "narrative": "Mango Warrior strikes! +180ml",
    "timestamp": "..."
})

ui.send_message("node_status", {
    "node_id": 0,
    "online": true,
    "last_seen": "..."
})

ui.send_message("game_state", {
    "state": "active",   # waiting / active / paused / game_over
    "score_0": 1240,
    "score_1": 980,
    "leader": 0,
    "duration_s": 1842
})
```

---

## 4. UNO Q MCU → Python (Bridge RPC)

The UNO Q MCU is NOT in the sensor data path for Juice Battle.
It handles LED indicators only.

```
Function name      Args         Returns   Notes
──────────────────────────────────────────────────────────────────
set_game_led       state: bool  none      Game-active indicator LED
set_node_led       id, state    none      Node A or B connected indicator
```

---

## 5. Config (config.py) — All Thresholds

```python
# Node IDs
NODE_A = 0
NODE_B = 1

# Juice density (g/ml) — used to convert weight delta to volume
JUICE_DENSITY_MANGO  = 1.05   # approximate — calibrate per juice type
JUICE_DENSITY_ORANGE = 1.04

# Pour detection
POUR_THRESHOLD_G     = 20.0   # minimum weight delta to qualify as a pour
POUR_DURATION_MS     = 500    # must sustain for this long to confirm
POUR_STABLE_COUNT    = 3      # consecutive readings below threshold to end pour

# Network
MQTT_BROKER          = "localhost"   # MQTT runs on UNO Q
MQTT_PORT            = 1883
MQTT_TOPIC_PREFIX    = "juice_battle"

# Node health
NODE_TIMEOUT_S       = 5     # no message for this long = node offline

# Sampling
WEIGHT_SAMPLE_RATE   = 1     # target readings per second from ESP32

# Game
SCORE_UNIT           = "ml"  # scoring unit shown on dashboard
GAME_SESSION_RESET_CMD = "RESET_GAME"

# Web UI
WEBUI_PORT           = 7000
```
