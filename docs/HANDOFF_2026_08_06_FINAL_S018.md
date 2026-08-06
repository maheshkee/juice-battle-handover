# Juice Battle — Handoff S017 → S018
Date: 2026-08-06
Session: S018

---

## Current system state (verified at session close)

- JB-0 (Lemon Warrior, node=0): connected, scoring ✓
- JB-1 (Melon Crusher, node=1): connected, scoring ✓
- Services running + boot-enabled: juice-ble-scanner, juice-battle
- Active dashboard: http://AQ3:5000/v3 (kiosk on LCD via wireless HDMI)
- Speaker: working — bansuri flute loops continuously, TTS announcements every 30s
- Kiosk auto-reload: working — service restart triggers Ctrl+R to Chromium via xdotool
- Git branch: juice-battle-main (push.default = upstream, always use `git push`)
- All changes committed and pushed this session ✓

---

## What was built this session (S018)

### 1. Speaker audio pipeline (end-to-end)
- USB audio adapter detected as ALSA card — `~/.asoundrc` written using card NAME
  `"Device"` not card number (numbers change on reboot, names are stable)
- `pygame` installed system-wide (`pip install pygame --break-system-packages`)
- `SoundPlayer` class added to `hub/game.py`:
  - Uses `pygame.mixer.Sound` (NOT `mixer.music`) for game sounds
  - Non-blocking daemon thread per sound
  - Triggers: `glass.mp3` on scored pour, `fanfare.mp3` on game_over
- `AmbientPlayer` class in new `hub/ambient.py`:
  - `pygame.mixer.music` reserved EXCLUSIVELY for looping bansuri flute
  - `pygame.mixer.Sound` used for TTS announcements (separate channel)
  - Music ducks to 0.05 volume during announcements, restores to 0.60 after
  - Announcement interval: 30 seconds, round-robin through 7 announcements
- `hub/main.py`: `AmbientPlayer().start()` wired before `dashboard.start()`

### 2. TTS announcements (pre-generated, saved to disk)
- Tool: `gTTS` (Google TTS via `translate.google.co.in`) — Indian English female voice
- Generated once at setup, saved as MP3s in `hub/static/sounds/`
- 7 announcements: ann_namaste, ann_grounded, ann_come_taste, ann_every_drop,
  ann_enthusiasts, ann_real_sensors, ann_every_dot
- `flute.mp3` downloaded from Pixabay (free license, kalsstockmedia):
  "Free Soul Indian Bansuri Music for Festivities and Travel Vlogs"

### 3. USB audio hotplug recovery (udev rule)
- File: `/etc/udev/rules.d/99-juice-battle-audio.rules`
- Triggers on `SUBSYSTEM=="sound"`, `ATTRS{idVendor}=="1b3f"`, `ATTRS{idProduct}=="2008"`
- Uses `systemd-run --no-block` to restart juice-battle (udev cannot call systemctl directly)
- `juice-battle.service` updated: `TimeoutStopSec=5`, `SDL_AUDIODRIVER=alsa`,
  `AUDIODEV=hw:Device` (stable device name, not card number)

### 4. Kiosk auto-reload on service restart
- `hub/main.py`: `touch /tmp/jb_reload` at startup
- `juice_battle_kiosk.sh`: focus-keeper loop checks `/tmp/jb_reload` every 3s,
  sends `xdotool key ctrl+r` to Chromium window, deletes file
- `export DISPLAY=:0` added to focus-keeper subshell (required for xdotool)
- v3 JS: `socket.io.on('reconnect')` + `wasDisconnected` flag as browser fallback
- Flask `/v3` route: cache-control headers added (`no-store, no-cache`)

### 5. Bug fixes
- Streak badge: `&#x1F525;` → `🔥` (textContent does not parse HTML entities)
- `SoundPlayer` switched from `mixer.music` to `mixer.Sound` so game sounds
  no longer hijack the background music channel
- `setup.sh`: updated to 6 steps, includes pygame, gtts, announcement generation,
  udev rule install, card-name-based `.asoundrc`

---

## Working contract (carry forward always)

- **Claude Chat = Brain**: architecture, diagnosis, research, decisions, prompts for CLI
- **Claude CLI = Hands**: ALL file edits, ALL code, ALL bash execution on board
- **Never write code in chat** unless it is a one-liner diagnostic — even then, flag it
- `/` route: NEVER touch. Stable fallback. All development on `/v2` and `/v3`
- `git push` always works because `push.default = upstream` is set permanently
- Mahesh's style: fast, direct, short feedback ("yes", "ok", "good")
  Make autonomous design decisions when asked. Don't present options, make a call.
- Philosophy: WHY before HOW. First principles always. Nothing "just works".

---

