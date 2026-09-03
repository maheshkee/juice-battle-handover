# Juice Battle — Dharanova

A two-player crowd-interactive juice-pouring game with real-time BLE weighing, per-round scoring, and live audience display. Built by Dharanova. Deployed at IoT Summit 2026.

> **This is a test extraction repo** (`maheshkee/juice-battle-1`).
> Active development still pushes to `gratiantechnologies/project13` on branch `juice-battle-main`.
> This repo will become the primary once the migration is validated end-to-end.

---

<!-- LIVE:START -->
## Current State

**Last documented session:** S019 — 2026-08-07
**Source:** [docs/HANDOFF_2026_08_07_FINAL_S019.md](docs/HANDOFF_2026_08_07_FINAL_S019.md)
**Most recent stable tag:** `stable-s024` (2026-08-13)

### What is working (S019 verified)

- JB-0 (Lemon Warrior, `70:AF:09:32:F3:C2`, node=0): connected, scoring
- JB-1 (Melon Crusher, `AC:27:6E:53:DC:4A`, node=1): connected, scoring
- Firmware: 5 s supervision timeout via `onConnect updateConnParams` — both nodes reflashed
- Services: `juice-ble-scanner` + `juice-battle` running, boot-enabled on AQ3
- Dashboard: `http://AQ3:5000/` live on Arzopa 28" via wireless HDMI kiosk
- Auto-round system: `ROUND_SIZE=10` glasses combined, persisted in SQLite `kv_store`, 10 s TTS cooldown
- Clean-restart flag: SIGTERM → fresh scores; crash or power loss → session resumes
- Audio: `fuzzy_horizon.mp3` single-track loop; TTS announcements; pygame buffer 8192, `~/.asoundrc` dmix route (installed by `setup.sh` from `hub/asoundrc`)
- BLE ghost-connection watchdog: 60 s eviction cycle via `bluetoothctl remove`; firmware supervision timeout 5 s

### Next session scope

- Session architecture (three-tier: all-time / session / round) — designed in S019, not yet built
- Startup BLE discovery: programmatic scan at boot (eliminates manual `bluetoothctl scan on` workaround)
- End-to-end pour test with full round completion from both jars
- Authoritative doc: [docs/HANDOFF_2026_08_07_FINAL_S019.md](docs/HANDOFF_2026_08_07_FINAL_S019.md)

### Node hardware state

| Node | MAC | NODE_ID | σ_g | Cal | Power |
|------|-----|---------|-----|-----|-------|
| JB-0 | `70:AF:09:32:F3:C2` | 0 | ~3.15 g | NVS persisted | USB adapter |
| JB-1 | `AC:27:6E:53:DC:4A` | 1 | ~3.92 g | NVS persisted | USB adapter |

<!-- LIVE:END -->

---

## What This Is

Two teams, two jars, one audience. Each jar sits on a precision load cell — one per team. Visitors pour juice into their jar. Every pour is detected in real time over BLE and scored. The crowd watches a 28" display showing glass counts, per-round winners, and a running audience total.

No cloud. No internet dependency. No laptop at the stall. Runs entirely on an Arduino UNO Q (Linux MPU + Zephyr MCU) with two ESP32-C3 sensor nodes.

---

## Architecture

> `docs/ARCHITECTURE.md` is a Phase 0 planning stub that describes a WiFi/MQTT design abandoned in S007. The diagram below reflects the actual deployed system.

```
CZL601 (jar A)     CZL601 (jar B)
     │                   │
  ADS1232             ADS1232
     │                   │
ESP32-C3 JB-0      ESP32-C3 JB-1
(firmware/node/)   (firmware/node/)
     │   BLE GATT        │   BLE GATT
     └────────┬───────────┘
              │
       BlueZ D-Bus (AQ3 Linux)
              │
       hub/ble_scanner.py
              │ TCP :7001
       hub/main.py  (orchestrator — zero logic)
         ┌────┴────┐
    game.py    storage.py
         └────┬────┘
       dashboard.py (Flask + Socket.IO :5000)
              │
       Chromium kiosk → Arzopa 28" display
```

| Link | Protocol | Verified |
|------|----------|---------|
| Load cell → ADS1232 | Analog differential | S003 |
| ADS1232 → ESP32-C3 | Bit-bang SPI-like (SCLK/DOUT) | S003 |
| ESP32-C3 → AQ3 | BLE GATT notify (NimBLE 2.5.0) | S007 |
| hub → browser | Flask + Socket.IO v4.6.1 (served locally, no CDN) | S010 |
| AQ3 → display | Wireless HDMI | S018 |

**Architecture laws — non-negotiable:**

- Hub = brain. Owns all logic, state, scoring, history.
- Node = sensor. Reports `delta_g` only. No decisions, no business logic.
- `main.py` = orchestrator. Zero logic. Wires modules only.

---

## Hardware

> Source: `docs/HARDWARE_MANIFEST.md` (Phase 0 baseline) combined with session-verified values from `docs/SESSIONS.md`.

