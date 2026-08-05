#!/bin/bash
# deploy.sh — developer redeploy script for Juice Battle.
# Run after any code change to push it live without a full setup.
#
# Usage:
#   ./deploy.sh          — restart hub (juice-battle) only
#   ./deploy.sh --ble    — restart hub + BLE scanner
#   ./deploy.sh -b       — same as --ble
#
# Does NOT touch firmware — use Arduino IDE for .ino changes.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Juice Battle Deploy ==="
echo ""

# ── STEP 1: Git pull ───────────────────────────────────────────────────────────
echo "[1/5] Pulling latest code..."
cd "$SCRIPT_DIR"
git pull origin juice-battle-main || echo "      WARNING: git pull failed — deploying local code as-is."

# ── STEP 2: Restart hub ────────────────────────────────────────────────────────
echo "[2/5] Restarting main app..."
sudo systemctl restart juice-battle.service
echo "      Main app restarted."

# ── STEP 3: Optional BLE restart ──────────────────────────────────────────────
echo "[3/5] BLE scanner..."
if [ "$1" = "--ble" ] || [ "$1" = "-b" ]; then
    sudo systemctl restart juice-ble-scanner.service
    echo "      BLE scanner restarted."
else
    echo "      BLE scanner untouched (pass --ble to restart it too)."
fi

# ── STEP 4: Wait and show status ──────────────────────────────────────────────
echo "[4/5] Waiting 3s for startup..."
sleep 3
systemctl status juice-battle.service --no-pager | head -8

# ── STEP 5: Tail logs ─────────────────────────────────────────────────────────
echo ""
echo "[5/5] Tailing logs — Ctrl+C to exit."
journalctl -u juice-battle.service -f
