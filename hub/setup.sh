#!/usr/bin/env bash
# Juice Battle - one-time board setup
# Run once: bash hub/setup.sh
# Safe to re-run.
set -e

echo "=== Juice Battle: one-time hub setup ==="

echo "[1/4] Installing system BLE/D-Bus packages..."
sudo apt-get update -qq
sudo apt-get install -y python3-dbus python3-gi gir1.2-glib-2.0

echo "[2/4] Installing systemd service..."
sudo cp hub/juice-ble-scanner.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable juice-ble-scanner

echo "[3/4] Starting BLE scanner service..."
sudo systemctl start juice-ble-scanner
sleep 2
sudo systemctl status juice-ble-scanner --no-pager | head -10

echo "[4/4] Verifying TCP port..."
sleep 2
if nc -z localhost 7001 2>/dev/null; then
    echo "OK - TCP :7001 is open"
else
    echo "WARN - TCP :7001 not yet open (may need node advertising)"
fi

echo ""
echo "=== Setup complete ==="
echo "Monitor logs: journalctl -u jb-ble-scanner -f"
echo "Verify stream: nc localhost 7001"
