#!/bin/bash

# Force black desktop immediately — hides the boot wait gap
xfconf-query -c xfce4-desktop -p /backdrop/screen0/monitor0/color-style -s 0 -t int 2>/dev/null || true
xfconf-query -c xfce4-desktop -p /backdrop/screen0/monitor0/image-show -s false -t bool 2>/dev/null || true
xfconf-query -c xfce4-desktop -p /backdrop/screen0/monitor1/color-style -s 0 -t int 2>/dev/null || true
xfconf-query -c xfce4-desktop -p /backdrop/screen0/monitor1/image-show -s false -t bool 2>/dev/null || true

# Silence desktop notifications — prevents popups stealing focus
xfconf-query -c xfce4-notifyd -p /do-not-disturb -s true 2>/dev/null || true

# Kill any focus-stealing applets before Chromium launches
pkill blueman-applet 2>/dev/null || true
pkill blueman-tray   2>/dev/null || true

until curl -s http://localhost:5000 > /dev/null; do sleep 1; done

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
  "http://localhost:5000/static/splash.html" &

# Focus keeper: re-raise kiosk window within 3s if anything steals focus
(
  export DISPLAY=:0
  sleep 10
  while true; do
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
