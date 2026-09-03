#!/bin/bash
# setup.sh — one-time setup for Juice Battle on a fresh Arduino UNO Q board.
# Run once after cloning the repo. Safe to re-run (idempotent throughout).
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HUB_DIR="$SCRIPT_DIR/hub"

echo "=== Juice Battle Setup ==="
echo "    Project root: $SCRIPT_DIR"
echo ""

# ── STEP 1: System packages ────────────────────────────────────────────────────
# unclutter/xdotool: kiosk. python3-gi + python3-dbus + bluez: hub/ble_scanner.py
# talks to BlueZ over D-Bus. chromium: kiosk browser. curl: kiosk wait-loop +
# pendrive udev hook.
echo "[1/13] Installing apt packages..."
sudo apt-get install -y \
    unclutter xdotool python3-pip \
    python3-gi python3-dbus bluez \
    chromium curl

# ── STEP 2: Python dependencies ────────────────────────────────────────────────
echo "[2/13] Installing Python dependencies (requirements.txt)..."
pip install -r "$SCRIPT_DIR/requirements.txt" --break-system-packages

# ── STEP 3: Audio output (.asoundrc dmix route + USB adapter) ──────────────────
# All sound assets are committed under hub/static/sounds/, so audio needs only:
#   1. pygame (installed above)
#   2. ~/.asoundrc routing the ALSA "default" PCM through dmix  (this step)
#   3. juice-battle.service with NO AUDIODEV override           (in the unit file)
#   4. the Generalplus USB adapter physically plugged in
# Raw hw: access without dmix causes a continuous ALSA underrun storm — see
# hub/asoundrc header and CLAUDE.md (root-caused 2026-08-20).
echo "[3/13] Configuring audio output (.asoundrc dmix route)..."
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
echo "[4/13] Creating data directory..."
mkdir -p "$HUB_DIR/data"

# ── STEP 5: socket.io.js client (offline-safe) ────────────────────────────────
echo "[5/13] Checking socket.io.js v4.6.1..."
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
echo "[6/13] Installing and enabling systemd services..."
sudo cp "$HUB_DIR/juice-ble-scanner.service" /etc/systemd/system/
sudo cp "$HUB_DIR/juice-battle.service"      /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable juice-ble-scanner.service juice-battle.service

# ── STEP 7: udev hot-plug rules ──────────────────────────────────────────────
# 99-juice-battle-audio: replugging the USB audio adapter restarts juice-battle.
# 99-juice-pendrive: a USB stick auto-mounts and the ambient player rescans it
# for a music playlist. Field-proven on AQ3 — versions in hub/udev/ are canonical.
echo "[7/13] Installing udev hot-plug rules..."
sudo cp "$HUB_DIR/udev/99-juice-battle-audio.rules" /etc/udev/rules.d/
sudo cp "$HUB_DIR/udev/99-juice-pendrive.rules"     /etc/udev/rules.d/
sudo udevadm control --reload-rules

# ── STEP 8: Kiosk auth (autologin + passwordless service control) ─────────────
# WHY: the board must boot demo-ready with no password prompt anywhere.
#  - LightDM drop-in  → 'arduino' logs straight into the desktop.
#  - sudoers.d/juice-battle → deploy.sh + udev rules restart services unattended.
#  - App Lab autostart suppressed → it no longer pops over the kiosk (and its
#    keyring/login prompt no longer appears).
echo "[8/13] Configuring kiosk auth (autologin + passwordless service control)..."
sudo mkdir -p /etc/lightdm/lightdm.conf.d
sudo cp "$HUB_DIR/lightdm/50-juice-battle-autologin.conf" /etc/lightdm/lightdm.conf.d/

if sudo /usr/sbin/visudo -cf "$HUB_DIR/sudoers/juice-battle" >/dev/null; then
    sudo install -m 0440 -o root -g root "$HUB_DIR/sudoers/juice-battle" /etc/sudoers.d/juice-battle
    echo "      /etc/sudoers.d/juice-battle installed"
else
    echo "      ERROR: hub/sudoers/juice-battle failed visudo check — NOT installed."
fi

mkdir -p /home/arduino/.config/autostart
cat > /home/arduino/.config/autostart/ArduinoAppLab.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Arduino App Lab
Exec=/bin/true
Hidden=true
X-GNOME-Autostart-enabled=false
EOF

# ── STEP 9: Kiosk launch script ──────────────────────────────────────────────
echo "[9/13] Installing kiosk script..."
cp "$SCRIPT_DIR/hub/juice_battle_kiosk.sh" /home/arduino/juice_battle_kiosk.sh
chmod +x /home/arduino/juice_battle_kiosk.sh

# ── STEP 10: Autostart desktop entries ───────────────────────────────────────
echo "[10/13] Installing autostart desktop files..."
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

# ── STEP 11: XFCE kiosk hardening ────────────────────────────────────────────
echo "[11/13] Applying XFCE kiosk hardening..."
xfconf-query -c xfce4-desktop -p /backdrop/screen0/monitor0/color-style -s 0 -t int 2>/dev/null || true
xfconf-query -c xfce4-desktop -p /backdrop/screen0/monitor0/image-show -s false -t bool 2>/dev/null || true
xfconf-query -c xfce4-notifyd -p /do-not-disturb -s true 2>/dev/null || true

# ── STEP 12: (Re)start services ──────────────────────────────────────────────
# restart, not start: on a re-run the old instance is already up with stale
# config (unit file / .asoundrc just changed) and `start` would be a no-op.
echo "[12/13] (Re)starting services..."
sudo systemctl restart juice-ble-scanner.service
echo "      Waiting 4s for BLE scanner to acquire GATT connection..."
sleep 4
sudo systemctl restart juice-battle.service

# ── STEP 13: Summary ────────────────────────────────────────────────────────
echo ""
echo "[13/13] Setup complete."
echo ""
echo "  Dashboard:              http://$(hostname).local:5000/v6"
echo ""
echo "  Autologin + kiosk take effect on next reboot. To apply now without a"
echo "  reboot:  sudo systemctl restart lightdm   (closes the desktop session)"
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
