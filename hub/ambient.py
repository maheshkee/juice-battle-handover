"""
ambient.py — Background music + periodic voice announcements for Juice Battle.

Architecture:
  - Music channel (pygame.mixer.music): plays AMBIENT_PLAYLIST tracks in order, cycling.
  - Announcement channel (pygame.mixer.Sound): plays TTS MP3s at full volume.
  - Scheduler thread: every ANNOUNCE_INTERVAL_S seconds, picks next announcement,
    ducks music, plays announcement, restores music.

Why two separate pygame channels?
  pygame.mixer.music  = single streaming channel, ideal for long looping tracks.
  pygame.mixer.Sound  = sample channel (pre-loaded), ideal for short clips.
  This lets us duck/restore music volume independently of announcements.
"""

import os
import threading
import time
import logging
import pygame
import config

log = logging.getLogger(__name__)

SOUNDS_DIR       = os.path.join(os.path.dirname(__file__), "static", "sounds")
AMBIENT_PLAYLIST = ['varanasi.mp3', 'anirudh.mp3']   # played in order, cycling
MUSIC_VOLUME     = 0.20   # 0.0–1.0  (background level — low enough to talk over)
DUCKED_VOLUME    = 0.05   # near-silent while announcement plays
ANNOUNCE_INTERVAL_S = 30  # seconds between announcements
FADE_MS          = 800    # music fade duration in ms

# Announcement files in rotation order
ANNOUNCEMENTS = [
    "ann_namaste",
    "ann_come_taste",
    "ann_grounded",
    "ann_every_drop",
    "ann_enthusiasts",
    "ann_real_sensors",
    "ann_every_dot",
]


def _detect_usb_playlist() -> list:
    """Scan for a USB pendrive mounted under /media/arduino/ containing
    MP3 files. If found, use those as the ambient playlist (sorted
    alphabetically). Falls back to built-in playlist if nothing found.

    WHY: operator plugs in a pendrive before the stall starts.
    No SSH, no code changes. Pull it out = automatic fallback.
    The pendrive REPLACES the built-in playlist entirely — operator
    curates it for the specific event.
    """
    import glob

    media_root = "/media/arduino"
    fallback   = AMBIENT_PLAYLIST  # built-in list defined in config or here

    if not os.path.isdir(media_root):
        return fallback

    # Find all mounted volumes under /media/arduino/
    try:
        volumes = [
            os.path.join(media_root, d)
            for d in os.listdir(media_root)
            if os.path.isdir(os.path.join(media_root, d))
        ]
    except PermissionError:
        return fallback

    for vol in sorted(volumes):
        mp3s = sorted(glob.glob(os.path.join(vol, "*.mp3")))
        if mp3s:
            log.info(
                "USB playlist detected: %d tracks from %s", len(mp3s), vol
            )
            return mp3s

    log.info("No USB playlist found — using built-in playlist")
    return fallback


