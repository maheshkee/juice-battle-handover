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
echo "[1/5] Installing Python dependencies..."
pip install flask flask-socketio --break-system-packages

# ── 2. Data directory ──────────────────────────────────────────────────────
echo "[2/5] Creating data directory..."
mkdir -p "$DATA_DIR"
# ── 2b. Socket.IO JS client (served locally - offline-safe) ────────────────
echo "      Downloading socket.io.js (v4.6.1)..."
mkdir -p "$HUB_DIR/static"
curl -L -o "$HUB_DIR/static/socket.io.js" \
    "https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.6.1/socket.io.min.js"
echo "      socket.io.js: $(du -sh "$HUB_DIR/static/socket.io.js" | cut -f1)"

# ── 3. Systemd service files ───────────────────────────────────────────────
echo "[3/5] Installing systemd services..."
sudo cp "$HUB_DIR/juice-ble-scanner.service" /etc/systemd/system/
sudo cp "$HUB_DIR/juice-battle.service"      /etc/systemd/system/

# ── 4. Enable on boot ──────────────────────────────────────────────────────
echo "[4/5] Enabling services (will auto-start on every boot)..."
sudo systemctl daemon-reload
sudo systemctl enable juice-ble-scanner.service
sudo systemctl enable juice-battle.service

# ── 5. Start now ───────────────────────────────────────────────────────────
echo "[5/5] Starting services..."
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
