#!/bin/bash
# deploy.sh - redeploy Juice Battle after code changes to hub/ Python files.
# Does NOT touch the BLE scanner service - BLE connection stays live.
# Does NOT touch firmware - use Arduino IDE for .ino changes.
set -e

echo "=== Juice Battle Redeploy ==="

echo "[1/2] Restarting main app (game + dashboard)..."
sudo systemctl restart juice-battle.service

echo "[2/2] Waiting for startup..."
sleep 2

echo ""
systemctl status juice-battle.service --no-pager -l

echo ""
echo "=== Tailing logs - Ctrl+C to exit ==="
journalctl -u juice-battle.service -f
