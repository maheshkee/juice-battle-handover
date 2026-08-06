# Juice Battle — BLE Transport Debug Postmortem

**Date:** 2026-08-05 / 2026-08-06  
**Session:** S018  
**Status:** RESOLVED ✓  
**Time to resolve:** ~4 hours across two sessions

---

## 1. The Symptom

Both ESP32-C3 nodes (JB-0 and JB-1) powered on. Dashboard showed:

- JB-0: connecting, heartbeats flowing, scores counting ✓  
- JB-1: invisible. Never appeared in `bluetoothctl devices`. Scanner logs showed only `node=0`. Dashboard stuck showing "JAR 1 RECONNECTING" or "BOTH NODES CONNECTED" falsely.

This happened **three times** across development sessions. Each time it looked different:
- Sometimes JB-1 never connected at all
- Sometimes it connected once then vanished
- Sometimes a power cycle of JB-1 fixed it temporarily

---

## 2. The Full Stack — Layer by Layer

```
ESP32-C3 (JB-0, JB-1)
    ↓ BLE GATT notifications (NimBLE, advertising as "JB-0" / "JB-1")
BlueZ on AQ3 (Linux BLE stack)
    ↓ D-Bus InterfacesAdded / PropertiesChanged signals
ble_scanner.py  (systemd: juice-ble-scanner.service)
    ↓ TCP NDJSON on 0.0.0.0:7001
transport.py    (TCP client, connects to 127.0.0.1:7001)
    ↓ callbacks
game.py         (game logic, state machine)
    ↓ Socket.IO
dashboard.py    (Flask, /v2 and /v3 routes)
    ↓ browser WebSocket
Chromium kiosk  (Arzopa 28" display)
```

**Key files:**
- `hub/ble_scanner.py` — BLE GATT central, BlueZ D-Bus, TCP server
- `hub/transport.py` — TCP client
- `hub/config.py` — ports, hosts
- `hub/game.py` — game logic
- `firmware/node/comms.cpp` — NimBLE GATT server on ESP32-C3
- `firmware/node/juicebattle.ino` — main loop, MAC-based node identity

---

## 3. Bugs Found and Fixed (in order of discovery)

### Bug 1 — Wrong Transport Host (Docker leftover)
**File:** `hub/config.py`  
**Line:** `TRANSPORT_CLIENT_HOST = "172.17.0.1"`

**What happened:** transport.py was trying to connect to `172.17.0.1:7001` — the Docker bridge gateway. This was left over from when the app ran inside a Docker container. Running natively on Debian, nothing listens on `172.17.0.1`. So transport connected, got nothing, timed out every 10 seconds, reconnected, repeated forever.

**How found:** `ss -tlnp | grep 7001` showed scanner listening on `0.0.0.0:7001`. `ss -tlnp | grep 5001` showed nothing. Transport logs showed `timed out` every 10s.

**Fix:**
```bash
sed -i 's/TRANSPORT_CLIENT_HOST = "172.17.0.1"/TRANSPORT_CLIENT_HOST = "127.0.0.1"/' hub/config.py
```

**Verification:** Transport logs changed from `timed out` to `TCP client connected: ('127.0.0.1', XXXXX)`.

---

### Bug 2 — Hardware Watchdog Causing JB-0 BLE Drops
**File:** `firmware/node/juicebattle.ino`  
**Lines:** 158–171 (watchdog init + loop reset)

**What happened:** A 10-second hardware watchdog was added in commit `31a3551`. JB-0 had this firmware flashed. Something in the BLE stack or ADS1232 read was blocking `loop()` for >10s during reconnection storms, causing the watchdog to fire → chip reboots → re-advertises → scanner reconnects → repeat. JB-0 was dropping every ~14 seconds reliably.

**How found:** Scanner logs showed `NODE_CONNECTED → NODE_DISCONNECTED` in milliseconds, then `le-connection-abort-by-local`. Timing of drops (~14s after connect) matched the 10s watchdog + connection overhead. JB-1 was stable — it had older firmware without the watchdog.

