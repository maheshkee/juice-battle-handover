# Technical Learnings — Audio Pipeline, ALSA, udev, Kiosk, xdotool
Date: 2026-08-06 | Juice Battle S018 | Hardware: Arduino UNO Q (AQ3)

---

## 1. Linux Audio Stack — How it actually works

### The layers (bottom to top)

```
Hardware (USB audio chip — Generalplus 1b3f:2008)
      ↓
Kernel ALSA driver (snd_usb_audio module)
      ↓
ALSA (Advanced Linux Sound Architecture) — kernel-level audio routing
      ↓
~/.asoundrc — user-level ALSA config (which device is "default")
      ↓
SDL2 (pygame uses SDL2 as its audio backend)
      ↓
pygame.mixer — Python API
      ↓
Your application code
```

**Why this matters:** A problem at any layer blocks all layers above it.
When we had no sound, we debugged layer by layer — `aplay -l` (ALSA),
`speaker-test` (SDL+ALSA), `python3 -c "import pygame..."` (pygame).

### ALSA card numbers vs card names

```bash
aplay -l
# Output:
# card 0: Device [USB Audio Device]    ← USB adapter
# card 1: ArduinoImolaHPH [Arduino-Imola-HPH-LOUT]  ← onboard (silent)
```

**Critical:** Card numbers are assigned at boot based on enumeration order.
If the USB adapter is plugged in after the onboard audio initialises,
it gets card 1. If it's plugged in first, it gets card 0.
**Card numbers are NOT stable across reboots.**

**Solution:** Use card NAME in `~/.asoundrc`:

```
pcm.!default {
    type hw
    card "Device"       ← matches "USB Audio Device" — stable forever
}
ctl.!default {
    type hw
    card "Device"
}
```

The name `"Device"` comes from the bracketed part of `aplay -l` output:
`card 0: Device [USB Audio Device]` → name is `Device`.

### Checking available mixer controls

```bash
amixer -c 0 scontrols     # list controls on card 0
amixer -c 0 sset Speaker 90%   # set speaker volume
```

### Testing audio at each layer

```bash
# Layer 1: ALSA direct
aplay /usr/share/sounds/alsa/Front_Left.wav

# Layer 2: speaker-test (generates test tones)
speaker-test -c 2 -t wav

# Layer 3: pygame
python3 -c "
import pygame
pygame.mixer.init()
pygame.mixer.music.load('path/to/file.mp3')
pygame.mixer.music.play()
import time; time.sleep(5)
"
```

---

## 2. pygame Audio Architecture — mixer.music vs mixer.Sound

### Two completely different systems

**`pygame.mixer.music`** — single streaming channel
- Designed for long files (music, background tracks)
- Only ONE file can play at a time
- `music.load()` STOPS whatever is currently playing and loads new file
- `music.play(loops=-1)` loops forever
- Volume: `music.set_volume(0.0–1.0)`

**`pygame.mixer.Sound`** — multi-channel sample system
- Designed for short clips (sound effects, voice)
- Multiple sounds can play simultaneously on different channels
- `Sound(path).play()` returns a Channel object
- Does NOT interrupt `mixer.music`
- Check completion: `channel.get_busy()`

### The bug we hit

```python
# WRONG — kills background music every time a glass is scored
def _play_file(self, path):
    pygame.mixer.music.load(path)   # ← hijacks the flute channel!
    pygame.mixer.music.play()

# CORRECT — plays on its own channel, flute continues
def _play_file(self, path):
    sound = pygame.mixer.Sound(path)
    channel = sound.play()
    while channel.get_busy():
        pygame.time.wait(100)
```

### Architecture rule for Juice Battle

```
mixer.music  →  RESERVED for AmbientPlayer (flute loop only)
mixer.Sound  →  ALL other sounds (glass, fanfare, announcements)
```

### Volume ducking pattern

