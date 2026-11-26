"""SQLite persistence adapter implementing StorePort."""

import sqlite3
import uuid
from pathlib import Path

from jarvis.config import settings

NOW = "strftime('%Y-%m-%d %H:%M:%f','now')"

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at TEXT NOT NULL DEFAULT ({NOW}),
    updated_at TEXT NOT NULL DEFAULT ({NOW})
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT ({NOW})
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
"""


class SQLiteStoreAdapter:
    """Persistent storage engine for conversation history using SQLite."""

    def __init__(self, path: str | None = None) -> None:
        path = path or settings.db_path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex[:8]

    def exists(self, session_id: str) -> bool:
        row = self.db.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return row is not None

    def new_session(self) -> str:
        sid = self.new_id()
        with self.db:
            self.db.execute("INSERT INTO sessions (id) VALUES (?)", (sid,))
        return sid

    def latest_session(self) -> str | None:
        row = self.db.execute(
            "SELECT id FROM sessions ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        return row["id"] if row else None

    def find_session(self, prefix: str) -> str | None:
        rows = self.db.execute(
            "SELECT id FROM sessions WHERE substr(id, 1, ?) = ?", (len(prefix), prefix)
        ).fetchall()
        return rows[0]["id"] if len(rows) == 1 else None

    def add_turn(self, session_id: str, user: str, assistant: str) -> None:
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO sessions (id) VALUES (?)", (session_id,))
            self.db.executemany(
                "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                [(session_id, "user", user), (session_id, "assistant", assistant)],
            )
            self.db.execute(
                f"UPDATE sessions SET updated_at = {NOW}, title = COALESCE(title, ?) WHERE id = ?",
                (user[:40], session_id),
            )

    def messages(self, session_id: str) -> list[dict]:
        rows = self.db.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_session(self, session_id: str) -> bool:
        with self.db:
            cursor = self.db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return cursor.rowcount > 0

    def rename_session(self, session_id: str, new_title: str) -> bool:
        with self.db:
            cursor = self.db.execute(
                f"UPDATE sessions SET title = ?, updated_at = {NOW} WHERE id = ?",
                (new_title.strip()[:100], session_id),
            )
            return cursor.rowcount > 0

    def list_sessions(self, limit: int = 10) -> list[sqlite3.Row]:
        return self.db.execute(
            """
            SELECT s.id, COALESCE(s.title, '(empty)') AS title, s.updated_at,
                   (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS n
            FROM sessions s ORDER BY s.updated_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()


# Alias for backward compatibility
Store = SQLiteStoreAdapter
