# ARCHITECTURE — Juice Battle
# Status: STUB — to be completed in Phase 0

---

## System overview (to be drawn in Phase 0)

```
CZL601 Load Cell (Jar A)          CZL601 Load Cell (Jar B)
        │                                   │
   ADS1232 ADC                         ADS1232 ADC
        │                                   │
 ESP32-C3 Node A                    ESP32-C3 Node B
 (firmware/node/)                   (firmware/node/)
 config.h: NODE_ID=0                config.h: NODE_ID=1
        │                                   │
        └──────── WiFi (MQTT) ──────────────┘
                        │
              Arduino UNO Q (hub)
              /home/arduino/arduino_apps/juice_battle/
                        │
             Python MPU side (hub/)
             ├── main.py (orchestrator)
             ├── receiver.py (MQTT listener)
             ├── game_engine.py (scoring)
             ├── persona_engine.py (narrative)
             └── dashboard.py (Socket.IO)
                        │
             WebUI Brick (port 7000)
                        │
              Browser → index.html
              (live dashboard)
                        │
             MCU side (sketch.ino)
             (LED indicators only)
```

---

## Communication protocols (to be confirmed in Phase 0)

| Link                      | Protocol   | Status  |
|---------------------------|------------|---------|
| Load cell → ADS1232       | Analog     | DERIVED |
| ADS1232 → ESP32-C3        | Bit-bang SPI-like | TBD Phase 1 |
| ESP32-C3 → UNO Q          | WiFi + MQTT (or UDP) | TBD Phase 0 |
| Python → Browser          | Socket.IO  | DERIVED |
| Python ↔ MCU              | Bridge RPC | DERIVED |

---

## Data flow (to be completed in Phase 0)

1. ADS1232 samples load cell at 10 SPS or 80 SPS
2. ESP32-C3 reads raw 24-bit value via bit-bang
3. `weight_engine` applies rolling filter and detects pour events
4. `comms` sends JSON payload to MQTT broker on UNO Q
5. `receiver.py` receives and parses payload
6. `game_engine.py` converts pour → ml → score update → game event
7. `persona_engine.py` translates game event → persona emotion + narrative
8. `dashboard.py` pushes update to browser via Socket.IO
9. Browser renders updated personas, scores, and event feed

---

## MQTT payload schema (to be confirmed in Phase 0)

```json
{
  "node_id": 0,
  "weight_g": 842.5,
  "is_pour": true,
  "pour_g": 187.3,
  "quality": "GOOD",
  "timestamp": "2026-07-10T14:32:00"
}
```

---

## Game event schema (to be confirmed in Phase 0)

```json
{
  "event": "pour_detected",
  "node_id": 0,
  "persona": "mango_warrior",
  "ml_poured": 180,
  "score_delta": 180,
  "new_score": 1240,
  "rival_score": 980,
  "timestamp": "2026-07-10T14:32:01"
}
```

---

## SQLite schema (hub/data/game.db) — to be confirmed in Phase 0

```sql
-- All weights in grams. All volumes in ml.

CREATE TABLE pour_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    TEXT NOT NULL,        -- ISO 8601
    node_id      INTEGER NOT NULL,     -- 0 or 1
    weight_g     REAL NOT NULL,        -- weight at pour start
    pour_g       REAL NOT NULL,        -- delta weight = juice removed
    pour_ml      REAL NOT NULL,        -- pour_g / juice_density
    quality      TEXT NOT NULL         -- GOOD / DEGRADED / FAILED
);

CREATE TABLE game_sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at    TEXT NOT NULL,
    ended_at      TEXT,
    score_node0   REAL NOT NULL DEFAULT 0,
    score_node1   REAL NOT NULL DEFAULT 0,
    winner        INTEGER               -- 0 or 1, NULL if ongoing
);
```