| Component | Qty | Notes |
|-----------|-----|-------|
| Arduino UNO Q | 1 | Hub. Linux MPU (4× Cortex-A53, 4 GB RAM) + Zephyr MCU (STM32 Cortex-M33) |
| ESP32-C3 SuperMini | 2 | Sensor nodes JB-0 and JB-1. BLE 5.0, 3.3 V GPIO, RISC-V 160 MHz, 4 MB flash |
| CZL601 single-point load cell | 2 | 40 kg rated. Validated to <2% error across 200 g–10 kg range (S003) |
| ADS1232 24-bit ADC board | 2 | TI ADS1232. 10 SPS (SPEED → GND). 5 V AVDD, 3.3 V DVDD |
| Arzopa 28" display | 1 | Kiosk scoreboard |
| Wireless HDMI TX/RX | 1 | Cable-free video from AQ3 to display |
| USB-C PD adapter | 1 | Powers AQ3 at stall (no laptop) |
| USB adapters | 2 | Power JB-0 and JB-1 independently |

**JB-1 wiring:** green and white load cell wires are swapped at ADS1232 INNA+/INNA− to correct polarity. Both nodes also negate `raw_value` in firmware. Confirmed S012b.

**Voltage discipline:** AQ3 MCU headers are 3.3 V. JCTL/JMISC are 1.8 V only — applying 3.3 V causes permanent hardware damage.

---

## Repo Structure

```
juice-battle/
├── CLAUDE.md                          # AI agent working contract
├── SESSION_CLOSE_PROTOCOL.md          # Mandatory session-close checklist
├── deploy.sh                          # Developer redeploy (restart services)
├── setup.sh                           # One-time board setup
├── docs/
│   ├── ARCHITECTURE.md                # Phase 0 stub (WiFi/MQTT — superseded by BLE)
│   ├── BACKLOG.md
│   ├── BLE_TRANSPORT_DEBUG_POSTMORTEM.md
│   ├── HANDOFF_*.md                   # Per-session handoff docs (S003–S019)
│   ├── HARDWARE_MANIFEST.md           # Phase 0 hardware baseline
│   ├── INTERFACE_CONTRACTS.md
│   ├── LEARNINGS_AND_INSIGHTS.md
│   ├── PROJECT_BRIEF.md
│   ├── PROJECT_CONTEXT.md             # One-screen current state — replace each session
│   ├── RESEARCH.md
│   ├── SESSIONS.md                    # Session log (S003–S015)
│   └── TODO.md
├── firmware/
│   └── node/                          # ESP32-C3 sketch + all C++ modules
│       ├── juicebattle.ino            # Entry point; MAC→node_id table
│       ├── comms.cpp / comms.h        # NimBLE GATT server
│       ├── cal.cpp / cal.h            # Calibration
│       ├── scale.cpp / scale.h        # Weight accumulation
│       ├── noise.cpp / noise.h        # Noise floor / sigma
│       ├── stability.cpp / stability.h# 4-state pour state machine
│       ├── ads1232.cpp / ads1232.h    # ADC driver
│       ├── config.h                   # NODE_ID lives here only
│       └── types.h
├── hub/
│   ├── main.py                        # Orchestrator — zero logic, wires modules
│   ├── ble_scanner.py                 # BlueZ D-Bus BLE GATT pipeline
│   ├── game.py                        # All scoring, round, and state logic
│   ├── storage.py                     # SQLite persistence (jb.db)
│   ├── dashboard.py                   # Flask + Socket.IO, /v3 route
│   ├── ambient.py                     # Background music + TTS announcements
│   ├── transport.py                   # TCP consumer from ble_scanner
│   ├── config.py                      # All tunable constants
│   ├── juice-battle.service           # systemd unit — hub
│   ├── juice-ble-scanner.service      # systemd unit — BLE scanner
│   ├── juice_battle_kiosk.sh          # XFCE kiosk autostart script
│   ├── static/                        # socket.io.js v4.6.1, sounds, assets
│   ├── templates/                     # v3.html (active), v2.html (preserved)
│   ├── data/                          # jb.db — NOT in git
│   └── SYSTEM_RUNBOOK.md              # Operator and developer command reference
├── sessions/
│   ├── S001_bootstrap.md
│   └── S002_architecture_phase1.md
└── tests/
    ├── mock_node.py
    ├── test_game_engine.py
    └── test_weight_engine.py
```

---

## Key Docs

| Document | Purpose |
|----------|---------|
| [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md) | One-screen current state — replace each session close, never append |
| [docs/SESSIONS.md](docs/SESSIONS.md) | Session log with hardware-verified results — append only |
| [docs/LEARNINGS_AND_INSIGHTS.md](docs/LEARNINGS_AND_INSIGHTS.md) | Cross-session lessons and architectural decisions |
| [docs/HANDOFF_2026_08_07_FINAL_S019.md](docs/HANDOFF_2026_08_07_FINAL_S019.md) | Most recent session handoff in this repo |
| [docs/BLE_TRANSPORT_DEBUG_POSTMORTEM.md](docs/BLE_TRANSPORT_DEBUG_POSTMORTEM.md) | BLE failure analysis and recovery patterns |
| [hub/SYSTEM_RUNBOOK.md](hub/SYSTEM_RUNBOOK.md) | Operator and developer command reference |
| [docs/juice_battle_stall_ops.html](docs/juice_battle_stall_ops.html) | Stall operator quick-reference (dark terminal HTML, offline) |

---

## Status

**Test extraction — not the working repo.**

Active development pushes to `gratiantechnologies/project13` on branch `juice-battle-main`. This repo (`maheshkee/juice-battle-1`) is a validated point-in-time extraction of that history. It will become the primary repo once the migration is signed off. Until then, new commits land in project13, not here.

To check which commit is live on the board:

```bash
ssh arduino@AQ3 "cd ~/ArduinoApps/juice_battle && git log -1 --oneline"
```
