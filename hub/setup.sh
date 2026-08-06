#!/bin/bash
# setup.sh - one-time setup for Juice Battle on a new board
# Run once after cloning the repo onto a fresh Arduino UNO Q.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HUB_DIR="$SCRIPT_DIR/hub"
DATA_DIR="$HUB_DIR/data"

echo "=== Juice Battle Setup ==="
echo "    Project root: $SCRIPT_DIR"
echo ""

# ── 1. Python dependencies ─────────────────────────────────────────────────
echo "[1/6] Installing Python dependencies..."
pip install flask flask-socketio --break-system-packages

# ── 2. Audio output (USB adapter + pygame) ────────────────────────────────
echo "[2/6] Configuring audio output..."
pip install pygame --break-system-packages

# Write .asoundrc using card NAME "Device" (matches USB Audio Device).
# Names are stable across reboots; card numbers are not.
ASOUNDRC="$HOME/.asoundrc"
if grep -q 'card "Device"' "$ASOUNDRC" 2>/dev/null; then
    echo "      .asoundrc already configured — skipping"
else
    cat > "$ASOUNDRC" << 'ASOUNDRC_EOF'
# Route default audio to USB adapter.
# Using card NAME not number — card numbers change on reboot depending
# on enumeration order. Names are stable.
defaults.pcm.card 0
defaults.ctl.card 0

pcm.!default {
    type hw
    card "Device"
}
ctl.!default {
    type hw
    card "Device"
}
ASOUNDRC_EOF
    echo "      .asoundrc written: USB audio (card Device) set as default"
fi

# Verify the USB audio device is visible to ALSA
if aplay -l 2>/dev/null | grep -q "USB Audio"; then
    echo "      USB audio adapter detected OK"
else
    echo "      WARNING: USB audio adapter not detected by ALSA"
    echo "               Plug in the USB adapter and re-run setup, or"
    echo "               audio will be silently disabled at runtime."
fi

# Install gTTS for announcement generation
pip install gtts --break-system-packages

# Generate announcement MP3s (skip if already exist)
echo "      Generating voice announcements (requires internet)..."
python3 << 'PYEOF'
import os, sys
try:
    from gtts import gTTS
except ImportError:
    print("      ERROR: gtts not installed — skipping announcements")
    sys.exit(0)

SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath("hub/setup.sh")), "hub", "static", "sounds")
os.makedirs(SOUNDS_DIR, exist_ok=True)

announcements = {
    "ann_namaste":      "Namaste! Welcome to Juice Battle, by Dharanova.",
    "ann_grounded":     "Dharanova. Grounded innovation, powering the future of IoT.",
    "ann_come_taste":   "Come, taste fresh juice and experience Dharanova's intelligent sensing technology. Every pour, measured in real time.",
    "ann_every_drop":   "Every drop measured. Every glass counted. This is IoT, made real.",
    "ann_enthusiasts":  "Dharanova welcomes all IoT enthusiasts. Step closer, and play Juice Battle!",
    "ann_real_sensors": "Real sensors. Real data. Real juice. Welcome to Juice Battle, by Dharanova.",
    "ann_every_dot":    "Every dot accounted for. Every connection matters. This is Dharanova.",
}

for filename, text in announcements.items():
    path = os.path.join(SOUNDS_DIR, f"{filename}.mp3")
    if os.path.exists(path):
        print(f"      ✓ {filename}.mp3 (exists, skipped)")
        continue
    try:
        gTTS(text=text, lang='en', tld='co.in').save(path)
        print(f"      ✓ {filename}.mp3 (generated)")
    except Exception as e:
        print(f"      WARNING: {filename}.mp3 failed: {e}")
PYEOF

# flute.mp3 must be manually downloaded (Pixabay requires browser)
FLUTE="$HUB_DIR/static/sounds/flute.mp3"
if [ ! -f "$FLUTE" ]; then
    echo ""
    echo "      ⚠️  flute.mp3 NOT found — background music will be silent."
    echo "      Download from Pixabay (free, no login required):"
    echo "      https://pixabay.com/music/india-free-soul-indian-bansuri-music-for-festivities-and-travel-vlogs-470121/"
    echo "      Save as flute.mp3 and copy to: $FLUTE"
    echo ""
else
    echo "      ✓ flute.mp3 found"
fi

# ── 3. Data directory ──────────────────────────────────────────────────────
echo "[3/6] Creating data directory..."
mkdir -p "$DATA_DIR"
# ── 2b. Socket.IO JS client (served locally - offline-safe) ────────────────
echo "      Downloading socket.io.js (v4.6.1)..."
mkdir -p "$HUB_DIR/static"
curl -L -o "$HUB_DIR/static/socket.io.js" \
    "https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.6.1/socket.io.min.js"
echo "      socket.io.js: $(du -sh "$HUB_DIR/static/socket.io.js" | cut -f1)"

# ── 4. Systemd service files ───────────────────────────────────────────────
echo "[4/6] Installing systemd services..."
sudo cp "$HUB_DIR/juice-ble-scanner.service" /etc/systemd/system/
sudo cp "$HUB_DIR/juice-battle.service"      /etc/systemd/system/

# ── 5. Enable on boot ──────────────────────────────────────────────────────
echo "[5/6] Enabling services (will auto-start on every boot)..."
sudo systemctl daemon-reload
sudo systemctl enable juice-ble-scanner.service
sudo systemctl enable juice-battle.service

# ── 5b. USB audio hotplug recovery (udev rule) ────────────────────────────
echo "[5b] Installing USB audio hotplug udev rule..."
sudo tee /etc/udev/rules.d/99-juice-battle-audio.rules > /dev/null << 'UDEV_EOF'
# Auto-restart juice-battle when Generalplus USB audio adapter is replugged.
# ATTRS (plural) searches parent USB device for idVendor/idProduct.
# SUBSYSTEM=="sound" fires when ALSA device appears — better timing than usb.
# systemd-run needed because udev context cannot call systemctl directly.
ACTION=="add", SUBSYSTEM=="sound", \
    ATTRS{idVendor}=="1b3f", ATTRS{idProduct}=="2008", \
    RUN+="/usr/bin/systemd-run --no-block /bin/systemctl restart juice-battle.service"
UDEV_EOF
sudo udevadm control --reload-rules
echo "      udev rule installed: USB audio replug will auto-restart juice-battle"

# ── 6. Start now ───────────────────────────────────────────────────────────
echo "[6/6] Starting services..."
sudo systemctl start juice-ble-scanner.service
echo "      Waiting 4s for BLE scanner to acquire GATT connection..."
sleep 4
sudo systemctl start juice-battle.service

echo ""
echo "=== Setup complete ==="
echo ""
echo "  Scoreboard:           http://$(hostname).local:5000"
echo "  BLE scanner status:   systemctl status juice-ble-scanner"
echo "  Main app status:      systemctl status juice-battle"
echo "  Main app logs:        journalctl -u juice-battle -f"
echo ""
echo "  Boot behaviour:       ENABLED (both services start automatically)"
echo "  To disable boot:      sudo systemctl disable juice-battle juice-ble-scanner"
echo ""
