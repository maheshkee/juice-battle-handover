import json
import socket
import time
import threading
import logging
from config import (TRANSPORT_CLIENT_HOST, TRANSPORT_CLIENT_PORT,
                    TRANSPORT_RECONNECT_S)

log = logging.getLogger(__name__)


class Transport:
    """
    WHY this class exists: the Docker app must never know or care about BLE.
    It registers callbacks. Transport delivers events. BLE is invisible.
    """
    def __init__(self):
        self._callbacks: list = []   # list of (msg_filter, fn) - msg_filter=None means all
        self._thread: threading.Thread | None = None
        self._running = False

    def on_event(self, fn, msg_filter=None):
        # WHY: msg_filter=None = receive all event types
        # msg_filter="POUR_SETTLED" = receive only that type
        self._callbacks.append((msg_filter, fn))

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        log.info("Transport started  %s:%d", TRANSPORT_CLIENT_HOST, TRANSPORT_CLIENT_PORT)

    def _run_loop(self):
        while self._running:
            try:
                self._connect_and_read()
            except Exception as e:
                log.warning("Transport disconnected: %s - reconnecting in %ds",
                            e, TRANSPORT_RECONNECT_S)
                time.sleep(TRANSPORT_RECONNECT_S)

    def _connect_and_read(self):
        with socket.create_connection(
            (TRANSPORT_CLIENT_HOST, TRANSPORT_CLIENT_PORT), timeout=10
        ) as sock:
            log.info("Transport connected to scanner")
            buf = b""
            while self._running:
                chunk = sock.recv(4096)
                if not chunk:
                    raise ConnectionResetError("Scanner closed connection")
                buf += chunk
                # WHY: split on newline - NDJSON framing
                while b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                    self._dispatch(line.decode('utf-8', errors='replace').strip())

    def _dispatch(self, line: str):
        if not line:
            return
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            log.warning("Bad JSON line: %r", line)
            return
        for msg_filter, fn in self._callbacks:
            if msg_filter is None or evt.get('msg') == msg_filter:
                try:
                    fn(evt)
                except Exception as e:
                    log.error("Callback error: %s", e)

    def stop(self):
        self._running = False


if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)
    t = Transport()
    t.on_event(lambda e: print(f"EVENT: {e}"))
    t.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        t.stop()
