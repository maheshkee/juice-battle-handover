import sqlite3
import os
import threading
import time
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
            CREATE TABLE IF NOT EXISTS overflow_events (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                ts             REAL    NOT NULL,
                node_id        INTEGER NOT NULL,
                seq            INTEGER,
                reason         TEXT    NOT NULL,
                grams          REAL    NOT NULL,
                window_open_ts REAL
            );
            CREATE INDEX IF NOT EXISTS ix_overflow_node_ts
                ON overflow_events(node_id, ts);
            CREATE INDEX IF NOT EXISTS ix_overflow_reason
                ON overflow_events(reason);
        """)
        self._conn.commit()
        self._migrate()
        log.info("Storage ready at %s", db_path)

    def _migrate(self) -> None:
        """Idempotent schema migrations. Safe to run on every startup."""
        try:
            self._conn.execute(
                "ALTER TABLE pour_events "
                "ADD COLUMN glasses_counted INTEGER NOT NULL DEFAULT 0"
            )
            self._conn.commit()
            log.info("Migration: added glasses_counted column to pour_events")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                pass  # already migrated — fine
            else:
                raise
        try:
            self._conn.execute(
                "ALTER TABLE pour_events ADD COLUMN event_time REAL"
            )
            self._conn.commit()
            log.info("Migration: added event_time column to pour_events")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                pass
            else:
                raise
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS node_resets (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                node_id    INTEGER NOT NULL,
                reset_at   REAL    NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        self._conn.commit()

    def record_pour(self, session_id: int, ts: str, node_id: int,
                    delta_g: float, sigma_g: float, seq: int,
                    glasses_counted: int = 0) -> None:
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT INTO pour_events "
                    "(session_id, ts, node_id, delta_g, sigma_g, seq, glasses_counted, event_time) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (session_id, ts, node_id, delta_g, sigma_g, seq, glasses_counted, time.time())
                )
                self._conn.commit()
        except sqlite3.Error as e:
            log.error("record_pour failed: %s", e)
            self.record_error(datetime.now(timezone.utc).isoformat(), "record_pour", str(e))

    def log_node_reset(self, session_id: int, node_id: int) -> None:
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT INTO node_resets (session_id, node_id, reset_at) VALUES (?, ?, ?)",
                    (session_id, node_id, time.time())
                )
                self._conn.commit()
        except sqlite3.Error as e:
            log.error("log_node_reset failed: %s", e)
            self.record_error(datetime.now(timezone.utc).isoformat(), "log_node_reset", str(e))

    def log_overflow(self, node_id: int, seq, reason: str,
                     grams: float, window_open_ts=None) -> None:
        VALID = {
            'ANOMALY_DELTA', 'ANOMALY_CLR', 'DISTURBANCE_CLR',
            'ABANDONED_WINDOW', 'ABANDONED_BOUNDARY', 'RESIDUE'
        }
        if reason not in VALID:
            raise ValueError(f"Unknown overflow reason: {reason}")
        if grams <= 0:
            return
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT INTO overflow_events "
                    "(ts, node_id, seq, reason, grams, window_open_ts) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (time.time(), node_id, seq, reason, grams, window_open_ts)
                )
                self._conn.commit()
        except sqlite3.Error as e:
            log.error("log_overflow failed: %s", e)
            self.record_error(datetime.now(timezone.utc).isoformat(), "log_overflow", str(e))

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

    def get_resumable_session(self) -> dict | None:
        """Return the most recent unclosed session with its glass counts.
        WHY: unclosed session (ended_at IS NULL) means service was killed mid-game.
        Returns None if no resumable session exists."""
        try:
            with self._lock:
                row = self._conn.execute(
                    "SELECT id FROM sessions "
                    "WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if not row:
                    return None
                session_id = row[0]
                counts = self._conn.execute(
                    """
                    SELECT pe.node_id, SUM(pe.glasses_counted)
                    FROM pour_events pe
                    LEFT JOIN (
                        SELECT node_id, MAX(reset_at) AS last_reset
                        FROM node_resets
                        WHERE session_id = ?
                        GROUP BY node_id
                    ) nr ON nr.node_id = pe.node_id
                    WHERE pe.session_id = ?
                      AND pe.event_time > COALESCE(nr.last_reset, 0)
                    GROUP BY pe.node_id
                    """,
                    (session_id, session_id)
                ).fetchall()
                glass_counts = {r[0]: int(r[1]) for r in counts if r[1] is not None}
                return {"session_id": session_id, "glass_counts": glass_counts}
        except sqlite3.Error as e:
            log.error("get_resumable_session failed: %s", e)
            return None

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
