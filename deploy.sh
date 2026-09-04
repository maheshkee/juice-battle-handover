#!/bin/bash
# deploy.sh — developer redeploy script for Juice Battle.
# Run after any code change to push it live without a full setup.
#
# Usage:
#   ./deploy.sh          — restart hub (juice-battle) only
#   ./deploy.sh --ble    — restart hub + BLE scanner
#   ./deploy.sh -b       — same as --ble
#
# Also re-syncs the installed kiosk script (~/juice_battle_kiosk.sh) from the
# repo — takes effect on the next kiosk relaunch (reboot / session restart).
#
# Does NOT touch firmware — use Arduino IDE for .ino changes.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Juice Battle Deploy ==="
echo ""

# ── STEP 1: Git pull ───────────────────────────────────────────────────────────
echo "[1/5] Pulling latest code..."
cd "$SCRIPT_DIR"
git pull origin main || echo "      WARNING: git pull failed — deploying local code as-is."

# ── STEP 2: Re-sync systemd unit files, then restart hub ──────────────────────
# WHY: a plain restart does NOT pick up changes to the unit files in the repo
# (e.g. dropping AUDIODEV). Without this re-copy the installed unit silently
# drifts from the repo. cmp avoids a needless daemon-reload when nothing changed.
echo "[2/5] Syncing service units + restarting main app..."
for unit in juice-battle.service juice-ble-scanner.service; do
    if ! cmp -s "$SCRIPT_DIR/hub/$unit" "/etc/systemd/system/$unit"; then
        sudo cp "$SCRIPT_DIR/hub/$unit" "/etc/systemd/system/$unit"
        echo "      updated /etc/systemd/system/$unit"
        NEED_RELOAD=1
    fi
done
if [ -n "$NEED_RELOAD" ]; then sudo systemctl daemon-reload; fi
sudo systemctl restart juice-battle.service
echo "      Main app restarted."

# ── STEP 3: Re-sync the installed kiosk script ───────────────────────────────
# WHY: setup.sh copies hub/juice_battle_kiosk.sh to ~/juice_battle_kiosk.sh, but
# deploy.sh used to skip it — a git pull with a kiosk-script change (e.g. the
# screen-blank/DPMS fix) never reached the running board. Applies on next kiosk
# relaunch (reboot or session restart), not live.
echo "[3/6] Syncing kiosk script..."
if ! cmp -s "$SCRIPT_DIR/hub/juice_battle_kiosk.sh" "$HOME/juice_battle_kiosk.sh"; then
    cp "$SCRIPT_DIR/hub/juice_battle_kiosk.sh" "$HOME/juice_battle_kiosk.sh"
    chmod +x "$HOME/juice_battle_kiosk.sh"
    echo "      updated ~/juice_battle_kiosk.sh (reboot or restart the kiosk to apply)"
else
    echo "      already current."
fi

# ── STEP 4: Optional BLE restart ──────────────────────────────────────────────
echo "[4/6] BLE scanner..."
if [ "$1" = "--ble" ] || [ "$1" = "-b" ]; then
    sudo systemctl restart juice-ble-scanner.service
    echo "      BLE scanner restarted."
else
    echo "      BLE scanner untouched (pass --ble to restart it too)."
fi

# ── STEP 5: Wait and show status ──────────────────────────────────────────────
echo "[5/6] Waiting 3s for startup..."
sleep 3
systemctl status juice-battle.service --no-pager | head -8

# ── STEP 6: Tail logs ─────────────────────────────────────────────────────────
echo ""
echo "[6/6] Tailing logs — Ctrl+C to exit."
journalctl -u juice-battle.service -f
