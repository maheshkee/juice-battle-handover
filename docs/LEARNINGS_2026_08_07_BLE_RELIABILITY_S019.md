# Technical Learnings — BLE Reliability, Firmware, Audio, Scanner
Date: 2026-08-07 | Juice Battle S019 | Hardware: Arduino UNO Q (AQ3)

---

## 1. The JB-1 Ghost Connection — Root Cause (Final Answer)

### What is a ghost connection?
NimBLE on ESP32-C3 maintains its own connection state machine. When a central
(AQ3/BlueZ) connects to JB-1, NimBLE transitions from ADVERTISING → CONNECTED.
If the central disappears WITHOUT a clean disconnect (power loss, crash, service
restart), NimBLE waits for the **supervision timeout** to detect the absence.
Until that timeout fires, NimBLE stays in CONNECTED state and **stops advertising**.
A device that is not advertising is invisible to BlueZ. It cannot be discovered,
connected, or communicated with.

### Why JB-0 was stable but JB-1 wasn't
Same firmware binary. Same hardware. The difference was **connection history**.
JB-0 happened to get clean disconnects more often (USB flash resets, etc).
JB-1 accumulated more unclean disconnects and hit the ghost state more frequently.
This is not a hardware difference — it will happen to JB-0 too under the same conditions.

### The supervision timeout — what it is and why it matters
```
BLE connection parameters include a "supervision timeout" — a timer that
the peripheral uses to detect central absence. If no packets are received
from the central for supervision_timeout seconds, NimBLE declares the
connection dead → calls onDisconnect() → restarts advertising.

Default BlueZ supervision timeout: ~42 seconds.
Our fix: 5 seconds (500 × 10ms units).

42s ghost → node invisible for up to 42s + reconnect time ≈ 60s dead gap
5s ghost  → node invisible for up to 5s + reconnect time  ≈ 15s dead gap
```

### The firmware API mistake — setConnectionParams vs updateConnParams
**Wrong (what we had first):**
```cpp
// In comms_init(), after NimBLEDevice::init():
NimBLEDevice::setConnectionParams(16, 32, 0, 500);
```
`NimBLEDevice::setConnectionParams` is a **central** API — it sets parameters
used when the ESP32 acts as the one initiating connections. JB-0 and JB-1 are
**peripherals** — they advertise and accept connections. On a peripheral this
call is a complete no-op. The supervision timeout was NEVER actually set.

**Correct (what works):**
```cpp
// In ServerCallbacks::onConnect():
void onConnect(NimBLEServer* pServer, NimBLEConnInfo& connInfo) override {
    // Negotiate 5s supervision timeout with the central at connection time.
    // WHY: if AQ3 vanishes without clean disconnect, NimBLE detects it
    // within 5s and calls onDisconnect → restarts advertising automatically.
    pServer->updateConnParams(connInfo.getConnHandle(), 16, 32, 0, 500);
}
```
`pServer->updateConnParams()` is the **peripheral** API — it sends a connection
parameter update request to the central at connection time. This negotiates
the supervision timeout correctly.

**Parameter meanings:**
- 16 = min connection interval (16 × 1.25ms = 20ms)
- 32 = max connection interval (32 × 1.25ms = 40ms)
- 0  = slave latency (no skipped connection events)
- 500 = supervision timeout (500 × 10ms = **5 seconds**)

### Current firmware status (2026-08-07)
- JB-1 (10:00:3B:CD:63:32): ✓ flashed with onConnect updateConnParams
- JB-0 (70:AF:09:32:F3:C2): ✓ flashed with onConnect updateConnParams
- Both nodes: supervision timeout 5s active

---

## 2. BLE Scanner — The Connect Storm Bug

### What happened
We added _connecting_nodes pre-claiming at call sites (before idle_add) to
prevent duplicate connect attempts from queuing up. The logic was:

