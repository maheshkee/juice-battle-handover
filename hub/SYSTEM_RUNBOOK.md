# Juice Battle — System Operations Runbook
_Last updated: 2026-08-08 | Hardware: Arduino UNO Q (AQ3)_

## 1. System Inventory

### Hardware
| Component | Detail |
|---|---|
| Hub | Arduino UNO Q — hostname AQ3, IP 192.168.88.25 |
| Node 0 | JB-0 "Lemon Warrior" — ESP32-C3, MAC 70:AF:09:32:F3:C2 |
| Node 1 | JB-1 "Melon Crusher" — ESP32-C3, MAC 10:00:3B:CD:63:32 |
| Display | Arzopa 28" via wireless HDMI — Chromium kiosk |
| Audio | USB audio adapter (card name: Device) + speaker |
| Pendrive | USB pendrive — exFAT, auto-mounts to /media/arduino/pendrive |

### Key Paths
| What | Path |
|---|---|
| App root | ~/ArduinoApps/juice_battle/ |
| Hub code | ~/ArduinoApps/juice_battle/hub/ |
| Database | ~/ArduinoApps/juice_battle/hub/data/jb.db |
| Sounds | ~/ArduinoApps/juice_battle/hub/static/sounds/ |
| Config | ~/ArduinoApps/juice_battle/hub/config.py |
| This runbook | ~/ArduinoApps/juice_battle/hub/SYSTEM_RUNBOOK.md |

### Services
| Service | Purpose |
|---|---|
| juice-ble-scanner | BLE scanner — connects to JB-0 and JB-1 |
| juice-battle | Main app — Flask, game engine, audio, Socket.IO |

### Network
| What | Address |
|---|---|
| Dashboard (kiosk) | http://192.168.88.25:5000/v3 |
| Ops panel (phone) | http://192.168.88.25:5000/ops |
| State API | http://192.168.88.25:5000/state |

---

## 2. Configuration Reference

### config.py — key values
| Setting | Current Value | Notes |
|---|---|---|
| ROUND_SIZE | 2 | SET TO 10 BEFORE STALL GOES LIVE |
| MUSIC_VOLUME | 0.20 | Ambient music volume (0.0–1.0) |
| GLASS_VOLUME_G | 150 | Grams per glass |
| PYGAME_MIXER_BUFFER | 4096 | ALSA buffer — do not reduce |

### Audio rules (NEVER violate)
- `SDL_AUDIODRIVER=alsa` in systemd service — correct, keep it
- `AUDIODEV=hw:Device` must NEVER be in the systemd service — bypasses ALSA plug layer, causes constant underruns and silence
- ALSA card name `"Device"` in `~/.asoundrc` — never use card number (changes on reboot)
- After any manual `amixer` change: run `sudo alsactl store 0` to persist

### BLE rules (NEVER violate)
- JB-1 "not found" is ALWAYS a NimBLE ghost connection — never debug at BlueZ layer
- Fix order: power cycle node → wait 10s → `bluetoothctl devices | grep JB`
- If still missing: `sudo hciconfig hci0 down && sleep 2 && sudo hciconfig hci0 up`

### Pendrive rules
- Pendrive is hot-pluggable — plug or remove anytime
- Auto-mounts to `/media/arduino/pendrive` via udev rule
- Playlist reloads automatically within ~3 seconds of plug/unplug
- Format: exFAT. Any `.mp3` files in root of pendrive will be played (sorted alphabetically)
- If no pendrive: falls back to `varanasi.mp3` → `anirudh.mp3`

---

## 3. Startup Sequence

Run these steps IN ORDER every time the system is set up at a stall.

### Step 1 — Power on
Power on the Arduino UNO Q hub. Services start automatically.
The pendrive can be plugged in before OR after power-on — it auto-mounts.

### Step 2 — Verify services running
```bash
sudo systemctl status juice-ble-scanner juice-battle --no-pager | grep -E "Active|running|failed"
```
Expected: both show `active (running)`

If either shows failed:
```bash
sudo systemctl restart juice-ble-scanner && sleep 3 && sudo systemctl restart juice-battle
```

### Step 3 — Verify BLE nodes connected
```bash
bluetoothctl devices | grep JB
sudo journalctl -u juice-ble-scanner -n 5 --no-pager | grep -E "NODE_CONNECTED|HEARTBEAT"
```
Expected: JB-0 and JB-1 listed. HEARTBEAT lines for both nodes.

If a node is missing: power cycle that node (unplug 5s, replug). Wait 15s. Check again.