**Fix:** Removed watchdog entirely from firmware:
```bash
sed -i 's/#include <esp_task_wdt.h>//' firmware/node/juicebattle.ino
sed -i '/WHY: hardware watchdog/,/esp_task_wdt_add(NULL)/d' firmware/node/juicebattle.ino
sed -i '/esp_task_wdt_reset/d' firmware/node/juicebattle.ino
```

Reflashed both nodes via Arduino IDE (SCP firmware to laptop, flash from there).

**Note for future:** If watchdog is re-added, must ensure `esp_task_wdt_reset()` is called inside any blocking BLE or ADS1232 operation, not just at the top of `loop()`.

---

### Bug 3 — JB-1 Never Discovered (THE MAIN BUG)
**File:** `hub/ble_scanner.py`  
**Function:** `_check_known_devices()` + startup call at line 471

**What happened:** `_check_known_devices()` ran **once at startup** via `GLib.idle_add`. It checked BlueZ's device registry for cached JB-* devices. If JB-1 wasn't in BlueZ cache at that exact moment (because it booted slightly later, or its cache entry was stale), it was never picked up.

The scanner then waited for `InterfacesAdded` — the D-Bus signal BlueZ fires when it **first discovers** a new device. But `InterfacesAdded` only fires on **first discovery**. If BlueZ had seen JB-1 in a previous session and cached it (even stale), it would NOT fire `InterfacesAdded` again. So the scanner waited forever. JB-1 never connected.

**The deceptive part:** `bluetoothctl devices` didn't show JB-1 at all — meaning BlueZ had no cache entry. But `InterfacesAdded` also never fired. So JB-1 was advertising into a void.