```python
# At call site (e.g. _check_known_devices):
if name not in _connecting_nodes and name not in _active_connections:
    _connecting_nodes.add(name)          # ← pre-claim HERE
    GLib.idle_add(_connect, path, name)  # ← queue connect

# Inside _connect():
if node_name in _active_connections or node_name in _connecting_nodes:
    return False  # ← THIS now sees the pre-claim and exits immediately
_connecting_nodes.add(name)  # never reached
```

Result: _connect() always saw its own pre-claim and returned False immediately.
Neither JB-0 nor JB-1 connected. Scanner crashed on 30s watchdog in a tight loop.

### The fix
Remove _connecting_nodes from the guard INSIDE _connect(). The storm prevention
lives at call sites. _connect just checks _active_connections:

```python
# Inside _connect() — corrected:
if node_name in _active_connections:  # only check this
    return False
_connecting_nodes.add(node_name)  # claim it here as safety net
```

### Why GLib.idle_add causes storms
`GLib.idle_add(fn, *args)` queues a callback — it does NOT execute immediately.
Multiple callers can queue the same callback before any of them runs. When they
finally execute, the first one claims _connecting_nodes and the rest are blocked
— but all N were already queued. The fix is to check-and-claim synchronously
at the call site, before queuing.

---

## 3. BLE Scanner — InterfacesRemoved Handler

