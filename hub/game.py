from datetime import datetime, timezone
import threading
import time
import logging
import config

log = logging.getLogger(__name__)


class Game:
    """
    Hub-side game state machine.

    Wiring (main.py's responsibility, not Game's):
        transport.on_event(game.on_pour_settled, msg_filter="POUR_SETTLED")

    Glass counting rules:
      - Noise filter: delta_g must exceed max(POUR_MIN_G, POUR_SIGMA_K * sigma_g)
      - Pour window:  events arriving within POUR_WINDOW_S of each other
                      accumulate (same physical pour, split settle events).
                      Gap > POUR_WINDOW_S resets partial_g - new visitor, fresh start.
      - Count:        while partial_g >= GLASS_VOLUME_G: glass_count += 1,
                      partial_g -= GLASS_VOLUME_G
      - Remainder:    stays in partial_g, waiting for next split event within window.
                      Discarded on window expiry.

    Thread safety: Transport callbacks fire on GLib thread. get_state() may be
    called from dashboard thread. One lock protects all mutable state.
    """

    def __init__(self, storage):
        self._storage = storage
        self._lock    = threading.Lock()
        self._running    = False
        self._session_id = None

        # Per-node state (keyed by node_id: 0 or 1)
        self._partial_g      = {0: 0.0,  1: 0.0}   # accumulated grams in current window
        self._glass_count    = {0: 0,    1: 0}
        self._last_seq       = {0: -1,   1: -1}     # dedup guard
        self._last_settled_t = {0: None, 1: None}   # time.monotonic() of last event

    def start(self, node_count: int = 1) -> None:
        """Open a storage session and begin accepting pour events."""
        with self._lock:
            if self._running:
                log.warning("Game.start() called while already running - ignored")
                return
            self._session_id = self._storage.open_session(node_count)
            self._partial_g      = {0: 0.0,  1: 0.0}
            self._glass_count    = {0: 0,    1: 0}
            self._last_seq       = {0: -1,   1: -1}
            self._last_settled_t = {0: None, 1: None}
            self._running = True
            log.info("Game started - session_id=%s node_count=%d",
                     self._session_id, node_count)

    def stop(self) -> None:
        """Close the storage session and stop accepting pour events."""
        with self._lock:
            if not self._running:
                return
            self._storage.close_session(self._session_id)
            self._running = False
            log.info("Game stopped - session_id=%s final_count=%s",
                     self._session_id, dict(self._glass_count))

    def on_pour_settled(self, event: dict) -> None:
        """
        Called by Transport on every POUR_SETTLED packet.
        Registered by main.py - Game does not self-register on Transport.

        Expected event keys: msg, node, delta_g, sigma_g, seq, version
        """
        # Defensive: transport filter should guarantee this, but verify
        if event.get("msg") != "POUR_SETTLED":
            log.warning("on_pour_settled received unexpected msg=%s", event.get("msg"))
            return

        node_id = event.get("node",    -1)
        delta_g = event.get("delta_g", 0.0)
        sigma_g = event.get("sigma_g", 0.0)
        seq     = event.get("seq",     -1)

        if node_id not in (0, 1):
            log.warning("POUR_SETTLED: unknown node_id=%s - ignored", node_id)
            return

        with self._lock:
            if not self._running:
                # Event arrived before start() or after stop() - discard silently
                return

            # --- Belt-and-suspenders dedup (ble_scanner.py also deduplicates) ---
            if seq == self._last_seq[node_id]:
                log.debug("POUR_SETTLED: dup seq=%d node=%d - ignored", seq, node_id)
                return
            self._last_seq[node_id] = seq

            # --- Noise floor filter using live sigma_g from this event ---
            # sigma_g is measured at node boot under real operating conditions.
            # 3-sigma rule: anything below 3*sigma is statistically indistinguishable
            # from noise. POUR_MIN_G is an absolute floor for sigma_g=0 edge case.
            threshold = max(config.POUR_MIN_G, config.POUR_SIGMA_K * sigma_g)
            if delta_g < threshold:
                log.info("POUR_SETTLED: node=%d delta=%.1fg below threshold=%.1fg "
                         "(sigma=%.2fg) - noise, ignored", node_id, delta_g, threshold)
                return

            # --- Pour window: same pour or new visitor? ---
            # If gap since last settled event > POUR_WINDOW_S, this is a new visitor.
            # Discard any stale partial_g left from the previous pour before accumulating.
            now = time.monotonic()
            if (self._last_settled_t[node_id] is not None and
                    now - self._last_settled_t[node_id] > config.POUR_WINDOW_S):
                if self._partial_g[node_id] > 0:
                    log.info("POUR_SETTLED: node=%d window expired - "
                             "discarding stale partial=%.1fg",
                             node_id, self._partial_g[node_id])
                self._partial_g[node_id] = 0.0
            self._last_settled_t[node_id] = now

            # --- Accumulate and count ---
            self._partial_g[node_id] += delta_g
            new_glasses = 0
            while self._partial_g[node_id] >= config.GLASS_VOLUME_G:
                self._glass_count[node_id] += 1
                self._partial_g[node_id]   -= config.GLASS_VOLUME_G
                new_glasses += 1

            # --- Persist to storage ---
            ts = datetime.now(timezone.utc).isoformat()
            self._storage.record_pour(
                session_id=self._session_id,
                ts=ts,
                node_id=node_id,
                delta_g=delta_g,
                sigma_g=sigma_g,
                seq=seq,
            )

            log.info("POUR_SETTLED: node=%d delta=%.1fg new_glasses=%d "
                     "total=%d partial=%.1fg seq=%d",
                     node_id, delta_g, new_glasses,
                     self._glass_count[node_id], self._partial_g[node_id], seq)

    def get_state(self) -> dict:
        """
        Thread-safe snapshot. Safe to call from dashboard thread at any time.
        partial_g: grams accumulated so far in the current pour window.
        """
        with self._lock:
            return {
                "session_id":  self._session_id,
                "glass_count": dict(self._glass_count),
                "partial_g":   dict(self._partial_g),
                "running":     self._running,
            }
