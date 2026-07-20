import struct
import sys
import json
import time
import socket
import threading
import logging
import dbus
import dbus.mainloop.glib
from gi.repository import GLib
from config import (DEVICE_PREFIX, TRANSPORT_HOST, TRANSPORT_PORT,
                    WATCHDOG_TIMEOUT_S, MSG_NAMES, JB_CHAR_UUID, MSG_DIAG)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [BLE-SCANNER] %(levelname)s %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

BLUEZ        = 'org.bluez'
ADAPTER_PATH = '/org/bluez/hci0'
DBUS_OM      = 'org.freedesktop.DBus.ObjectManager'
DBUS_PROP    = 'org.freedesktop.DBus.Properties'
DEVICE_IFACE = 'org.bluez.Device1'
GATT_CHAR    = 'org.bluez.GattCharacteristic1'

last_packet_time = time.monotonic()
clients: list              = []
clients_lock               = threading.Lock()
loop: GLib.MainLoop | None = None
_bus                       = None

# Connection state — per node, keyed by name ("JB-0", "JB-1")
_active_connections: dict[str, str] = {}   # name → device_path
_connecting_nodes:   set[str]       = set()
_notify_subs:        dict[str, str] = {}   # char_path → node_name


def parse_jb_payload(data: bytes) -> dict | None:
    # WHY: strict length check - partial packets must be silently dropped
    if len(data) < 13:
        return None
    version  = data[0]
    msg_type = data[1]
    node_id  = data[2]

    if msg_type == MSG_DIAG:
        # WHY: DIAG reuses bytes 3-12 differently — no seq_num, no sigma_g
        current_g = struct.unpack_from('<f', data, 3)[0]
        slope_gs  = struct.unpack_from('<f', data, 7)[0]
        state     = data[11]
        quality   = data[12]
        return {
            'msg':       'DIAG',
            'node':      node_id,
            'current_g': round(float(current_g), 2),
            'slope_gs':  round(float(slope_gs), 3),
            'state':     state,
            'quality':   quality,
        }

    # WHY: IEEE754 little-endian float - must be bytes(), not dbus.Array
    delta_g  = struct.unpack_from('<f', data, 3)[0]
    sigma_g  = struct.unpack_from('<f', data, 7)[0]
    seq_num  = struct.unpack_from('<H', data, 11)[0]
    return {
        'msg':     MSG_NAMES.get(msg_type, f'UNKNOWN_0x{msg_type:02X}'),
        'node':    node_id,
        'delta_g': round(float(delta_g), 2),
        'sigma_g': round(float(sigma_g), 3),
        'seq':     seq_num,
        'version': version,
    }


def emit_event(evt: dict, clients: list, clients_lock: threading.Lock) -> None:
    # WHY: NDJSON - one JSON object per line, newline terminated
    # Any client can reconnect and immediately start reading valid lines
    line = json.dumps(evt) + '\n'
    encoded = line.encode('utf-8')
    if evt['msg'] == 'DIAG':
        log.info("[DIAG] node=%d current=%.1fg slope=%.3fg/s state=%d quality=%d",
                 evt['node'], evt['current_g'], evt['slope_gs'], evt['state'], evt['quality'])
    else:
        log.info("[%s] node=%d delta=%.1fg sigma=%.3fg seq=%d",
                 evt['msg'], evt['node'], evt['delta_g'], evt['sigma_g'], evt['seq'])
    with clients_lock:
        dead = []
        for c in clients:
            try:
                c.sendall(encoded)
            except OSError:
                # WHY: client disconnected - remove silently, never crash
                dead.append(c)
        for c in dead:
            clients.remove(c)
            try: c.close()
            except: pass


def _on_notify(interface, changed, invalidated, path):
    global last_packet_time
    if 'Value' not in changed:
        return
    try:
        # WHY: bytes() cast - dbus.Array is not bytes, struct.unpack needs bytes
        data = bytes(changed['Value'])
        evt  = parse_jb_payload(data)
        if evt:
            last_packet_time = time.monotonic()
            emit_event(evt, clients, clients_lock)
    except Exception as e:
        log.warning("Notify parse error from %s: %s", path, e)


