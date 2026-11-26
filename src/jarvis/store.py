"""SQLite persistence layer for Jarvis sessions and messages.

This module provides thread-safe access to SQLite to manage:
1. `sessions`: Metadata about conversation threads (ID, title, timestamps).
2. `messages`: Chronological chat messages linked by foreign key with cascade deletion.

Design Highlights:
- Uses SQLite WAL mode / check_same_thread=False for async/multi-thread compatibility.
- Uses transactions (`with self.db:`) to ensure turn additions are atomic.
- Automatically assigns an auto-truncated title (first 40 characters of initial message).
- Short session IDs (8 hex characters) for easy copy-pasting in CLI and URLs.

Example:
    ```python
    from jarvis.store import Store

    store = Store(":memory:")  # In-memory database for testing
    session_id = store.new_session()
    store.add_turn(session_id, user="Hello!", assistant="Hi there!")

    messages = store.messages(session_id)
    print(messages)
    # [{'role': 'user', 'content': 'Hello!'}, {'role': 'assistant', 'content': 'Hi there!'}]
    ```
"""

import sqlite3
import uuid
from pathlib import Path

from jarvis.config import settings

# SQLite function string to produce formatted UTC timestamps
NOW = "strftime('%Y-%m-%d %H:%M:%f','now')"

# Database schema definitions
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


class Store:
    """Persistent storage engine for conversation history using SQLite."""

    def __init__(self, path: str | None = None) -> None:
        """Initialize SQLite connection and apply table schemas.

        Args:
            path: Path to the SQLite database file, or ':memory:' for transient test storage.
                  If omitted, defaults to `settings.db_path`.
        """
        path = path or settings.db_path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)

    @staticmethod
    def new_id() -> str:
        """Generate a compact 8-character random hexadecimal identifier.

        Returns:
            An 8-character string (e.g. 'a3f89b1c').
        """
        return uuid.uuid4().hex[:8]

    def exists(self, session_id: str) -> bool:
        """Check whether a session with the given ID exists.

        Args:
            session_id: The session ID to check.

        Returns:
            True if the session exists in the database, False otherwise.
        """
        row = self.db.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return row is not None

    def new_session(self) -> str:
        """Create and persist a new empty session row.

        Returns:
            The generated unique session ID string.
        """
        sid = self.new_id()
        with self.db:
            self.db.execute("INSERT INTO sessions (id) VALUES (?)", (sid,))
        return sid

    def latest_session(self) -> str | None:
        """Retrieve the ID of the most recently updated session.

        Returns:
            The session ID string if any sessions exist, otherwise None.
        """
        row = self.db.execute(
            "SELECT id FROM sessions ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        return row["id"] if row else None

    def find_session(self, prefix: str) -> str | None:
        """Find a single session matching a given ID prefix (e.g., shorthand CLI resumes).

        Args:
            prefix: Substring or prefix of the session ID.

        Returns:
            The full session ID if exactly one matching session is found, else None.
        """
        rows = self.db.execute(
            "SELECT id FROM sessions WHERE substr(id, 1, ?) = ?", (len(prefix), prefix)
        ).fetchall()
        return rows[0]["id"] if len(rows) == 1 else None

    def add_turn(self, session_id: str, user: str, assistant: str) -> None:
        """Save a single user/assistant exchange atomically within a transaction.

        If the session record does not already exist, it is created.
        If the session does not have a title, the first 40 characters of the user message
        are used as the session title.

        Args:
            session_id: Unique identifier of the session.
            user: Text of the user's message.
            assistant: Text of the assistant's reply.

        Example:
            >>> store.add_turn("a1b2c3d4", "What is Python?", "Python is a programming language.")
        """
        with self.db:
            # Ensure the parent session exists before inserting messages
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
        """Fetch all historical messages for a session in chronological order.

        Args:
            session_id: The session ID to fetch history for.

        Returns:
            List of dicts formatted with 'role' and 'content' keys.

        Example:
            >>> store.messages("a1b2c3d4")
            [{'role': 'user', 'content': 'Hi'}, {'role': 'assistant', 'content': 'Hello!'}]
        """
        rows = self.db.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages (via ON DELETE CASCADE).

        Args:
            session_id: The session ID to delete.

        Returns:
            True if a session was deleted, False if it was not found.
        """
        with self.db:
            cursor = self.db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return cursor.rowcount > 0

    def rename_session(self, session_id: str, new_title: str) -> bool:
        """Update the title of a specific session.

        Args:
            session_id: The session ID to rename.
            new_title: The new title string.

        Returns:
            True if updated, False if session not found.
        """
        with self.db:
            cursor = self.db.execute(
                f"UPDATE sessions SET title = ?, updated_at = {NOW} WHERE id = ?",
                (new_title.strip()[:100], session_id),
            )
            return cursor.rowcount > 0

    def list_sessions(self, limit: int = 10) -> list[sqlite3.Row]:
        """List the most recently active sessions with message counts.

        Args:
            limit: Maximum number of sessions to return (default 10).

        Returns:
            List of sqlite3.Row objects with fields: `id`, `title`, `updated_at`, `n` (message count).
        """
        return self.db.execute(
            """
            SELECT s.id, COALESCE(s.title, '(empty)') AS title, s.updated_at,
                   (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS n
            FROM sessions s ORDER BY s.updated_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
