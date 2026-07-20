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
from config import (COMPANY_ID, DEVICE_PREFIX, TRANSPORT_HOST, TRANSPORT_PORT,
                    WATCHDOG_TIMEOUT_S, MSG_NAMES, PAYLOAD_VERSION)

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

last_packet_time = time.monotonic()
clients: list      = []
clients_lock       = threading.Lock()
loop: GLib.MainLoop | None = None


def parse_jb_payload(data: bytes) -> dict | None:
    # WHY: strict length check - partial BLE packets must be silently dropped
    if len(data) < 13:
        return None
    version  = data[0]
    msg_type = data[1]
    node_id  = data[2]
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


def _handle_device_props(props: dict) -> None:
    global last_packet_time
    mfr = props.get('ManufacturerData')
    if mfr:
        for key, value in mfr.items():
            # WHY: dbus.UInt16 needs explicit int cast for safe comparison
            if int(key) == COMPANY_ID:
                # WHY: cast to bytes() - dbus.Array is not bytes, struct.unpack needs bytes
                data = bytes(value)
                evt = parse_jb_payload(data)
                if evt:
                    last_packet_time = time.monotonic()
                    emit_event(evt, clients, clients_lock)
                return
    # Fallback: name-prefix filter for packets where ManufacturerData not yet populated
    name = str(props.get('Name', ''))
    if name.startswith(DEVICE_PREFIX):
        log.debug("Seen %s (no ManufacturerData yet)", name)


def _on_interfaces_added(path, interfaces):
    if DEVICE_IFACE not in interfaces:
        return
    _handle_device_props(dict(interfaces[DEVICE_IFACE]))


def _on_properties_changed(interface, changed, invalidated, path):
    if interface != DEVICE_IFACE:
        return
    _handle_device_props(dict(changed))


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
    global loop

    log.info("Juice Battle BLE scanner starting - adapter hci0, TCP :%d", TRANSPORT_PORT)
    log.info("Watchdog: %ds timeout", WATCHDOG_TIMEOUT_S)

    # TCP server - start before BLE so clients can connect immediately
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((TRANSPORT_HOST, TRANSPORT_PORT))
    server_sock.listen(8)
    t = threading.Thread(target=_tcp_accept_loop, args=(server_sock,), daemon=True)
    t.start()

    # D-Bus main loop
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    # Adapter
    adapter_obj   = bus.get_object(BLUEZ, ADAPTER_PATH)
    adapter_iface = dbus.Interface(adapter_obj, 'org.bluez.Adapter1')

    # Discovery filter: LE only, DuplicateData=True so every advertisement fires an event
    adapter_iface.SetDiscoveryFilter(dbus.Dictionary({
        'Transport':     dbus.String('le'),
        'DuplicateData': dbus.Boolean(True),
    }, signature='sv'))

    # Signal handlers
    bus.add_signal_receiver(
        _on_interfaces_added,
        dbus_interface=DBUS_OM,
        signal_name='InterfacesAdded'
    )
    bus.add_signal_receiver(
        _on_properties_changed,
        dbus_interface=DBUS_PROP,
        signal_name='PropertiesChanged',
        path_keyword='path'
    )

    # Start discovery
    adapter_iface.StartDiscovery()
    log.info("BLE discovery started")

    # Watchdog: check every 10s, exit(1) if silent for WATCHDOG_TIMEOUT_S
    loop = GLib.MainLoop()
    GLib.timeout_add_seconds(10, watchdog_fn)

    loop.run()


if __name__ == '__main__':
    main()