```python
# Duck music during announcement
pygame.mixer.music.set_volume(0.05)   # near-silent

# Play announcement on Sound channel
sound = pygame.mixer.Sound(ann_path)
sound.play()
time.sleep(sound.get_length() + 0.3)  # wait for it to finish

# Restore
pygame.mixer.music.set_volume(0.60)
```

---

## 3. gTTS — Google Text-to-Speech

### What it is

gTTS is a Python library that calls Google Translate's TTS endpoint
(the same engine that reads text in Google Translate) and downloads
the audio as MP3 bytes.

```
Your text string
      ↓
gTTS(text, lang='en', tld='co.in')
      ↓
HTTP POST → translate.google.co.in/translate_tts
      ↓
Google synthesises speech → returns MP3 bytes
      ↓
tts.save("file.mp3") writes to disk
```

**Requires internet at generation time. Runtime playback is offline.**

### The `tld` parameter controls the voice

- `tld='com'` → American English female voice
- `tld='co.in'` → Indian English female voice (what we used)
- `tld='co.uk'` → British English female voice

### Why it sounds robotic

gTTS uses Google Translate's basic TTS — no prosody control, no pitch
variation, no emphasis. It's flat monotone. The "advanced version" uses
Google Cloud TTS WaveNet or ElevenLabs — those sound nearly human but
require API keys and cost money.

### Generation command

```python
from gtts import gTTS
tts = gTTS(text="Namaste! Welcome to Juice Battle.", lang='en', tld='co.in')
tts.save("ann_namaste.mp3")
```

### Setup: generate all announcements

```bash
pip install gtts --break-system-packages
python3 << 'EOF'
from gtts import gTTS
import os
SOUNDS_DIR = "hub/static/sounds"
announcements = {
    "ann_namaste": "Namaste! Welcome to Juice Battle, by Dharanova.",
    # ... etc
}
for filename, text in announcements.items():
    gTTS(text=text, lang='en', tld='co.in').save(f"{SOUNDS_DIR}/{filename}.mp3")
EOF
```

---

## 4. udev — What it is and how we used it

### What is udev?

udev is the **userspace device manager** for Linux. When hardware events
happen (USB plugged in, USB removed, network adapter appears), the kernel
fires a **uevent**. udev receives these events and runs rules in response.

```
USB device plugged in
      ↓
Kernel detects device → creates /dev/snd/pcmC0D0p etc.
      ↓
Kernel fires uevent: "ACTION=add, SUBSYSTEM=sound, ..."
      ↓
udev daemon (/lib/systemd/systemd-udevd) receives it
      ↓
Scans /etc/udev/rules.d/*.rules top to bottom
      ↓
Matching rule → executes RUN+= command
```

**udev is NOT a daemon you start/stop.** It's part of systemd and runs
permanently. It's always listening.

### Rule syntax

```
ACTION=="add",              ← when device is connected (not removed)
SUBSYSTEM=="sound",         ← when ALSA sound device appears (not raw USB)
ATTRS{idVendor}=="1b3f",    ← Generalplus Technology USB audio
ATTRS{idProduct}=="2008",   ← specific product ID
RUN+="/usr/bin/systemd-run --no-block /bin/systemctl restart juice-battle.service"
```

### ATTR vs ATTRS — critical difference

- `ATTR{x}` — checks attribute on the EXACT device node being matched
- `ATTRS{x}` — searches UP the device tree to parent devices

`idVendor` and `idProduct` live on the **parent USB device**, not on the
ALSA sound interface. So you MUST use `ATTRS` (plural).

Using `ATTR` (singular) → rule never matches → nothing happens.

### SUBSYSTEM=="usb" vs SUBSYSTEM=="sound"

- `usb` fires when the raw USB device appears — too early, ALSA not ready yet
- `sound` fires when the ALSA sound card is registered — correct timing

### Why udev can't call systemctl directly

