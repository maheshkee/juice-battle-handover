# Juice Battle — Handoff S019 → S020
Date: 2026-08-07
Session: S019

---

## WORKING CONTRACT (non-negotiable, every session)
- **Claude Chat = Brain**: architecture, diagnosis, decisions, CLI prompts only
- **Claude CLI = Hands**: ALL file edits, ALL code, ALL bash on board
- **Never write final implementation code in chat**
- `/` and `/v2` routes: NEVER touch. Active dashboard: `/v3`
- `git push` always works — `push.default = upstream` set permanently
- Philosophy: WHY before HOW. First principles always. Nothing "just works."
- Mahesh's style: fast, direct. Make autonomous design decisions when asked.

---

## Current System State (verified at session close)

- JB-0 (Lemon Warrior, node=0, MAC 70:AF:09:32:F3:C2): connected, scoring ✓
- JB-1 (Melon Crusher, node=1, MAC 10:00:3B:CD:63:32): connected, scoring ✓
- Both nodes: new firmware with 5s supervision timeout (onConnect updateConnParams) ✓
- Services: juice-ble-scanner, juice-battle — running + boot-enabled ✓
- Active dashboard: http://AQ3:5000/v3 (kiosk on Arzopa 28" via wireless HDMI)
- Audio: varanasi.mp3 → anirudh.mp3 playlist, MUSIC_VOLUME=0.40, announcements at full
- Git branch: juice-battle-main (push.default = upstream, always use `git push`)
- DB path: hub/data/jb.db (NOT hub/juice_battle.db — that's a stale leftover)
- All S019 changes committed and pushed ✓

---

## What Was Built This Session (S019)

### BLE Reliability (major work)
1. **Ghost connection watchdog** — `_watchdog_ghost_connections()` in ble_scanner.py
   runs every 60s, removes unconnected nodes from BlueZ cache via `bluetoothctl remove`,
   forces NimBLE to re-advertise. 30s startup delay before first run.

2. **Watchdog GATT guard** — watchdog now skips nodes in `_connecting_nodes`
   (mid-handshake). Previously evicted nodes during GATT discovery causing infinite loops.

3. **Connect storm fix** — `_connecting_nodes` pre-claimed at call sites before
   `GLib.idle_add`. Guard inside `_connect()` only checks `_active_connections`
   (not `_connecting_nodes`) to avoid self-blocking.

4. **InterfacesRemoved handler** — `_interfaces_removed()` registered on D-Bus.
   When BlueZ evicts a device, cleans `_active_connections`, stops retry loops,
   schedules reconnect. Prevents permanent "char not found" deadlock.

5. **Firmware fix** — `onConnect` callback with `pServer->updateConnParams(handle, 16, 32, 0, 500)`
   sets 5s supervision timeout correctly (peripheral API, not central API).
   Both JB-0 and JB-1 reflashed with this firmware.

### Auto Round System
- `ROUND_SIZE = 10` in config.py (both jars combined)
- Round counter persists in SQLite kv_store (`round_number`)
- `_trigger_round_end()` in game.py: freezes scoring, determines winner, spawns thread
- 10s cooldown: TTS announcement → wait → reset scores → increment round → resume
- Socket.IO events: `round_over` (payload: round, winner, score0, score1) and `round_begin`
- v3 dashboard: centre-panel overlay with winner display + CSS drain bar animation
- `POST /reset_rounds` endpoint to reset round counter manually

### Clean Shutdown Flag
- SIGTERM → `sys.exit(0)` → `atexit` fires → writes `service_stopped_cleanly=true` to kv_store
- On startup: if flag true → reset jar scores to 0, clear flag (clean restart = fresh game)
- Power loss/crash: flag never written → scores resume (unclean = resume)
- round_number and all-time counter NOT reset on service restart

### Audio Pipeline
- Playlist: `varanasi.mp3` → `anirudh.mp3` (ordered, loops)
- `get_busy()` polling replaces event-driven approach (more reliable on ARM)
- `_announcement_playing` flag prevents false track-end detection during ducking
- pygame mixer buffer: 4096 (was 512) — eliminates ALSA underruns on ARM
- `MUSIC_VOLUME = 0.40`, announcements play at hardware volume (full SDL channel)
- USB audio adapter: ALSA card name "Device" in `~/.asoundrc` (stable across reboots)
- systemd env: `SDL_AUDIODRIVER=alsa`, `AUDIODEV=hw:Device`

### Round Overlay (UI)
- Centre panel transforms on `round_over` event — jar cards remain visible
- Shows: round number, both scores, winner name, 10s CSS drain bar
- `round_begin` event: 2s "ROUND N BEGINS" flash, then returns to normal VS view
- Old full-screen overlay removed

### Ops Reference
- `docs/juice_battle_stall_ops.html` — dark terminal HTML, all live stall commands
- Includes: audio mute/restore, service control, BLE diagnostics, kiosk navigation
- Key fix documented: `export DISPLAY=:0` before xdotool in SSH sessions

---

## Pending Work — Next Session (S020)

### P1 — Session Architecture (HIGHEST PRIORITY — designed, not built)

**Three-tier hierarchy:**
```
All-time  → kv_store, never resets
Session   → one stall day, resets on clean restart
Round     → 10 glasses, auto-resets
```

**Session lifecycle:**
- Clean restart (SIGTERM) → new session, round_number → 1
- Power loss/crash → resume session (Option C hybrid)
- Grace period: if restart >4 hours since last activity → new session regardless

**DB additions needed:**
```sql
-- sessions table already exists but needs human-readable ID and total_glasses
-- Need to ADD:
ALTER TABLE sessions ADD COLUMN session_key TEXT;  -- "2026-08-07-001"
ALTER TABLE sessions ADD COLUMN total_glasses INTEGER DEFAULT 0;

-- New table needed:
CREATE TABLE round_results (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER REFERENCES sessions(id),
    round_number INTEGER NOT NULL,
    score0       INTEGER NOT NULL,
    score1       INTEGER NOT NULL,
    winner       TEXT NOT NULL,  -- 'lemon', 'melon', 'tie'
    completed_at TEXT NOT NULL
);
```

**Jar card display change:**
- Big number → current round glasses only (resets each round, NOT cumulative)
- Small text → "ROUND WINS: 2" (rounds won this session)

**"X IoT Enthusiasts" counter:**
- Shows session total live (counts up in real time)
- All-time counter stays in kv_store separately

**Files to touch:** storage.py, game.py, dashboard.py, v3 template

### P2 — JB-1 Sigma Check
JB-1 sigma = 9.748g (threshold DEGRADED = 10g). Check physical mount:
- Are load cell screws tight?
- Does jar sit flat and stable?
- Is the platform on a vibrating surface?
A crowded stall with people bumping the table could push sigma above 10g.

### P3 — End-to-End Test Run
Pour from both jars, confirm scoring, round completion, audio, overlay.
Has NOT been done yet this session — always something broke before we got here.

### P4 — _find_characteristic Retry Limit
After ~10 retries (~30s), give up, clean _active_connections, trigger fresh connect.
Currently retries forever — self-heals only via 30s packet watchdog restart.

---

## Current DB Schema

```
hub/data/jb.db  ← THE CORRECT DB FILE
  sessions        — id, started_at, ended_at, node_count
  pour_events     — id, session_id, ts, node_id, delta_g, sigma_g, seq, glasses_counted
  node_health     — id, ts, node_id, msg, current_g, slope_gs, state, quality, sigma_g, seq
  error_log       — id, ts, source, message
  overflow_events — id, ts, node_id, seq, reason, grams, window_open_ts
  node_resets     — id, session_id, node_id, reset_at
  kv_store        — key, value
    round_number            → current round (persists)
    service_stopped_cleanly → shutdown flag (transient)
    all_time_glasses        → lifetime pour count
```

---

## BLE — Critical Knowledge (Never Forget)

**JB-1 "not found" = ALWAYS NimBLE ghost connection.**
Node believes it is still connected to a previous central and stops advertising.
Root cause is NEVER BlueZ, NEVER Python scanner code.

**Diagnosis steps (in order):**
1. `bluetoothctl devices | grep JB` — is it in BlueZ cache?
2. If not: power cycle node (unplug 5s, replug) → should appear within 10s
3. If still not: `sudo hciconfig hci0 down && sleep 2 && sudo hciconfig hci0 up`
4. `sudo systemctl restart juice-ble-scanner`

**Ghost connection recovery chain:**
- Firmware fix (5s supervision timeout): auto-recovers within 5s of AQ3 crash
- Scanner watchdog: removes from BlueZ every 60s if not connected
- InterfacesRemoved handler: cleans state if BlueZ evicts the device
- Last resort: power cycle node

**le-connection-abort-by-local error:**
BlueZ adapter dirty state from too many rapid connect/disconnect cycles.
Fix: hciconfig hci0 down/up + restart scanner.

**JB char not found — retrying:**
Node connected at BLE level but GATT discovery pending. Wait up to 60s.
If >60s: `bluetoothctl remove <MAC>` + restart scanner forces fresh discovery.

---

## File Map

```
hub/
  game.py          — Game state, SoundPlayer, round logic, clean-restart flag check
  ambient.py       — AmbientPlayer, varanasi→anirudh playlist, announcements
  main.py          — Orchestrator, SIGTERM handler, atexit, service start
  dashboard.py     — Flask + Socket.IO, all routes including /v3, /reset_rounds
  ble_scanner.py   — BlueZ D-Bus BLE scanner, watchdog, InterfacesRemoved handler
  storage.py       — SQLite, kv_store, round_number, all-time counter
  config.py        — All constants: ROUND_SIZE=10, MUSIC_VOLUME=0.40, DB_PATH, etc.
  data/jb.db       — THE database (not hub/juice_battle.db)
  static/sounds/   — glass.mp3, pour.mp3, fanfare.mp3, cheer.mp3,
                     varanasi.mp3, anirudh.mp3, ann_*.mp3 (TTS announcements),
                     ann_round_winner_*.mp3, ann_round_begin_*.mp3
  templates/       — v3.html (active), v2.html (preserved), index.html (untouched)
  juice-battle.service      — systemd unit
  juice_battle_kiosk.sh     — XFCE autostart, focus-keeper, reload flag

firmware/node/
  juicebattle.ino  — main sketch, MAC→node_id table
  comms.cpp        — NimBLE GATT server, onConnect updateConnParams(5s timeout) ✓
  comms.h, config.h, ads1232.*, cal.*, noise.*, scale.*, stability.*, types.h

/etc/udev/rules.d/
  99-juice-battle-audio.rules  — USB audio hotplug → restart juice-battle

~/.asoundrc      — routes ALSA default to card "Device" (USB adapter by name)
docs/
  juice_battle_stall_ops.html  — live stall operator command reference
```

---

## Developer Terminal Cheat Sheet

```bash
# Both services status
sudo systemctl status juice-ble-scanner juice-battle --no-pager

# Restart both (correct order)
sudo systemctl restart juice-ble-scanner && sleep 2 && sudo systemctl restart juice-battle

# BLE — node status
bluetoothctl devices | grep JB
sudo journalctl -u juice-ble-scanner -f | grep -E "NODE_CONNECTED|WATCHDOG|node="

# BLE — adapter reset (when le-connection-abort-by-local)
sudo hciconfig hci0 down && sleep 2 && sudo hciconfig hci0 up && sleep 2 && sudo systemctl restart juice-ble-scanner

# Game control
curl -s -X POST http://localhost:5000/game_over | python3 -m json.tool
curl -s -X POST http://localhost:5000/reset/0 | python3 -m json.tool
curl -s -X POST http://localhost:5000/reset/1 | python3 -m json.tool
curl -s -X POST http://localhost:5000/reset_rounds | python3 -m json.tool
curl -s -X POST "http://localhost:5000/adjust/0/1" | python3 -m json.tool

# Audio
amixer -c 0 sset Speaker 0%    # silence
amixer -c 0 sset Speaker 90%   # restore
aplay -l                         # verify USB adapter present

# Kiosk (always export DISPLAY first in SSH)
export DISPLAY=:0
xdotool search --name "Juice Battle" | head -1 | xargs -I{} xdotool windowactivate {}
xdotool search --name "Juice Battle" | head -1 | xargs -I{} bash -c 'DISPLAY=:0 xdotool key --window {} ctrl+r'

# DB inspect
sqlite3 ~/ArduinoApps/juice_battle/hub/data/jb.db "SELECT * FROM kv_store;"
sqlite3 ~/ArduinoApps/juice_battle/hub/data/jb.db ".tables"

# Live logs — filtered
sudo journalctl -u juice-ble-scanner -f | grep -E "NODE_CONNECTED|NODE_DISCONNECTED|WATCHDOG|le-connection"
journalctl -u juice-battle -f | grep -E "AmbientPlayer|SoundPlayer|POUR_SETTLED|round|Clean restart"
```

---

## Known Issues / Watch-Outs

- `hub/juice_battle.db` is a stale leftover — never query it. Always use `hub/data/jb.db`
- JB-1 sigma = 9.748g (close to 10g DEGRADED threshold) — check physical mount
- End-to-end pour test not yet done this session
- Session architecture not yet built (designed and agreed, ready to implement)
- `_find_characteristic` has no retry limit — self-heals via watchdog restart only
- Three kiosk script instances may occasionally run — resolves on reboot
- `anirudh.mp3` is 53MB in git (38-minute mashup) — may need git-lfs later
- ALSA card numbers change on reboot — ALWAYS use card name "Device", never "card 0"
- `udev RUN+=` cannot call systemctl directly — must use `systemd-run --no-block`
- `DISPLAY=:0` must be explicitly exported in SSH sessions before using xdotool
