#!/bin/bash

# Force black desktop immediately — hides the boot wait gap
xfconf-query -c xfce4-desktop -p /backdrop/screen0/monitor0/color-style -s 0 -t int 2>/dev/null || true
xfconf-query -c xfce4-desktop -p /backdrop/screen0/monitor0/image-show -s false -t bool 2>/dev/null || true
xfconf-query -c xfce4-desktop -p /backdrop/screen0/monitor1/color-style -s 0 -t int 2>/dev/null || true
xfconf-query -c xfce4-desktop -p /backdrop/screen0/monitor1/image-show -s false -t bool 2>/dev/null || true

# Silence desktop notifications — prevents popups stealing focus
xfconf-query -c xfce4-notifyd -p /do-not-disturb -s true 2>/dev/null || true

# Kill screen blanking / DPMS — a kiosk display must never power down or blank.
# Without this the panel goes black after the X default idle timeout (~10 min)
# even though Chromium is still running the dashboard underneath.
export DISPLAY=:0
xset s off        2>/dev/null || true
xset s noblank    2>/dev/null || true
xset -dpms        2>/dev/null || true
xset dpms 0 0 0   2>/dev/null || true

# Kill any focus-stealing applets before Chromium launches
pkill blueman-applet 2>/dev/null || true
pkill blueman-tray   2>/dev/null || true

# Dashboard port is owned by hub/config.py — read it at runtime, never hardcode it here.
JB_HUB="$HOME/ArduinoApps/juice_battle/hub"
DASHBOARD_PORT="$(cd "$JB_HUB" && python3 -c 'from config import DASHBOARD_PORT; print(DASHBOARD_PORT)')"
if [ -z "$DASHBOARD_PORT" ]; then
  echo "kiosk: could not read DASHBOARD_PORT from $JB_HUB/config.py" >&2
  exit 1
fi
DASHBOARD_URL="http://localhost:${DASHBOARD_PORT}"

until curl -s "$DASHBOARD_URL" > /dev/null; do sleep 1; done

pkill chromium || true

unclutter -idle 0 &

chromium \
  --kiosk \
  --start-fullscreen \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-restore-session-state \
  --no-first-run \
  --disable-translate \
  --disable-features=TranslateUI \
  --disable-notifications \
  --disable-popup-blocking \
  --no-default-browser-check \
  --disable-component-update \
  --check-for-update-interval=31536000 \
  "${DASHBOARD_URL}/static/splash.html" &

# Focus keeper: re-raise kiosk window within 3s if anything steals focus
(
  export DISPLAY=:0
  sleep 10
  while true; do
    # Re-assert every cycle — something in the session re-enables DPMS after the
    # one-shot xset calls at script start (observed: screen still blanked after
    # a clean reboot despite `xset -dpms`). At 3s cadence the blank timer, which
    # is minutes, can never elapse.
    xset s off        2>/dev/null || true
    xset s noblank    2>/dev/null || true
    xset -dpms        2>/dev/null || true
    WID=$(xdotool search --name "Juice Battle" 2>/dev/null | head -1)
    if [ -f /tmp/jb_reload ]; then
      rm -f /tmp/jb_reload
      if [ -n "$WID" ]; then
        xdotool key --window "$WID" ctrl+r
      fi
    fi
    if [ -n "$WID" ]; then
      ACTIVE=$(xdotool getactivewindow 2>/dev/null)
      if [ "$ACTIVE" != "$WID" ]; then
        xdotool windowactivate "$WID" 2>/dev/null
      fi
    fi
    sleep 3
  done
) &

wait
