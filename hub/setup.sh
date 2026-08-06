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

# Set USB audio adapter as default ALSA device (card 1).
# Why card 1? Card 0 is the onboard (silent/HDMI) device.
# The USB adapter enumerates as card 1 when plugged into the hub.
ASOUNDRC="$HOME/.asoundrc"
if grep -q "defaults.pcm.card 1" "$ASOUNDRC" 2>/dev/null; then
    echo "      .asoundrc already configured — skipping"
else
    cat >> "$ASOUNDRC" << 'ASOUNDRC_EOF'
# Juice Battle: route default audio to USB adapter (card 1)
defaults.pcm.card 1
defaults.ctl.card 1
ASOUNDRC_EOF
    echo "      .asoundrc written: USB audio set as default"
fi

# Verify the USB audio device is visible to ALSA
if aplay -l 2>/dev/null | grep -q "USB Audio"; then
    echo "      USB audio adapter detected OK"
else
    echo "      WARNING: USB audio adapter not detected by ALSA"
    echo "               Plug in the USB adapter and re-run setup, or"
    echo "               audio will be silently disabled at runtime."
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