class AmbientPlayer:
    """
    Start with AmbientPlayer().start()
    Stop with AmbientPlayer().stop()
    Both are thread-safe.
    """

    def __init__(self):
        self._running             = False
        self._lock                = threading.Lock()
        self._ann_index           = 0          # round-robin index into ANNOUNCEMENTS
        self._music_ok            = False
        self._scheduler           = None
        self._music_thread        = None
        self._playlist_index      = 0
        self._announcement_playing = False
        self._music_paused         = False
        self._playlist = _detect_usb_playlist()
        log.info("AmbientPlayer playlist: %s",
                 [os.path.basename(p) for p in self._playlist])

    def start(self) -> None:
        """Start background music and announcement scheduler."""
        try:
            # pygame.mixer may already be initialised by SoundPlayer in game.py.
            # init() is idempotent — safe to call again.
            if not pygame.mixer.get_init():
                pygame.mixer.init(
                    frequency=config.PYGAME_MIXER_FREQUENCY,
                    size=config.PYGAME_MIXER_SIZE,
                    channels=config.PYGAME_MIXER_CHANNELS,
                    buffer=config.PYGAME_MIXER_BUFFER,
                )

            self._playlist_index = 0
            _t0 = self._playlist[0]
            if not os.path.isabs(_t0):
                _t0 = os.path.join(SOUNDS_DIR, _t0)
            if not os.path.exists(_t0):
                log.warning("AmbientPlayer: %s not found — music disabled",
                            os.path.basename(self._playlist[0]))
                self._music_ok = False
            else:
                pygame.mixer.music.load(_t0)
                pygame.mixer.music.set_volume(MUSIC_VOLUME)
                pygame.mixer.music.play()
                self._music_ok = True
                log.info("AmbientPlayer: background music started — %s (volume=%.2f)",
                         os.path.basename(self._playlist[0]), MUSIC_VOLUME)
                log.info("AmbientPlayer: now playing track %d/%d: %s",
                         self._playlist_index + 1, len(self._playlist),
                         os.path.basename(self._playlist[self._playlist_index]))

        except Exception as e:
            log.warning("AmbientPlayer: failed to start music: %s", e)
            self._music_ok = False

        self._running = True
        self._music_thread = threading.Thread(
            target=self._music_loop, daemon=True, name="ambient-music"
        )
        self._music_thread.start()
        self._scheduler = threading.Thread(
            target=self._scheduler_loop, daemon=True, name="ambient-scheduler"
        )
        self._scheduler.start()
        log.info("AmbientPlayer: announcement scheduler started (interval=%ds)", ANNOUNCE_INTERVAL_S)

    def stop(self) -> None:
        """Gracefully stop music and scheduler."""
        with self._lock:
            self._running = False
        if self._music_ok:
            pygame.mixer.music.fadeout(FADE_MS)
        log.info("AmbientPlayer: stopped")

    def set_music_volume(self, level: float) -> float:
        """Set music volume live. Clamps to 0.0–1.0.
        Also updates module-level MUSIC_VOLUME so ducking/restore
        still targets the new level, not the old constant."""
        global MUSIC_VOLUME
        level = max(0.0, min(1.0, level))
        MUSIC_VOLUME = level
        with self._lock:
            if not self._announcement_playing:
                pygame.mixer.music.set_volume(level)
        log.info("AmbientPlayer: volume set to %.2f", level)
        return level

    def pause_music(self) -> None:
        """Pause background music. Announcements still work."""
        with self._lock:
            pygame.mixer.music.pause()
            self._music_paused = True
        log.info("AmbientPlayer: music paused")

    def resume_music(self) -> None:
        """Resume background music after pause."""
        with self._lock:
            pygame.mixer.music.unpause()
            self._music_paused = False
        log.info("AmbientPlayer: music resumed")

    def next_track(self) -> str:
        """Skip to next track in playlist immediately.
        Returns the basename of the new track."""
        with self._lock:
            self._playlist_index = (
                (self._playlist_index + 1) % len(self._playlist)
            )
            track = self._playlist[self._playlist_index]
            # WHY: fallback playlist entries are bare filenames ('varanasi.mp3').
            # Must resolve to absolute path — same pattern as _music_loop().
            if not os.path.isabs(track):
                track = os.path.join(SOUNDS_DIR, track)
            pygame.mixer.music.load(track)
            pygame.mixer.music.set_volume(MUSIC_VOLUME)
            pygame.mixer.music.play()
        name = os.path.basename(track)
        log.info("AmbientPlayer: skipped to %s", name)
        return name

    def rescan_playlist(self) -> dict:
        """
        Hot-plug handler. Re-runs USB detection and reloads music if
        playlist changed. Safe to call anytime — from udev via curl.
        Called by POST /audio/rescan_playlist endpoint.
        """
        old_playlist = list(self._playlist)
        new_playlist = _detect_usb_playlist()

        if new_playlist == old_playlist:
            log.info("AmbientPlayer: rescan — playlist unchanged")
            return {"changed": False, "playlist": new_playlist}

        # Playlist changed — reload
        self._playlist = new_playlist
        self._playlist_index = 0
        log.info(
            "AmbientPlayer: rescan — playlist changed → %s",
            [os.path.basename(p) for p in new_playlist]
        )

        # Stop current music and restart with new playlist
        try:
            pygame.mixer.music.stop()
            self._music_paused = False
            threading.Timer(0.5, self._play_current_track).start()
        except Exception as e:
            log.warning("AmbientPlayer: rescan reload error: %s", e)

        return {"changed": True, "playlist": [os.path.basename(p) for p in new_playlist]}

    # ------------------------------------------------------------------ #
    #  Internal                                                            #
    # ------------------------------------------------------------------ #

    def _play_current_track(self) -> None:
        """Load and play the track at self._playlist_index."""
        track = self._playlist[self._playlist_index]
        if not os.path.isabs(track):
            track = os.path.join(SOUNDS_DIR, track)
        pygame.mixer.music.load(track)
        pygame.mixer.music.set_volume(MUSIC_VOLUME)
        pygame.mixer.music.play()
        log.info("AmbientPlayer: now playing track %d/%d: %s",
                 self._playlist_index + 1, len(self._playlist),
                 os.path.basename(track))

    def _music_loop(self) -> None:
        """Polling playlist loop. Advances to the next track when get_busy() returns False."""
        while True:
            with self._lock:
                if not self._running:
                    break
            if not self._announcement_playing and not self._music_paused and not pygame.mixer.music.get_busy():
                self._playlist_index = (self._playlist_index + 1) % len(self._playlist)
                track = self._playlist[self._playlist_index]
                # WHY: fallback playlist returns bare filenames, USB returns absolute paths.
                # Only prepend SOUNDS_DIR if the path is not already absolute.
                if not os.path.isabs(track):
                    track = os.path.join(SOUNDS_DIR, track)
                pygame.mixer.music.load(track)
                pygame.mixer.music.set_volume(MUSIC_VOLUME)
                pygame.mixer.music.play()
                log.info("AmbientPlayer: playlist advanced → %s",
                         os.path.basename(self._playlist[self._playlist_index]))
                log.info("AmbientPlayer: now playing track %d/%d: %s",
                         self._playlist_index + 1, len(self._playlist),
                         os.path.basename(self._playlist[self._playlist_index]))
            time.sleep(1)

    def _scheduler_loop(self) -> None:
        """Runs in daemon thread. Fires announcements on a fixed interval."""
        # Wait one full interval before first announcement
        # so music can establish itself first
        time.sleep(ANNOUNCE_INTERVAL_S)

        while True:
            with self._lock:
                if not self._running:
                    break

            self._play_announcement()
            time.sleep(ANNOUNCE_INTERVAL_S)

    def _play_announcement(self) -> None:
        """Duck music → play announcement → restore music."""
        name = ANNOUNCEMENTS[self._ann_index % len(ANNOUNCEMENTS)]
        self._ann_index += 1

        path = os.path.join(SOUNDS_DIR, f"{name}.mp3")
        if not os.path.exists(path):
            log.warning("AmbientPlayer: announcement file missing: %s", path)
            return

        try:
            # Load announcement as a Sound object (pre-buffered, separate channel)
            sound = pygame.mixer.Sound(path)
            duration = sound.get_length()   # seconds

            # Duck background music
            self._announcement_playing = True
            if self._music_ok:
                pygame.mixer.music.set_volume(DUCKED_VOLUME)

            log.info("AmbientPlayer: playing announcement '%s' (%.1fs)", name, duration)
            sound.play()

            # Wait for announcement to finish
            time.sleep(duration + 0.3)   # 300ms tail gap

            # Restore music volume
            if self._music_ok:
                pygame.mixer.music.set_volume(MUSIC_VOLUME)
            self._announcement_playing = False

        except Exception as e:
            log.warning("AmbientPlayer: announcement playback error: %s", e)
            # Always restore volume even on error
            if self._music_ok:
                pygame.mixer.music.set_volume(MUSIC_VOLUME)
            self._announcement_playing = False

    def play_round_winner(self, winner_node: int) -> None:
        """Play round winner announcement. Blocks until audio finishes."""
        if winner_node == 0:
            name = 'ann_round_winner_0'
        elif winner_node == 1:
            name = 'ann_round_winner_1'
        else:
            name = 'ann_round_tie'
        path = os.path.join(SOUNDS_DIR, f"{name}.mp3")
        if not os.path.exists(path):
            log.warning("AmbientPlayer: file missing: %s", path)
            return
        try:
            sound = pygame.mixer.Sound(path)
            duration = sound.get_length()
            self._announcement_playing = True
            if self._music_ok:
                pygame.mixer.music.set_volume(DUCKED_VOLUME)
            log.info("AmbientPlayer: playing '%s' (%.1fs)", name, duration)
            sound.play()
            time.sleep(duration + 0.3)
            if self._music_ok:
                pygame.mixer.music.set_volume(MUSIC_VOLUME)
            self._announcement_playing = False
        except Exception as e:
            log.warning("AmbientPlayer: playback error: %s", e)
            if self._music_ok:
                pygame.mixer.music.set_volume(MUSIC_VOLUME)
            self._announcement_playing = False

    def play_round_begin(self, round_number: int) -> None:
        """Play round begin announcement. Blocks until audio finishes."""
        if 1 <= round_number <= 10:
            name = f'ann_round_begin_{round_number}'
        else:
            name = 'ann_round_begin_generic'
        path = os.path.join(SOUNDS_DIR, f"{name}.mp3")
        if not os.path.exists(path):
            log.warning("AmbientPlayer: file missing: %s", path)
            return
        try:
            sound = pygame.mixer.Sound(path)
            duration = sound.get_length()
            self._announcement_playing = True
            if self._music_ok:
                pygame.mixer.music.set_volume(DUCKED_VOLUME)
            log.info("AmbientPlayer: playing '%s' (%.1fs)", name, duration)
            sound.play()
            time.sleep(duration + 0.3)
            if self._music_ok:
                pygame.mixer.music.set_volume(MUSIC_VOLUME)
            self._announcement_playing = False
        except Exception as e:
            log.warning("AmbientPlayer: playback error: %s", e)
            if self._music_ok:
                pygame.mixer.music.set_volume(MUSIC_VOLUME)
            self._announcement_playing = False