### Step 4 — Set audio volume
```bash
amixer -c 0 sset Speaker 90% unmute
sudo alsactl store 0
```

### Step 5 — Fresh session for the day
```bash
curl -s -X POST http://localhost:5000/new_session | python3 -m json.tool
curl -s -X POST http://localhost:5000/reset_rounds | python3 -m json.tool
curl -s -X POST http://localhost:5000/reset/0 | python3 -m json.tool
curl -s -X POST http://localhost:5000/reset/1 | python3 -m json.tool
```

### Step 6 — Verify audio playing
Listen for music from speaker. If silent:
```bash
sudo journalctl -u juice-battle -n 10 --no-pager | grep -iE "ambient|track|playing"
```
Expected: `now playing track 1/2: varanasi.mp3` (or pendrive tracks if plugged in)

### Step 7 — Verify kiosk display
Open http://192.168.88.25:5000/v3 on phone to confirm dashboard is live.
If kiosk screen shows error page: `DISPLAY=:0 xdotool key F5`

### Step 8 — Set ROUND_SIZE before going live
```bash
sed -i 's/ROUND_SIZE = 2/ROUND_SIZE = 10/' ~/ArduinoApps/juice_battle/hub/config.py
grep ROUND_SIZE ~/ArduinoApps/juice_battle/hub/config.py
sudo systemctl restart juice-battle
```

---

## 4. Subsystem Controls

### BLE Subsystem
```bash
# Status
sudo systemctl status juice-ble-scanner --no-pager

# Restart scanner only
sudo systemctl restart juice-ble-scanner

# Live scanner log
sudo journalctl -u juice-ble-scanner -f | grep -E "NODE_CONNECTED|HEARTBEAT|WATCHDOG|ERROR"

# Check which nodes are visible to BlueZ
bluetoothctl devices | grep JB

# Hard reset BLE adapter (last resort)
sudo hciconfig hci0 down && sleep 2 && sudo hciconfig hci0 up
```

### Audio Subsystem
```bash
# Check volume
amixer -c 0 sget Speaker

# Set volume to 90%
amixer -c 0 sset Speaker 90% unmute && sudo alsactl store 0

# Via ops API
curl -s -X POST http://localhost:5000/audio/volume \
  -H "Content-Type: application/json" -d '{"level":0.4}'
curl -s -X POST http://localhost:5000/audio/pause
curl -s -X POST http://localhost:5000/audio/resume
curl -s -X POST http://localhost:5000/audio/next
curl -s -X POST http://localhost:5000/audio/rescan_playlist

# Check what's playing
sudo journalctl -u juice-battle -n 20 --no-pager | grep -iE "track|playing|playlist"
```

### Game Subsystem
```bash
# Game state
curl -s http://localhost:5000/state | python3 -m json.tool

# Session controls
curl -s -X POST http://localhost:5000/new_session | python3 -m json.tool
curl -s -X POST http://localhost:5000/reset_rounds | python3 -m json.tool
curl -s -X POST http://localhost:5000/reset/0 | python3 -m json.tool
curl -s -X POST http://localhost:5000/reset/1 | python3 -m json.tool

# Round controls
curl -s -X POST http://localhost:5000/force_round_end | python3 -m json.tool
curl -s -X POST http://localhost:5000/set_round \
  -H "Content-Type: application/json" -d '{"round":1}'
```

### Visual Subsystem
```bash
# Reload kiosk display
DISPLAY=:0 xdotool key F5

# Check Chromium is running
pgrep -a chromium | head -3

# Kiosk script location
cat ~/juice_battle_kiosk.sh
```

### Database Subsystem
```bash
# Recent sessions
sqlite3 ~/ArduinoApps/juice_battle/hub/data/jb.db \
  "SELECT id, slug, total_glasses FROM sessions ORDER BY id DESC LIMIT 5;"

# Round results
sqlite3 ~/ArduinoApps/juice_battle/hub/data/jb.db \
  "SELECT * FROM round_results ORDER BY id DESC LIMIT 10;"

# All-time glasses
sqlite3 ~/ArduinoApps/juice_battle/hub/data/jb.db \
  "SELECT * FROM kv_store;"

# Reset DB for fresh stall day (DANGER — deletes all data)
# sudo systemctl stop juice-battle
# rm ~/ArduinoApps/juice_battle/hub/data/jb.db
# sudo systemctl start juice-battle
```

### Ops Panel
Open on phone: http://192.168.88.25:5000/ops
- Live status, glass counts, round controls
- Audio volume, pause, resume, next track
- Node resets, new session, game over

---

## 5. End-to-End Health Check