udev runs in a **restricted execution environment**:
- No D-Bus access
- No systemd session
- Minimal environment variables
- `systemctl` requires D-Bus to communicate with systemd

**Solution:** `systemd-run --no-block /bin/systemctl restart service`

`systemd-run` creates a transient systemd unit that runs outside udev's
restricted context and CAN communicate with systemd.

### Finding vendor/product IDs

```bash
lsusb | grep -i audio
# Bus 001 Device 004: ID 1b3f:2008 Generalplus Technology Inc. USB Audio Device
#                        ^^^^ ^^^^
#                        vendor product
```

### Reload rules after changing them

```bash
sudo udevadm control --reload-rules
# No restart needed — udev picks up changes immediately
```

### Debugging — monitor udev events in real time

```bash
udevadm monitor --udev --subsystem-match=usb
# Then plug/unplug device — events appear in real time
```

### Verify your rule matches a device

```bash
udevadm info /sys/bus/usb/devices/1-1.1 | grep -E "idVendor|idProduct|SUBSYSTEM"
```

---

## 5. XFCE, X11, DISPLAY, and the Headless Session Problem

### What is XFCE?

XFCE is a **desktop environment** — it manages windows, the taskbar,
desktop background, and autostart applications on the MPU's Linux.
The Arduino UNO Q MPU runs Debian + XFCE as the graphical layer.

### What is X11?

X11 (X Window System) is the protocol that graphical applications use
to draw windows and receive input on Linux. It's a client-server model:

```
Application (e.g. Chromium)  ←→  X Server (:0)  ←→  Display hardware
```

The X server manages the actual screen. Applications connect to it via
a socket, identified by the `DISPLAY` environment variable.

### DISPLAY=:0

`:0` means "the first X display" — your Arzopa screen connected via
wireless HDMI. Any application that wants to draw to the screen or
interact with windows MUST have `DISPLAY=:0` set.

### The headless session problem

When you SSH into the board:
```bash
ssh arduino@AQ3
echo $DISPLAY
# (empty)
```

Your SSH session has NO display. It's headless. Any tool that interacts
with the graphical session (xdotool, chromium, etc.) will fail silently
or with cryptic errors.

**Solution:** Explicitly set `DISPLAY=:0`:

```bash
DISPLAY=:0 xdotool search --name "Juice Battle"
```

Or export it for the session:
```bash
export DISPLAY=:0
```

**Why the kiosk script works:** It's launched by XFCE autostart, which
runs in the graphical session with `DISPLAY=:0` already set. But subshells
spawned inside the script may or may not inherit it — always export explicitly.

---

## 6. xdotool — Programmatic Window Control

### What is xdotool?

xdotool is a command-line tool that simulates keyboard/mouse input and
queries windows on an X11 display. It's how we force Chromium kiosk to
reload without a physical keyboard.

### Key commands used in Juice Battle

```bash
# Find a window by title
DISPLAY=:0 xdotool search --name "Juice Battle"
# Returns: window ID (e.g. 20971524)

# Get window title
DISPLAY=:0 xdotool getwindowname 20971524

# Send Ctrl+R to a specific window (reload)
DISPLAY=:0 xdotool key --window 20971524 ctrl+r

# Bring a window to front
DISPLAY=:0 xdotool windowactivate 20971524

# Combined: find and reload in one command
DISPLAY=:0 xdotool search --name "Juice Battle" | head -1 | \
  xargs -I{} xdotool key --window {} ctrl+r
```

### Why `window.location.reload()` didn't work in kiosk mode

Chromium's `--kiosk` flag restricts certain JavaScript APIs for security.
`window.location.reload()` triggered by Socket.IO reconnect events was
being ignored or rate-limited by Chromium's kiosk security model.

**Solution:** Bypass the browser entirely — send the reload keystroke
from outside using xdotool. The kiosk can't block a real keyboard event.

---

## 7. The /tmp/jb_reload Flag Mechanism

### The problem

