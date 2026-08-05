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
echo "[1/10] Installing apt packages (unclutter, xdotool)..."
sudo apt-get install -y unclutter xdotool

# ── STEP 2: Python dependencies ────────────────────────────────────────────────
echo "[2/10] Installing Python dependencies..."
pip install flask flask-socketio qrcode pillow dbus-python --break-system-packages

# ── STEP 3: Data directory ─────────────────────────────────────────────────────
echo "[3/10] Creating data directory..."
mkdir -p "$HUB_DIR/data"

# ── STEP 4: socket.io.js client (offline-safe) ────────────────────────────────
echo "[4/10] Checking socket.io.js v4.6.1..."
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

# ── STEP 5: Systemd service files ─────────────────────────────────────────────
echo "[5/10] Installing and enabling systemd services..."
sudo cp "$HUB_DIR/juice-ble-scanner.service" /etc/systemd/system/
sudo cp "$HUB_DIR/juice-battle.service"      /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable juice-ble-scanner.service juice-battle.service

# ── STEP 6: Kiosk launch script ───────────────────────────────────────────────
echo "[6/10] Installing kiosk script..."
cp "$SCRIPT_DIR/juice_battle_kiosk.sh" /home/arduino/juice_battle_kiosk.sh
chmod +x /home/arduino/juice_battle_kiosk.sh

# ── STEP 7: Autostart desktop entries ─────────────────────────────────────────
echo "[7/10] Installing autostart desktop files..."
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

# ── STEP 8: XFCE kiosk hardening ──────────────────────────────────────────────
echo "[8/10] Applying XFCE kiosk hardening..."
xfconf-query -c xfce4-desktop -p /backdrop/screen0/monitor0/color-style -s 0 -t int 2>/dev/null || true
xfconf-query -c xfce4-desktop -p /backdrop/screen0/monitor0/image-show -s false -t bool 2>/dev/null || true
xfconf-query -c xfce4-notifyd -p /do-not-disturb -s true 2>/dev/null || true

# ── STEP 9: Start services ────────────────────────────────────────────────────
echo "[9/10] Starting services..."
sudo systemctl start juice-ble-scanner.service
echo "      Waiting 4s for BLE scanner to acquire GATT connection..."
sleep 4
sudo systemctl start juice-battle.service

# ── STEP 10: Summary ──────────────────────────────────────────────────────────
echo ""
echo "[10/10] Setup complete."
echo ""
echo "  Dashboard:              http://AQ3.local:5000/v2"
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