Run this sequence to verify the full pipeline is working.

```bash
# 1. Services running
sudo systemctl status juice-ble-scanner juice-battle --no-pager | grep Active

# 2. Both nodes connected and heartbeating
sudo journalctl -u juice-ble-scanner -n 10 --no-pager | grep HEARTBEAT

# 3. Game state healthy
curl -s http://localhost:5000/state | python3 -m json.tool

# 4. Audio confirmed
sudo journalctl -u juice-battle -n 20 --no-pager | grep -iE "track|playing"
```

### What green looks like
- Both services: `active (running)`
- `/state` response: `"ble_status": {"0": "connected", "1": "connected"}`
- `/state` response: `"running": true`
- Journal: `HEARTBEAT` lines for both node=0 and node=1
- Journal: `now playing track N/N: <trackname>.mp3`
- Speaker: music audible

### Pour test
Pour a small amount into jar 0. Within 2 seconds:
- Dashboard glass count for Lemon Warrior increments
- Pour sound plays
- `/state` shows updated `glass_count`

---

## 6. Fault Diagnosis & Known Fixes

### Node not found / not connecting
**Symptom:** bluetoothctl shows only one node, or HEARTBEAT missing for a node
**Root cause:** ALWAYS a NimBLE ghost connection on the node — never BlueZ
**Fix:**
1. Power cycle the node (unplug from USB 5 seconds, replug)
2. Wait 15 seconds
3. `bluetoothctl devices | grep JB` — should appear
4. If still missing: `sudo hciconfig hci0 down && sleep 2 && sudo hciconfig hci0 up`
5. `sudo systemctl restart juice-ble-scanner`
Never debug at the Python or BlueZ layer first.

### Audio silent
**Symptom:** No sound from speaker despite service running
**Check 1 — Volume:**
```bash
amixer -c 0 sget Speaker
amixer -c 0 sset Speaker 90% unmute && sudo alsactl store 0
```
**Check 2 — ALSA underruns (constant loop = wrong SDL config):**
```bash
sudo journalctl -u juice-battle -n 20 --no-pager | grep snd_pcm_recover
```
If underruns: check `/etc/systemd/system/juice-battle.service` — must NOT contain
`AUDIODEV=hw:Device`. If present: remove it, daemon-reload, restart.

**Check 3 — Is pygame actually playing:**
```bash
sudo journalctl -u juice-battle -n 50 --no-pager | grep -iE "track|playing|ambient"
```

### Service crash on startup
**Symptom:** juice-battle shows `failed`, restarts in loop
**Check:**
```bash
sudo journalctl -u juice-battle -n 20 --no-pager | grep -iE "error|Error|Traceback"
```
Common causes and fixes documented in git log.

### Pendrive music not playing
**Symptom:** Fallback tracks playing instead of pendrive tracks
**Check:**
```bash
mount | grep pendrive          # should show sda1 mounted
ls /media/arduino/pendrive/    # should show .mp3 files
curl -s -X POST http://localhost:5000/audio/rescan_playlist | python3 -m json.tool
```
If mount empty: `sudo mount -t exfat /dev/sda1 /media/arduino/pendrive`
Then rescan. If persists, check udev rule:
`cat /etc/udev/rules.d/99-juice-pendrive.rules`

### Display not showing / kiosk blank
```bash
DISPLAY=:0 xdotool key F5
pgrep chromium || bash ~/juice_battle_kiosk.sh &
```

---

## 7. Shutdown Sequence

```bash
# 1. Persist audio volume
sudo alsactl store 0

# 2. Stop services cleanly
sudo systemctl stop juice-battle
sleep 2
sudo systemctl stop juice-ble-scanner

# 3. Commit any config changes
cd ~/ArduinoApps/juice_battle
git status
git add -A && git commit -m "ops: end of day config snapshot" && git push

# 4. Safe to power off
sudo poweroff
```

---

## Developer Cheat Sheet

```bash
# Full restart sequence
sudo systemctl restart juice-ble-scanner && sleep 3 && sudo systemctl restart juice-battle

# Git (always push to juice-battle-main)
git push   # push.default=upstream set — always just git push

# View live logs
sudo journalctl -u juice-battle -f | grep -vE "snd_pcm|werkzeug"
sudo journalctl -u juice-ble-scanner -f | grep -E "NODE|HEARTBEAT|WATCHDOG"

# DB quick check
sqlite3 hub/data/jb.db "SELECT * FROM kv_store;"

# ROUND_SIZE — dev=2, production=10
grep ROUND_SIZE hub/config.py
```
