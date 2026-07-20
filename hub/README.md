# Juice Battle - Hub Operations

## Architecture

```
ble_scanner.py  : systemd service on host Linux (NOT in Docker)
                  Connects to JB-0 / JB-1 via GATT
                  Publishes NDJSON events to TCP :7001

transport.py    : Docker-side consumer
                  Connects to TCP :7001, fires callbacks to game logic
```

## First time on a new board

```
cd ~/ArduinoApps/juice_battle
bash hub/setup.sh  # Installs: python3-dbus, systemd service, enables on boot
```

## After any code change

```
bash hub/deploy.sh  # Restarts: juice-ble-scanner service + App Lab app (when it exists)
```

## Monitoring

```
journalctl -u juice-ble-scanner -f     # live scanner logs
nc localhost 7001                       # raw NDJSON event stream
systemctl status juice-ble-scanner     # service health
```

## Key ports

```
TCP :7001  - NDJSON event stream (scanner → any consumer)
```

## BLE nodes

```
JB-0  dev_70_AF_09_32_F3_C2   (Node 0, confirmed working S007)
JB-1  (pending - second node, S012)
```

## Systemd service

```
Unit:     /etc/systemd/system/juice-ble-scanner.service
Restart:  always (auto-recovers from crashes and chip resets)
Boot:     enabled (starts automatically on power-on)
```

## Normal operation - what you should see

```
journalctl -u juice-ble-scanner shows:
  [HEARTBEAT] node=0 delta=0.0g sigma=4.0g seq=N  (every 2 seconds)

nc localhost 7001 shows:
  {"msg":"HEARTBEAT","node":0,"delta_g":0.0,"sigma_g":4.0,"seq":N}
```

## If something looks wrong

```
1. journalctl -u juice-ble-scanner -n 50    check for errors
2. systemctl status juice-ble-scanner        is it running?
3. nc localhost 7001                         is TCP open?
4. screen /dev/ttyUSB0 115200               node serial (USB connected)
```
