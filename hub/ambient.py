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
MUSIC_VOLUME     = 0.40   # 0.0–1.0  (background level — low enough to talk over)
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

            first_track = os.path.join(SOUNDS_DIR, AMBIENT_PLAYLIST[0])
            if not os.path.exists(first_track):
                log.warning("AmbientPlayer: %s not found — music disabled", AMBIENT_PLAYLIST[0])
                self._music_ok = False
            else:
                pygame.mixer.music.load(first_track)
                pygame.mixer.music.set_volume(MUSIC_VOLUME)
                pygame.mixer.music.play()
                self._playlist_index = 0
                self._music_ok = True
                log.info("AmbientPlayer: background music started — %s (volume=%.2f)",
                         AMBIENT_PLAYLIST[0], MUSIC_VOLUME)
                log.info("AmbientPlayer: now playing track %d/%d: %s",
                         self._playlist_index + 1, len(AMBIENT_PLAYLIST),
                         AMBIENT_PLAYLIST[self._playlist_index])

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

    # ------------------------------------------------------------------ #
    #  Internal                                                            #
    # ------------------------------------------------------------------ #

    def _music_loop(self) -> None:
        """Polling playlist loop. Advances to the next track when get_busy() returns False."""
        while True:
            with self._lock:
                if not self._running:
                    break
            if not self._announcement_playing and not pygame.mixer.music.get_busy():
                self._playlist_index = (self._playlist_index + 1) % len(AMBIENT_PLAYLIST)
                next_track = os.path.join(SOUNDS_DIR, AMBIENT_PLAYLIST[self._playlist_index])
                pygame.mixer.music.load(next_track)
                pygame.mixer.music.set_volume(MUSIC_VOLUME)
                pygame.mixer.music.play()
                log.info("AmbientPlayer: playlist advanced → %s",
                         AMBIENT_PLAYLIST[self._playlist_index])
                log.info("AmbientPlayer: now playing track %d/%d: %s",
                         self._playlist_index + 1, len(AMBIENT_PLAYLIST),
                         AMBIENT_PLAYLIST[self._playlist_index])
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
