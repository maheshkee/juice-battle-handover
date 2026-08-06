from datetime import datetime, timezone
import threading
import time
import logging
import config
import os
import pygame as _pygame

log = logging.getLogger(__name__)


class SoundPlayer:
    """Non-blocking audio player. pygame.mixer initialised once; each play() fires a
    daemon thread so audio never blocks the game logic thread."""

    _SOUNDS_DIR = os.path.join(os.path.dirname(__file__), "static", "sounds")

    def __init__(self):
        try:
            _pygame.mixer.init()
            self._ok = True
            log.info("SoundPlayer: pygame.mixer initialised")
        except Exception as e:
            self._ok = False
            log.warning("SoundPlayer: mixer init failed (%s) — audio disabled", e)

    def play(self, name: str) -> None:
        """Play <name>.mp3 from static/sounds/. Non-blocking."""
        if not self._ok:
            return
        path = os.path.join(self._SOUNDS_DIR, f"{name}.mp3")
        if not os.path.exists(path):
            log.warning("SoundPlayer: file not found: %s", path)
            return
        t = threading.Thread(target=self._play_file, args=(path,), daemon=True)
        t.start()

    def _play_file(self, path: str) -> None:
        try:
            # Use Sound (sample channel), not mixer.music.
            # mixer.music is reserved for AmbientPlayer's looping flute.
            # Sound plays on its own channel and does not interrupt background music.
            sound = _pygame.mixer.Sound(path)
            channel = sound.play()
            if channel is not None:
                while channel.get_busy():
                    _pygame.time.wait(100)
        except Exception as e:
            log.warning("SoundPlayer: playback error: %s", e)


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
        self._partial_g        = {0: 0.0,  1: 0.0}   # accumulated grams in current window
        self._partial_open_ts  = {0: None, 1: None}  # wall time: when current window opened
        self._glass_count      = {0: 0,    1: 0}
        self._last_seq         = {0: -1,   1: -1}    # dedup guard
        self._last_settled_t   = {0: None, 1: None}  # time.monotonic() of last event
        self._bounce_until     = {0: 0.0,  1: 0.0}  # wall time: suppress after disturbance
        self._settling_until   = {0: 0.0,  1: 0.0}  # wall time: suppress after anomaly
        self._node_status      = {0: 'connected', 1: 'connected'}  # BLE connectivity
        self._game_over            = False
        self._winner               = None   # node_id of winner, or None for draw
        self._reset_since_gameover = set()  # tracks which nodes reset after game_over
        self._sound = SoundPlayer()

        # Round state
        self._ambient           = None
        self.round_number       = storage.get_round_number()
        self.glasses_this_round = 0
        self._round_in_progress = True
        self._round_last_winner = -1
        self._round_last_score0 = 0
        self._round_last_score1 = 0

    def start(self, node_count: int = 1) -> None:
        """Open a storage session and begin accepting pour events."""
        with self._lock:
            if self._running:
                log.warning("Game.start() called while already running - ignored")
                return
            self._partial_g        = {0: 0.0,  1: 0.0}
            self._partial_open_ts  = {0: None, 1: None}
            self._glass_count      = {0: 0,    1: 0}
            self._last_seq         = {0: -1,   1: -1}
            self._last_settled_t   = {0: None, 1: None}
            self._bounce_until     = {0: 0.0,  1: 0.0}
            self._settling_until   = {0: 0.0,  1: 0.0}
            if config.RESUME_SESSION:
                resumable = self._storage.get_resumable_session()
                if resumable:
                    self._session_id = resumable["session_id"]
                    for node_id, count in resumable["glass_counts"].items():
                        self._glass_count[node_id] = count
                    log.info(
                        "RESTORED session=%d glass_counts=%s partial_g=0 (transient, reset)",
                        self._session_id, dict(self._glass_count)
                    )
                else:
                    self._session_id = self._storage.open_session(node_count)
                    log.info("Fresh session created: session_id=%d", self._session_id)
            else:
                self._session_id = self._storage.open_session(node_count)
                log.info("Fresh session created (RESUME_SESSION=False): session_id=%d",
                         self._session_id)
            # Check if last shutdown was clean (operator restart vs crash/power loss)
            if self._storage.get_kv('service_stopped_cleanly') == 'true':
                log.info("Clean restart detected — resetting current-round scores to zero")
                self._storage.set_kv('service_stopped_cleanly', 'false')  # consume the flag
                self._glass_count[0] = 0
                self._glass_count[1] = 0
                self.glasses_this_round = 0
                # round_number and all-time counter are NOT reset
            else:
                log.info("Unclean shutdown or first boot — resuming previous scores")

            self._game_over            = False
            self._winner               = None
            self._reset_since_gameover = set()
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

    def reset_node(self, node_id: int) -> None:
        with self._lock:
            self._storage.log_node_reset(self._session_id, node_id)
            self._glass_count[node_id]     = 0
            self._partial_g[node_id]       = 0.0
            self._partial_open_ts[node_id] = None
            log.info("reset_node: node=%d glass_count reset to 0", node_id)
            if self._game_over:
                self._reset_since_gameover.add(node_id)
                if {0, 1} <= self._reset_since_gameover:
                    self._game_over = False
                    self._winner    = None
                    self._reset_since_gameover.clear()
                    log.info("GAME_OVER cleared: both nodes reset")

    def game_over(self) -> dict:
        with self._lock:
            c0 = self._glass_count[0]
            c1 = self._glass_count[1]
            if c0 > c1:
                self._winner = 0
            elif c1 > c0:
                self._winner = 1
            else:
                self._winner = None
            self._game_over = True
            self._reset_since_gameover.clear()
            if self._winner is not None:
                log.info("GAME_OVER: winner=node=%d glasses=%d",
                         self._winner, self._glass_count[self._winner])
            else:
                log.info("GAME_OVER: DRAW")
            self._sound.play("fanfare")
            return {'game_over': True, 'winner': self._winner}

    def set_ambient(self, ambient) -> None:
        self._ambient = ambient

    def _trigger_round_end(self) -> None:
        # Called under self._lock.
        self._round_in_progress = False
        score0 = self._glass_count[0]
        score1 = self._glass_count[1]
        if score0 > score1:
            winner_node = 0
        elif score1 > score0:
            winner_node = 1
        else:
            winner_node = -1
        self._round_last_winner = winner_node
        self._round_last_score0 = score0
        self._round_last_score1 = score1
        log.info("ROUND_END: round=%d winner=%d score0=%d score1=%d",
                 self.round_number, winner_node, score0, score1)
        threading.Thread(
            target=self._round_end_sequence,
            args=(winner_node,),
            daemon=True
        ).start()

    def _round_end_sequence(self, winner_node: int) -> None:
        if self._ambient is not None:
            self._ambient.play_round_winner(winner_node)
        time.sleep(10)
        with self._lock:
            self._glass_count[0] = 0
            self._glass_count[1] = 0
            self.glasses_this_round = 0
            self.round_number += 1
            new_round = self.round_number
        self._storage.set_round_number(new_round)
        log.info("ROUND_BEGIN: round=%d", new_round)
        if self._ambient is not None:
            self._ambient.play_round_begin(new_round)
        with self._lock:
            self._round_in_progress = True

    def adjust_glass_count(self, node_id: int, delta: int) -> int:
        with self._lock:
            self._glass_count[node_id] = max(0, self._glass_count[node_id] + delta)
            log.info("ADJUST: node=%d delta=%+d new_count=%d",
                     node_id, delta, self._glass_count[node_id])
            return self._glass_count[node_id]

    def on_node_disconnected(self, evt: dict) -> None:
        node_id = evt.get('node', -1)
        if node_id not in (0, 1):
            return
        with self._lock:
            self._node_status[node_id] = 'disconnected'
        log.info("NODE_DISCONNECTED: node=%d", node_id)

    def on_node_connected(self, evt: dict) -> None:
        node_id = evt.get('node', -1)
        if node_id not in (0, 1):
            return
        with self._lock:
            self._node_status[node_id] = 'connected'
            self._partial_g[node_id]       = 0.0
            self._partial_open_ts[node_id] = None
        log.info("NODE_CONNECTED: node=%d partial_g reset", node_id)

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
            if self._game_over:
                return
            if not self._round_in_progress:
                return

            # --- Belt-and-suspenders dedup (ble_scanner.py also deduplicates) ---
            if seq == self._last_seq[node_id]:
                log.debug("POUR_SETTLED: dup seq=%d node=%d - ignored", seq, node_id)
                return
            self._last_seq[node_id] = seq

            # --- Suppression gates: post-disturbance bounce and post-anomaly settling ---
            now_wall = time.time()
            if now_wall < self._bounce_until[node_id]:
                log.info("POUR_SETTLED: node=%d delta=%.1fg bounce-suppressed", node_id, delta_g)
                return
            if now_wall < self._settling_until[node_id]:
                log.info("POUR_SETTLED: node=%d delta=%.1fg post-anomaly settling suppressed",
                         node_id, delta_g)
                return

            # --- Noise floor filter using live sigma_g from this event ---
            # sigma_g is measured at node boot under real operating conditions.
            # 3-sigma rule: anything below 3*sigma is statistically indistinguishable
            # from noise. POUR_MIN_G is an absolute floor for sigma_g=0 edge case.
            threshold = max(config.POUR_MIN_G, config.POUR_SIGMA_K * sigma_g)
            if delta_g < threshold:
                if delta_g < -threshold:
                    self._bounce_until[node_id] = time.time() + config.BOUNCE_SETTLE_S
                    if self._partial_g[node_id] > 0:
                        log.warning("DISTURBANCE: node=%d large neg delta=%.1fg "
                                    "clearing partial=%.1fg bounce suppressed %.0fs",
                                    node_id, delta_g, self._partial_g[node_id],
                                    config.BOUNCE_SETTLE_S)
                        self._storage.log_overflow(
                            node_id, seq, 'DISTURBANCE_CLR',
                            self._partial_g[node_id], self._partial_open_ts[node_id])
                        self._partial_g[node_id] = 0.0
                        self._partial_open_ts[node_id] = None
                else:
                    log.info("POUR_SETTLED: node=%d delta=%.1fg below threshold=%.1fg "
                             "(sigma=%.2fg) - noise, ignored", node_id, delta_g, threshold, sigma_g)
                return

            # --- Plausibility ceiling: jar lift produces delta >> any real pour ---
            if delta_g > config.GLASS_VOLUME_G * config.POUR_MAX_G_FRAC:
                log.warning("ANOMALY: node=%d delta=%.1fg exceeds %.0fg ceiling - "
                            "jar removed? NOT scored",
                            node_id, delta_g, config.GLASS_VOLUME_G * config.POUR_MAX_G_FRAC)
                self._settling_until[node_id] = time.time() + config.ANOMALY_SETTLE_S
                self._storage.log_overflow(
                    node_id, seq, 'ANOMALY_DELTA',
                    delta_g, None)
                if self._partial_g[node_id] > 0:
                    self._storage.log_overflow(
                        node_id, seq, 'ANOMALY_CLR',
                        self._partial_g[node_id], self._partial_open_ts[node_id])
                self._partial_g[node_id] = 0.0
                self._partial_open_ts[node_id] = None
                return

            # --- Pour window: same pour or new visitor? ---
            # BLE loss fallback: if POUR_ACTIVE was missed, boundary fires here.
            now = time.monotonic()
            self._boundary_check(node_id, now, seq)
            self._last_settled_t[node_id] = now

            # --- Accumulate and count ---
            if self._partial_g[node_id] == 0:
                self._partial_open_ts[node_id] = now_wall
            self._partial_g[node_id] += delta_g
            new_glasses = 0
            while self._partial_g[node_id] >= config.GLASS_VOLUME_G:
                self._glass_count[node_id] += 1
                self._partial_g[node_id]   -= config.GLASS_VOLUME_G
                new_glasses += 1
            # Per-person semantics: overshoot residue dies immediately at glass-fire.
            if new_glasses > 0:
                self._sound.play("glass")
                if self._partial_g[node_id] > 0:
                    self._storage.log_overflow(
                        node_id, seq, 'RESIDUE',
                        self._partial_g[node_id], self._partial_open_ts[node_id])
                self._partial_g[node_id] = 0.0
                self._partial_open_ts[node_id] = None
                self.glasses_this_round += new_glasses
                if self.glasses_this_round >= config.ROUND_SIZE:
                    self._trigger_round_end()

            # --- Persist to storage ---
            ts = datetime.now(timezone.utc).isoformat()
            self._storage.record_pour(
                session_id=self._session_id,
                ts=ts,
                node_id=node_id,
                delta_g=delta_g,
                sigma_g=sigma_g,
                seq=seq,
                glasses_counted=new_glasses,
            )

            log.info("POUR_SETTLED: node=%d delta=%.1fg new_glasses=%d "
                     "total=%d partial=%.1fg seq=%d",
                     node_id, delta_g, new_glasses,
                     self._glass_count[node_id], self._partial_g[node_id], seq)

    def on_pour_active(self, evt: dict) -> None:
        """POUR_ACTIVE = juice flowing right now (firmware slope detector).
        WHY: POUR_ACTIVE only fires when the slope detector sees real flow - slow drips
        never trigger it. A POUR_ACTIVE after gap > window is always a new visitor,
        never a drip continuation, so partial is unconditionally discarded."""
        node_id = evt.get('node', -1)
        if node_id not in (0, 1):
            return
        with self._lock:
            if not self._running:
                return
            now = time.monotonic()
            if (self._last_settled_t[node_id] is not None and
                    now - self._last_settled_t[node_id] > config.POUR_WINDOW_S):
                partial = self._partial_g[node_id]
                if partial > 0:
                    log.info("POUR_ACTIVE: node=%d new pour after %.0fs - "
                             "discarding partial=%.1fg",
                             node_id, now - self._last_settled_t[node_id], partial)
                    self._storage.log_overflow(
                        node_id, None, 'ABANDONED_BOUNDARY',
                        partial, self._partial_open_ts[node_id])
                    self._partial_g[node_id] = 0.0
                    self._partial_open_ts[node_id] = None
            self._last_settled_t[node_id] = now

    def _boundary_check(self, node_id: int, now: float, seq=None) -> None:
        """Called under self._lock. On window expiry, preserve or discard stale partial."""
        if self._last_settled_t[node_id] is None:
            return
        gap = now - self._last_settled_t[node_id]
        if gap <= config.POUR_WINDOW_S:
            return
        partial = self._partial_g[node_id]
        if partial == 0.0:
            return
        log.info("POUR_SETTLED: node=%d window expired - discarding partial=%.1fg",
                 node_id, partial)
        self._storage.log_overflow(
            node_id, seq, 'ABANDONED_WINDOW',
            partial, self._partial_open_ts[node_id])
        self._partial_g[node_id] = 0.0
        self._partial_open_ts[node_id] = None

    def get_state(self) -> dict:
        """
        Thread-safe snapshot. Safe to call from dashboard thread at any time.
        node_status: 'ok' | 'bounce' | 'anomaly' per node.
        """
        with self._lock:
            now = time.time()
            return {
                "session_id":  self._session_id,
                "glass_count": dict(self._glass_count),
                "partial_g":   dict(self._partial_g),
                "running":     self._running,
                "game_over":   self._game_over,
                "winner":      self._winner,
                "node_status": {
                    node_id: (
                        'anomaly' if now < self._settling_until[node_id] else
                        'bounce'  if now < self._bounce_until[node_id]   else
                        'ok'
                    )
                    for node_id in (0, 1)
                },
                "ble_status":  dict(self._node_status),
                "round_number":       self.round_number,
                "round_in_progress":  self._round_in_progress,
                "glasses_this_round": self.glasses_this_round,
                "round_last_winner":  self._round_last_winner,
                "round_last_score0":  self._round_last_score0,
                "round_last_score1":  self._round_last_score1,
            }
