import sqlite3
import os
import threading
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


class Storage:
    def __init__(self, db_path: str = "hub/data/jb.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at  TEXT NOT NULL,
                ended_at    TEXT,
                node_count  INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS pour_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  INTEGER REFERENCES sessions(id),
                ts          TEXT NOT NULL,
                node_id     INTEGER NOT NULL,
                delta_g     REAL NOT NULL,
                sigma_g     REAL NOT NULL,
                seq         INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS node_health (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          TEXT NOT NULL,
                node_id     INTEGER NOT NULL,
                msg         TEXT NOT NULL,
                current_g   REAL,
                slope_gs    REAL,
                state       INTEGER,
                quality     INTEGER,
                sigma_g     REAL,
                seq         INTEGER
            );
            CREATE TABLE IF NOT EXISTS error_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          TEXT NOT NULL,
                source      TEXT NOT NULL,
                message     TEXT NOT NULL
            );
        """)
        self._conn.commit()
        log.info("Storage ready at %s", db_path)

    def record_pour(self, session_id: int, ts: str, node_id: int,
                    delta_g: float, sigma_g: float, seq: int) -> None:
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT INTO pour_events "
                    "(session_id, ts, node_id, delta_g, sigma_g, seq) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (session_id, ts, node_id, delta_g, sigma_g, seq)
                )
                self._conn.commit()
        except sqlite3.Error as e:
            log.error("record_pour failed: %s", e)
            self.record_error(datetime.now(timezone.utc).isoformat(), "record_pour", str(e))

    def record_health(self, ts: str, node_id: int, msg: str,
                      current_g=None, slope_gs=None,
                      state=None, quality=None,
                      sigma_g=None, seq=None) -> None:
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT INTO node_health "
                    "(ts, node_id, msg, current_g, slope_gs, state, quality, sigma_g, seq) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (ts, node_id, msg, current_g, slope_gs, state, quality, sigma_g, seq)
                )
                self._conn.commit()
        except sqlite3.Error as e:
            log.error("record_health failed: %s", e)
            self.record_error(datetime.now(timezone.utc).isoformat(), "record_health", str(e))

    def record_error(self, ts: str, source: str, message: str) -> None:
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT INTO error_log (ts, source, message) VALUES (?, ?, ?)",
                    (ts, source, message)
                )
                self._conn.commit()
        except sqlite3.Error as e:
            # WHY: no self-recursion here - just log, never raise
            log.error("record_error failed: %s", e)

    def open_session(self, node_count: int) -> int:
        try:
            with self._lock:
                started_at = datetime.now(timezone.utc).isoformat()
                cur = self._conn.execute(
                    "INSERT INTO sessions (started_at, node_count) VALUES (?, ?)",
                    (started_at, node_count)
                )
                self._conn.commit()
                return cur.lastrowid
        except sqlite3.Error as e:
            log.error("open_session failed: %s", e)
            self.record_error(datetime.now(timezone.utc).isoformat(), "open_session", str(e))
            return -1

    def close_session(self, session_id: int) -> None:
        try:
            with self._lock:
                ended_at = datetime.now(timezone.utc).isoformat()
                self._conn.execute(
                    "UPDATE sessions SET ended_at = ? WHERE id = ?",
                    (ended_at, session_id)
                )
                self._conn.commit()
        except sqlite3.Error as e:
            log.error("close_session failed: %s", e)
            self.record_error(datetime.now(timezone.utc).isoformat(), "close_session", str(e))
