#!/bin/bash
# setup.sh — one-time setup for Juice Battle on a fresh Arduino UNO Q board.
# Run once after cloning the repo. Safe to re-run (socket.io.js skipped if present).
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HUB_DIR="$SCRIPT_DIR/hub"

echo "=== Juice Battle Setup ==="
echo "    Project root: $SCRIPT_DIR"
echo ""

# ── STEP 1: System packages ────────────────────────────────────────────────────
echo "[1/11] Installing apt packages (unclutter, xdotool, python3-pip)..."
sudo apt-get install -y unclutter xdotool python3-pip

# ── STEP 2: Python dependencies ────────────────────────────────────────────────
echo "[2/11] Installing Python dependencies..."
pip install flask flask-socketio qrcode pillow dbus-python pygame --break-system-packages

# ── STEP 3: Audio output (.asoundrc dmix route + USB adapter) ──────────────────
# All sound assets are committed under hub/static/sounds/, so audio needs only:
#   1. pygame (installed above)
#   2. ~/.asoundrc routing the ALSA "default" PCM through dmix  (this step)
#   3. juice-battle.service with NO AUDIODEV override           (in the unit file)
#   4. the Generalplus USB adapter physically plugged in
# Raw hw: access without dmix causes a continuous ALSA underrun storm — see
# hub/asoundrc header and CLAUDE.md (root-caused 2026-08-20).
echo "[3/11] Configuring audio output (.asoundrc dmix route)..."
ASOUNDRC="$HOME/.asoundrc"
CANONICAL="$HUB_DIR/asoundrc"
if [ ! -f "$CANONICAL" ]; then
    echo "      ERROR: $CANONICAL missing — repo checkout incomplete. Skipping audio config."
elif [ -f "$ASOUNDRC" ] && cmp -s "$CANONICAL" "$ASOUNDRC"; then
    echo "      ~/.asoundrc already matches canonical dmix config — skipping"
else
    if [ -f "$ASOUNDRC" ]; then
        BACKUP="$ASOUNDRC.pre-juicebattle.$(date +%Y%m%d-%H%M%S)"
        cp "$ASOUNDRC" "$BACKUP"
        echo "      existing ~/.asoundrc backed up → $BACKUP"
    fi
    cp "$CANONICAL" "$ASOUNDRC"
    echo "      ~/.asoundrc installed (USB card \"Device\" via dmix)"
fi
if aplay -l 2>/dev/null | grep -qi "USB Audio"; then
    echo "      USB audio adapter detected OK"
else
    echo "      WARNING: USB audio adapter not detected by ALSA — plug it in and"
    echo "               re-run setup, or audio will be silent at runtime."
fi

# ── STEP 4: Data directory ─────────────────────────────────────────────────────
echo "[4/11] Creating data directory..."
mkdir -p "$HUB_DIR/data"

# ── STEP 5: socket.io.js client (offline-safe) ────────────────────────────────
echo "[5/11] Checking socket.io.js v4.6.1..."
SOCKETIO_JS="$HUB_DIR/static/socket.io.js"
if [ -f "$SOCKETIO_JS" ]; then
    echo "      Already present — skipping download."
else
    mkdir -p "$HUB_DIR/static"
    echo "      Downloading from cdnjs..."
    curl -L -o "$SOCKETIO_JS" \
        "https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.6.1/socket.io.min.js"
    echo "      socket.io.js: $(du -sh "$SOCKETIO_JS" | cut -f1)"
fi

# ── STEP 6: Systemd service files ─────────────────────────────────────────────
echo "[6/11] Installing and enabling systemd services..."
sudo cp "$HUB_DIR/juice-ble-scanner.service" /etc/systemd/system/
sudo cp "$HUB_DIR/juice-battle.service"      /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable juice-ble-scanner.service juice-battle.service

# ── STEP 7: Kiosk launch script ───────────────────────────────────────────────
echo "[7/11] Installing kiosk script..."
cp "$SCRIPT_DIR/hub/juice_battle_kiosk.sh" /home/arduino/juice_battle_kiosk.sh
chmod +x /home/arduino/juice_battle_kiosk.sh

# ── STEP 8: Autostart desktop entries ─────────────────────────────────────────
echo "[8/11] Installing autostart desktop files..."
mkdir -p /home/arduino/.config/autostart

cat > /home/arduino/.config/autostart/juice_battle_kiosk.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Juice Battle Kiosk
Exec=/home/arduino/juice_battle_kiosk.sh
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF

cat > /home/arduino/.config/autostart/blueman.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=blueman-applet
Exec=/bin/true
Hidden=true
X-GNOME-Autostart-enabled=false
EOF

# ── STEP 9: XFCE kiosk hardening ──────────────────────────────────────────────
echo "[9/11] Applying XFCE kiosk hardening..."
xfconf-query -c xfce4-desktop -p /backdrop/screen0/monitor0/color-style -s 0 -t int 2>/dev/null || true
xfconf-query -c xfce4-desktop -p /backdrop/screen0/monitor0/image-show -s false -t bool 2>/dev/null || true
xfconf-query -c xfce4-notifyd -p /do-not-disturb -s true 2>/dev/null || true

# ── STEP 10: Start services ───────────────────────────────────────────────────
echo "[10/11] Starting services..."
sudo systemctl start juice-ble-scanner.service
echo "      Waiting 4s for BLE scanner to acquire GATT connection..."
sleep 4
sudo systemctl start juice-battle.service

# ── STEP 11: Summary ──────────────────────────────────────────────────────────
echo ""
echo "[11/11] Setup complete."
echo ""
echo "  Dashboard:              http://$(hostname).local:5000/v6"
echo ""
echo "  Service status:"
echo "    systemctl status juice-ble-scanner"
echo "    systemctl status juice-battle"
echo ""
echo "  Logs:"
echo "    journalctl -u juice-ble-scanner -f"
echo "    journalctl -u juice-battle -f"
echo ""
echo "  Developer reset (wipe DB and restart):"
echo "    sudo systemctl stop juice-battle"
echo "    rm -f $HUB_DIR/data/jb.db"
echo "    sudo systemctl start juice-battle"
echo ""
echo "  Deploy update:          ./deploy.sh"
echo ""