**Timeline of discovery:**
1. Observed JB-1 absent from scanner logs while JB-0 present
2. `bluetoothctl devices | grep JB` → only JB-0
3. `sudo hcitool lescan --duplicates` → nothing (misleading — BlueZ owns HCI, hcitool can't scan simultaneously)
4. Powered off JB-0, powered on JB-1 only → JB-1 appeared immediately in scanner logs
5. Powered both on → JB-0 connects, JB-1 never connects
6. Checked serial monitor: JB-1 boots correctly, `[BOOT] node_id=1 resolved from MAC`, GATT init, advertising — firmware fine
7. Root cause: race condition — JB-1 appears in BlueZ cache **after** the one-shot `_check_known_devices` ran, and `InterfacesAdded` doesn't re-fire for it

**Fix:**
```python
# In _check_known_devices(), change return value:
return True  # repeat when called via timeout_add (was: return False)

# Add periodic poll after startup idle_add (line 471):
GLib.idle_add(_check_known_devices)
GLib.timeout_add_seconds(10, _check_known_devices)  # periodic poll every 10s
```

**Applied via:**
```bash
sed -i 's/    return False  # GLib.idle_add: False = do not repeat/    return True  # repeat when called via timeout_add/' hub/ble_scanner.py
sed -i '/GLib.idle_add(_check_known_devices)/a\    GLib.timeout_add_seconds(10, _check_known_devices)' hub/ble_scanner.py
```

**Result:** Both nodes connect within 10 seconds of startup regardless of boot order. `_check_known_devices` polls BlueZ cache every 10s and connects to any JB-* device that appears.

---

## 4. Node Identity — How It Works (Important)

Node identity is **NOT compiled in**. Same `.ino` flashes to both nodes.

At boot, each node reads its BT MAC from ESP efuse (immutable, survives any flash):
```cpp
esp_read_mac(mac, ESP_MAC_BT);
```

Looks it up in `NODE_MAC_TABLE` in `juicebattle.ino`:
```cpp
{ {0x70, 0xAF, 0x09, 0x32, 0xF3, 0xC2}, 0 },  // JB-0
{ {0x10, 0x00, 0x3B, 0xCD, 0x63, 0x32}, 1 },  // JB-1
```

If MAC not found → FATAL halt, prints unknown MAC to serial. **This is how to add a new node:** flash, observe serial output for `[BOOT] FATAL: unknown MAC XX:XX:XX:XX:XX:XX`, add to table, reflash.

---

## 5. Transport Timeout Issue (Known, Not Yet Fixed)

**File:** `hub/transport.py` line 44  
`timeout=10` on TCP socket connect.

When game.py starts before any node is connected, scanner has no data to send. Transport sits idle for 10s, times out, reconnects. This loop repeats until a node connects and data flows. It recovers automatically due to the ring buffer in ble_scanner.py (200 events buffered, flushed to new client on connect).

**Not critical** — system self-heals. But creates noisy logs at startup.

**Future fix:** Add a keepalive ping from scanner to transport every 5s when no node data is flowing. Or increase timeout to 60s.

---

## 6. Diagnostic Commands — Quick Reference

```bash
# Is the scanner running and healthy?
sudo systemctl status juice-ble-scanner

# Live scanner log — what BLE events are happening?
sudo journalctl -u juice-ble-scanner -f

# Live game log — is scoring working?
sudo journalctl -u juice-battle -f

# What devices does BlueZ know about?
bluetoothctl devices | grep JB

# Is BlueZ actively scanning?
bluetoothctl show | grep -i "discover\|scanning"

# Is the TCP transport port open?
ss -tlnp | grep 7001

# Force BlueZ to scan (if JB-* not appearing):
bluetoothctl scan on &
sleep 15 && bluetoothctl devices | grep JB

# Check transport host config:
grep "TRANSPORT_CLIENT_HOST" hub/config.py  # must be 127.0.0.1

# Check for watchdog in firmware (should be empty after fix):
grep -n "wdt\|watchdog\|esp_task" firmware/node/juicebattle.ino
```

---

## 7. If JB-1 Disappears Again — Checklist

Work through these in order:

1. **Is JB-1 physically powered on?** LED should be on.
2. **Does JB-1 boot correctly?** Check serial monitor first lines — must show `[BOOT] node_id=1 resolved from MAC`. If FATAL → MAC not in table.
3. **Does BlueZ see JB-1?** `bluetoothctl devices | grep JB`. If not → wait 10s (periodic poll will catch it). If still not after 30s → step 4.
4. **Force rescan:** `bluetoothctl scan on` → wait 15s → `bluetoothctl devices | grep JB`.
5. **Restart scanner:** `sudo systemctl restart juice-ble-scanner`. The 10s periodic poll will pick it up.
6. **Check if JB-1 is connected to another device** (e.g., laptop Bluetooth). NimBLE only allows one central connection. Disconnect from laptop.
7. **Power cycle JB-1.** On reboot it re-advertises aggressively for ~30s.

---

## 8. Architecture Lessons Learned

- **`GLib.idle_add` is one-shot.** Never rely on it for ongoing discovery. Use `GLib.timeout_add_seconds` for anything that needs to repeat.
- **`InterfacesAdded` is unreliable for already-seen devices.** BlueZ only fires it on first discovery. Periodic cache polling is mandatory.
- **`hcitool lescan` conflicts with BlueZ.** If BlueZ owns the adapter, hcitool returns nothing — this is NOT evidence of a radio problem.
- **Docker config leaks.** `172.17.0.1` as transport host only works inside Docker. Running natively on Debian, must be `127.0.0.1`.
- **Hardware watchdog in BLE firmware is dangerous** if `loop()` has any blocking path. Either feed the watchdog inside every blocking call or don't use it.
- **Same firmware flashes to all nodes** — identity from MAC table, not compile-time constant.
- **Ring buffer in scanner** (200 events) means transport reconnect doesn't lose data. Scanner buffers events and flushes to new client on connect.

---

## 9. Commits Made This Session

```
fix(ble): periodic _check_known_devices poll every 10s — fixes JB-1 not discovered when both nodes on simultaneously
fix(firmware): remove hardware watchdog — was causing JB-0 BLE drops every ~10s  
fix: transport host 127.0.0.1, splash→v3, dashboard v3 added
feat(v3): atmospheric dashboard with cause panel, welcome band, India IoT map
```

---

*Document generated: 2026-08-06 | Project: Juice Battle | Board: Arduino UNO Q (AQ3)*