We need: "when service restarts, reload the kiosk browser page."

Two actors involved:
1. `main.py` (Python, runs as systemd service) — knows when service started
2. `juice_battle_kiosk.sh` (bash, runs in XFCE session) — has access to xdotool

They can't call each other directly. Need a communication channel.

### Solution: filesystem flag file

```
main.py starts
      ↓
touch /tmp/jb_reload       ← atomic, instant, no dependencies
      ↓
focus-keeper loop (every 3s) in kiosk script:
  if [ -f /tmp/jb_reload ]; then
      rm -f /tmp/jb_reload             ← consume the flag (idempotent)
      WID=$(xdotool search --name "Juice Battle" | head -1)
      xdotool key --window "$WID" ctrl+r   ← reload kiosk
  fi
```

**Why a file?** Simplest possible IPC (inter-process communication).
No sockets, no D-Bus, no pipes. Just a file that either exists or doesn't.
The kiosk loop polls every 3 seconds — max 3 second delay on reload.

---

## 8. USB Audio Hotplug — Full Recovery Chain

### What happens when USB audio adapter is unplugged

```
USB unplugged
      ↓
Kernel removes /dev/snd/pcmC0D0p
      ↓
pygame still holds old file descriptor → dead handle → silence
      ↓
pygame does NOT auto-recover — it has no hotplug awareness
```

### The full recovery chain we built

```
USB adapter replugged
      ↓
Kernel creates new ALSA device
      ↓
udev detects SUBSYSTEM=="sound" ADD event for 1b3f:2008
      ↓
udev rule fires: systemd-run → systemctl restart juice-battle
      ↓
juice-battle stops (TimeoutStopSec=5 — fast kill)
      ↓
juice-battle starts → main.py → pygame.mixer.init() → fresh handle
      ↓
main.py touches /tmp/jb_reload
      ↓
Kiosk focus-keeper sees flag → xdotool ctrl+r → Chromium reloads
      ↓
Everything working within ~8 seconds of replug
```

### The systemd service environment vars that make it work

```ini
Environment=SDL_AUDIODRIVER=alsa
Environment=AUDIODEV=hw:Device
```

`hw:Device` tells SDL/pygame to use the ALSA device named "Device"
regardless of card number. Without this, pygame would default to
whatever ALSA thinks is the default — which depends on `~/.asoundrc`
being correct, which depends on card names being stable.

---

## 9. Key Commands Reference

```bash
# Audio diagnostics
aplay -l                          # list ALSA devices
amixer -c 0 scontrols             # list mixer controls on card 0
amixer -c 0 sset Speaker 90%      # set volume
speaker-test -c 2 -t wav          # test audio output

# udev
sudo udevadm control --reload-rules          # reload rules without restart
udevadm monitor --udev --subsystem-match=usb # watch USB events live
udevadm info /sys/bus/usb/devices/1-1.1      # inspect device attributes
cat /etc/udev/rules.d/99-juice-battle-audio.rules  # view our rule

# xdotool (always needs DISPLAY=:0 from SSH)
DISPLAY=:0 xdotool search --name "Juice Battle"
DISPLAY=:0 xdotool key --window <WID> ctrl+r
DISPLAY=:0 xdotool windowactivate <WID>

# pygame audio test
python3 -c "
import pygame; pygame.mixer.init()
pygame.mixer.music.load('hub/static/sounds/flute.mp3')
pygame.mixer.music.set_volume(0.8); pygame.mixer.music.play()
import time; time.sleep(6)
"

# Service management
sudo systemctl restart juice-battle
sudo systemctl status juice-battle --no-pager
journalctl -u juice-battle -f | grep -E "AmbientPlayer|SoundPlayer|announcement"

# Manual kiosk reload (from SSH)
DISPLAY=:0 xdotool search --name "Juice Battle" | head -1 | \
  xargs -I{} xdotool key --window {} ctrl+r
```