def _subscribe_notify(char_path: str, node_name: str) -> None:
    global last_packet_time
    try:
        char = dbus.Interface(_bus.get_object(BLUEZ, char_path), GATT_CHAR)
        char.StartNotify()
        _notify_subs[char_path] = node_name
        _bus.add_signal_receiver(
            _on_notify,
            dbus_interface=DBUS_PROP,
            signal_name='PropertiesChanged',
            path=char_path,
            path_keyword='path'
        )
        last_packet_time = time.monotonic()  # reset watchdog on successful subscribe
        log.info("Subscribed to %s notifications at %s", node_name, char_path)
        _connecting_nodes.discard(node_name)
    except Exception as e:
        log.warning("Subscribe failed for %s: %s", node_name, e)
        _connecting_nodes.discard(node_name)
        if node_name in _active_connections:
            del _active_connections[node_name]


def _find_characteristic(dev_path: str, node_name: str) -> bool:
    if node_name not in _active_connections:
        return False  # disconnected before char discovery completed
    try:
        om      = dbus.Interface(_bus.get_object(BLUEZ, '/'), DBUS_OM)
        objects = om.GetManagedObjects()
        found   = None
        for obj_path, ifaces in objects.items():
            if GATT_CHAR not in ifaces:
                continue
            uuid = str(ifaces[GATT_CHAR].get('UUID', '')).lower()
            # WHY: check path prefix to avoid matching same UUID on the other node
            if uuid == JB_CHAR_UUID.lower() and obj_path.startswith(dev_path):
                found = obj_path
                break
        if found:
            log.info("Found JB char at %s for %s", found, node_name)
            _subscribe_notify(found, node_name)
        else:
            log.warning("JB char not found for %s yet - retrying in 3s", node_name)
            GLib.timeout_add(3000, _find_characteristic, dev_path, node_name)
    except Exception as e:
        log.warning("find_characteristic error for %s: %s", node_name, e)
    return False


def _reconnect_in(delay_ms: int, dev_path: str, node_name: str) -> None:
    def _cb():
        GLib.idle_add(_connect, dev_path, node_name)
        return False
    GLib.timeout_add(delay_ms, _cb)


def _connect(dev_path: str, node_name: str) -> bool:
    global last_packet_time
    if node_name in _active_connections or node_name in _connecting_nodes:
        return False  # already connected or connecting
    _connecting_nodes.add(node_name)
    # WHY: reset watchdog - device.Connect() blocks for up to ~25s (D-Bus timeout);
    # if the main loop is blocked that long, watchdog would fire spuriously.
    # Resetting here means watchdog gives us 30s AFTER connect attempt starts.
    last_packet_time = time.monotonic()
    try:
        dev_obj = _bus.get_object(BLUEZ, dev_path)
        device  = dbus.Interface(dev_obj, DEVICE_IFACE)
        log.info("Connecting to %s...", node_name)
        device.Connect()
        _active_connections[node_name] = dev_path
        log.info("Connected to %s", node_name)
        time.sleep(4)  # WHY: wait for GATT service discovery before searching for char
        GLib.idle_add(_find_characteristic, dev_path, node_name)
    except Exception as e:
        log.warning("Connect to %s failed: %s - retry in 5s", node_name, e)
        _connecting_nodes.discard(node_name)
        _reconnect_in(5000, dev_path, node_name)
    return False


def _interfaces_added(path, interfaces):
    if DEVICE_IFACE not in interfaces:
        return
    props = interfaces[DEVICE_IFACE]
    name  = str(props.get('Name', ''))
    if name.startswith(DEVICE_PREFIX):
        log.info("Found: %s at %s", name, path)
        if name not in _active_connections and name not in _connecting_nodes:
            # WHY: idle_add defers connect out of signal handler - matches reference pattern
            GLib.idle_add(_connect, path, name)


