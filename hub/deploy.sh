#!/usr/bin/env bash
# Juice Battle - deploy / restart
# Run after any code change: bash hub/deploy.sh
set -e

echo "=== Juice Battle: deploy ==="

echo "[1/2] Restarting BLE scanner service..."
sudo systemctl restart juice-ble-scanner
sleep 2
sudo systemctl status juice-ble-scanner --no-pager | head -6

echo "[2/2] Restarting App Lab app..."
# arduino-applab restart juice_battle  # uncomment when App Lab app exists
echo "(App Lab restart skipped - no app yet in S007)"

echo ""
echo "=== Deploy complete ==="
echo "Monitor scanner: journalctl -u jb-ble-scanner -f"
echo "Debug stream:    nc localhost 7001"