## Pending work (next session priorities)

### P1 — Pause/resume audio from terminal
Need a curl endpoint or simple command to pause/resume the ambient audio
(music + announcements) without restarting the service. Use case: operator
wants silence during a speech or important moment at the stall.
Design: `POST /ambient/pause` and `POST /ambient/resume` routes in dashboard.py,
delegating to `AmbientPlayer.pause()` and `AmbientPlayer.resume()`.

### P2 — Auto round system (replaces manual game_over button)
Current: game_over triggered manually via curl or web UI button (not accessible
from LCD kiosk without mouse/keyboard).
Proposed: every N glasses (configurable, default 10) = 1 round. System auto:
  1. Detects total glasses hit threshold
  2. Announces winner of round via TTS
  3. Displays "ROUND X WINNER: [NAME]" overlay on dashboard
  4. Auto-resets after countdown (10 seconds)
  5. Begins Round X+1
This makes the game fully autonomous — no operator intervention needed.
Design touches: game.py (round counter), ambient.py (round announcement TTS),
dashboard.py v3 (round overlay UI).

### P3 — Developer tools documentation
Add `docs/DEVTOOLS.md` with all curl commands (game_over, reset, adjust, state).
Already drafted in this session — just needs committing.

---

## Developer terminal cheat sheet

```bash
# Game over
curl -s -X POST http://localhost:5000/game_over | python3 -m json.tool

# Reset jar 0 (Lemon Warrior)
curl -s -X POST http://localhost:5000/reset/0 | python3 -m json.tool

# Reset jar 1 (Melon Crusher)
curl -s -X POST http://localhost:5000/reset/1 | python3 -m json.tool

# Increase count — jar 0
curl -s -X POST "http://localhost:5000/adjust/0/1" | python3 -m json.tool

# Decrease count — jar 0
curl -s -X POST "http://localhost:5000/adjust/0/-1" | python3 -m json.tool

# Increase count — jar 1
curl -s -X POST "http://localhost:5000/adjust/1/1" | python3 -m json.tool

# Force Chromium kiosk reload (if needed manually)
DISPLAY=:0 xdotool search --name "Juice Battle" | head -1 | xargs -I{} xdotool key --window {} ctrl+r

# Watch live logs
journalctl -u juice-battle -f | grep -E "AmbientPlayer|SoundPlayer|POUR_SETTLED|announcement"

# Restart service (triggers kiosk auto-reload within 3-5s)
sudo systemctl restart juice-battle

# Check audio device
aplay -l

# Set master volume (USB adapter)
amixer -c 0 sset Speaker 90%
```

---

## File map (what does what)

```
hub/
  game.py          — SoundPlayer + Game state machine. glass.mp3/fanfare.mp3 triggers here
  ambient.py       — AmbientPlayer. Flute loop + TTS announcements. Completely independent
  main.py          — Orchestrator. Wires everything. touches /tmp/jb_reload on start
  dashboard.py     — Flask + Socket.IO. All routes. v3 is active dashboard
  ble_scanner.py   — BlueZ D-Bus BLE scanner. Programmatic StartDiscovery ✓
  storage.py       — SQLite. Persists pours, sessions, all-time counter
  config.py        — All tunable constants
  static/sounds/   — All audio: glass.mp3, pour.mp3, fanfare.mp3, cheer.mp3,
                     flute.mp3, ann_*.mp3 (7 TTS announcements)
  juice-battle.service     — systemd unit. SDL_AUDIODRIVER=alsa, AUDIODEV=hw:Device,
                             TimeoutStopSec=5
  juice_battle_kiosk.sh   — XFCE autostart kiosk launcher. Focus-keeper + reload trigger

/etc/udev/rules.d/
  99-juice-battle-audio.rules  — USB audio hotplug → auto-restart juice-battle

~/.asoundrc              — Routes ALSA default to card "Device" (USB adapter by name)
```

---

## Known issues / watch-outs

- Three kiosk script instances were running simultaneously (from multiple autostart
  triggers). On next reboot this resolves itself — only one autostart entry exists.
- `flute.mp3` is committed to git (7MB) — acceptable for now, may need git-lfs later
- `adjust_glass_count` does NOT trigger glass.mp3 — by design (developer tool, not real pour)
- ALSA card numbers change on reboot — ALWAYS use card name `"Device"`, never `card 0`
- udev `RUN+=` cannot call `systemctl` directly — must use `systemd-run --no-block`
- `DISPLAY=:0` must be explicitly exported in any subshell that uses xdotool
- pygame `mixer.music` = single global channel for long tracks (flute)
  pygame `mixer.Sound` = per-sample channels for short clips (game sounds, announcements)
  NEVER mix these up — mixer.music.load() kills whatever is playing on that channel