def _properties_changed(interface, changed, invalidated, path):
    if interface != DEVICE_IFACE:
        return
    if 'Connected' not in changed:
        return
    if bool(changed['Connected']):
        return  # connect event - handled inside _connect
    # Disconnect: find which node and schedule reconnect
    for name, dev_path in list(_active_connections.items()):
        if dev_path == path:
            log.info("%s disconnected - reconnecting in 5s", name)
            del _active_connections[name]
            _connecting_nodes.discard(name)
            # Clean up stale char subscriptions for this node
            stale = [cp for cp, n in list(_notify_subs.items()) if n == name]
            for cp in stale:
                del _notify_subs[cp]
            _reconnect_in(5000, path, name)
            break


def _check_known_devices() -> bool:
    # WHY: handles nodes already in BlueZ cache before scanner started;
    # they won't fire InterfacesAdded again — matches reference _check_known_devices
    try:
        om      = dbus.Interface(_bus.get_object(BLUEZ, '/'), DBUS_OM)
        objects = om.GetManagedObjects()
        found   = 0
        for path, ifaces in objects.items():
            if DEVICE_IFACE not in ifaces:
                continue
            props = ifaces[DEVICE_IFACE]
            name  = str(props.get('Name', ''))
            if name.startswith(DEVICE_PREFIX):
                found += 1
                if name not in _active_connections and name not in _connecting_nodes:
                    log.info("Found cached: %s at %s", name, path)
                    GLib.idle_add(_connect, path, name)
        if found == 0:
            log.info("No cached JB-* devices found - waiting for InterfacesAdded")
    except Exception as e:
        log.warning("check_known_devices error: %s", e)
    return False  # GLib.idle_add: False = do not repeat


def _tcp_accept_loop(server_sock: socket.socket) -> None:
    log.info("TCP server accepting on %s:%d", TRANSPORT_HOST, TRANSPORT_PORT)
    while True:
        try:
            conn, addr = server_sock.accept()
            log.info("TCP client connected: %s", addr)
            with clients_lock:
                clients.append(conn)
        except OSError:
            break


def watchdog_fn() -> bool:
    elapsed = time.monotonic() - last_packet_time
    if elapsed > WATCHDOG_TIMEOUT_S:
        log.error("Watchdog triggered - no BLE packets for %ds. Exiting for systemd restart.",
                  WATCHDOG_TIMEOUT_S)
        loop.quit()
        sys.exit(1)
    return True  # GLib: must return True to repeat


def main():
    global loop, _bus

    log.info("Juice Battle BLE scanner starting - GATT central, TCP :%d", TRANSPORT_PORT)
    log.info("Watchdog: %ds timeout", WATCHDOG_TIMEOUT_S)

    # TCP server - start before BLE so consumers can connect immediately
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((TRANSPORT_HOST, TRANSPORT_PORT))
    server_sock.listen(8)
    t = threading.Thread(target=_tcp_accept_loop, args=(server_sock,), daemon=True)
    t.start()

    # D-Bus setup
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus  = dbus.SystemBus()
    _bus = bus

    adapter_obj   = bus.get_object(BLUEZ, ADAPTER_PATH)
    adapter_iface = dbus.Interface(adapter_obj, 'org.bluez.Adapter1')

    # WHY: signal receivers registered BEFORE StartDiscovery - matches proven reference pattern
    bus.add_signal_receiver(
        _interfaces_added,
        dbus_interface=DBUS_OM,
        signal_name='InterfacesAdded'
    )
    bus.add_signal_receiver(
        _properties_changed,
        dbus_interface=DBUS_PROP,
        signal_name='PropertiesChanged',
        path_keyword='path'
    )

    adapter_iface.SetDiscoveryFilter(dbus.Dictionary({
        'Transport': dbus.String('le'),
    }, signature='sv'))
    adapter_iface.StartDiscovery()
    log.info("BLE discovery started - scanning for JB-* nodes")

    # WHY: check nodes already in cache - matches reference _check_known_devices pattern
    GLib.idle_add(_check_known_devices)

    # Watchdog: check every 10s, exit(1) if no packets for WATCHDOG_TIMEOUT_S
    loop = GLib.MainLoop()
    GLib.timeout_add_seconds(10, watchdog_fn)

    loop.run()


if __name__ == '__main__':
    main()