### The deadlock it prevents
When BlueZ completely evicts a device (not just disconnects — evicts), it fires
`InterfacesRemoved` on D-Bus. Without a handler:
- _active_connections still has the node marked as "connected"
- _find_characteristic keeps retrying every 3s forever
- The watchdog skips the node (it's "connected")
- Nothing ever reconnects the node
- System is permanently deadlocked

### The handler we added
```python
def _interfaces_removed(path, interfaces):
    if DEVICE_IFACE not in interfaces:
        return
    for name, dev_path in list(_active_connections.items()):
        if dev_path == path:
            # Clean up all state
            del _active_connections[name]
            _connecting_nodes.discard(name)
            # Remove signal receivers
            # Emit NODE_DISCONNECTED
            # Schedule reconnect in 5s
```

Registered in main() alongside InterfacesAdded:
```python
bus.add_signal_receiver(
    _interfaces_removed,
    dbus_interface=DBUS_OM,
    signal_name='InterfacesRemoved'
)
```

---

## 4. BLE Scanner — _find_characteristic Timing Issue

### What happens
After Connect() succeeds, BlueZ resolves GATT services asynchronously. Our
_find_characteristic() polls every 3s. Sometimes BlueZ takes 10-30s to fully
resolve services (especially if it has stale cached data). During this time:
```
"JB char not found for JB-1 yet - retrying in 3s"  ← appears every 3s
```
This is normal and expected — wait it out. If it persists beyond ~60s,
it indicates a firmware or BlueZ cache problem.

### When bluetoothctl manually connecting helps
Running `bluetoothctl connect <MAC>` and `list-attributes` manually triggers
BlueZ's GATT resolver. Once services are resolved, our scanner's next poll
finds the characteristic immediately. This is a debugging tool, not a fix.

### The watchdog interaction
The packet watchdog fires if no BLE data received for 30s. During GATT
discovery, no data flows. If GATT discovery takes >30s the watchdog kills
the scanner. systemd restarts it and discovery succeeds on the fresh start.
This is self-healing — not ideal but functional.

---

## 5. BlueZ Adapter Reset

### When to use it
After many rapid connect/disconnect cycles, the HCI adapter can get into a
dirty state causing `le-connection-abort-by-local` errors on Connect().

### How to reset
```bash
sudo hciconfig hci0 down
sleep 2
sudo hciconfig hci0 up
sleep 2
sudo systemctl restart juice-ble-scanner
```

This resets the BT adapter completely, clears all stale connection state.

---

## 6. Audio — ALSA Underruns on ARM

### What causes underruns
```
pygame → SDL2 → ALSA buffer → speaker
```
ALSA maintains a small buffer of pre-decoded audio. If pygame/SDL2 can't
decode and fill the buffer fast enough, it runs empty → underrun →
`snd_pcm_recover underrun occurred` in logs → clicks/gaps/silence.

On ARM Cortex-A53, decoding a 38-minute MP3 (anirudh.mp3) while handling
BLE, Flask, and Socket.IO causes buffer starvation with default settings.

### The fix
```python
# Default (broken on ARM):
pygame.mixer.init()  # buffer=512 samples

# Fixed:
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
```
Buffer 4096 = 8× default. Uses ~350KB RAM. Gives ARM enough headroom.
Both SoundPlayer (game.py) and AmbientPlayer (ambient.py) must use
IDENTICAL parameters — second init() is a no-op if params differ.
Constants live in config.py: PYGAME_MIXER_FREQUENCY/SIZE/CHANNELS/BUFFER.

---

## 7. pygame.mixer.init() Idempotency

`pygame.mixer.init()` is only truly idempotent if called with IDENTICAL
parameters. If game.py inits with default params and ambient.py inits with
buffer=4096, the second call is silently ignored — you get the wrong buffer.
Always use constants from config.py for both init calls.

---

## 8. Ambient Music Playlist — event-driven vs polling

### Why event-driven (MUSIC_END) failed
`pygame.mixer.music.set_endevent(MUSIC_END)` fires the event when a track
ends. But during announcement ducking, the music channel is manipulated,
which can interfere with event delivery. The event was being consumed or
lost, causing the playlist to stop after the first track.

### Why polling works
```python
# In _music_loop thread (runs forever):
while self._running:
    if not self._announcement_playing and not pygame.mixer.music.get_busy():
        # track ended — advance playlist
        self._playlist_index = (self._playlist_index + 1) % len(AMBIENT_PLAYLIST)
        load_and_play(AMBIENT_PLAYLIST[self._playlist_index])
    time.sleep(1)
```
`_announcement_playing` flag prevents misreading a ducked track (volume 0.05,
still technically busy or recently stopped) as a track end.

---

## 9. DB Path — Critical

**Correct DB path:** `hub/data/jb.db`
**Wrong path (old leftover):** `hub/juice_battle.db`

Always query: `sqlite3 ~/ArduinoApps/juice_battle/hub/data/jb.db`
Config constant: `DB_PATH = str(pathlib.Path(__file__).parent / 'data' / 'jb.db')`

---

## 10. Key Diagnostic Commands

```bash
# BLE — both nodes status
bluetoothctl devices | grep JB
sudo journalctl -u juice-ble-scanner -f | grep -E "NODE_CONNECTED|NODE_DISCONNECTED|WATCHDOG"

# BLE — adapter reset (when le-connection-abort-by-local appears)
sudo hciconfig hci0 down && sleep 2 && sudo hciconfig hci0 up && sleep 2
sudo systemctl restart juice-ble-scanner

# Audio — check ALSA devices
aplay -l
amixer -c 0 sset Speaker 90%   # restore volume
amixer -c 0 sset Speaker 0%    # silence (hardware mute)

# DB — inspect kv_store
sqlite3 ~/ArduinoApps/juice_battle/hub/data/jb.db "SELECT * FROM kv_store;"

# Service logs
sudo journalctl -u juice-ble-scanner -f
journalctl -u juice-battle -f
```

---

## 11. Principles Reinforced Today

- **JB-1 "not found" = always NimBLE ghost connection.** Never debug at BlueZ
  or Python layer first. Power cycle node → check if it appears → proceed.
- **Never accept "it just works."** The setConnectionParams call compiled,
  ran without errors, and did absolutely nothing. Always verify the API
  is the right one for the role (central vs peripheral).
- **GLib.idle_add is not immediate.** It queues. Multiple queued callbacks
  for the same target cause storms. Claim state synchronously before queuing.
- **D-Bus signals have gaps.** InterfacesAdded fires on first discovery only.
  InterfacesRemoved fires on eviction. PropertiesChanged fires on property
  updates. Missing any one of these creates unrecoverable state.
- **DB path matters.** Two DB files existed. Code used one, we queried the
  other for hours thinking features were broken. Always verify with grep first.
