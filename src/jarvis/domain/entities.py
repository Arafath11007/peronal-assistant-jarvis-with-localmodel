"""Domain entities and value objects for Jarvis.

This module contains pure data representations independent of database or HTTP frameworks.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class Message:
    """Represents a chat message within a session."""
    role: str
    content: str


@dataclass
class SessionSummary:
    """Summary of a chat session for listing views."""
    id: str
    title: str
    updated_at: str
    message_count: int


@dataclass
class StreamStats:
    """Performance metrics for token streaming."""
    first_token_s: float | None = None
    total_s: float = 0.0
    chunks: int = 0
    completion_tokens: int | None = None

    def summary(self) -> str:
        n = self.completion_tokens or self.chunks
        tps = n / self.total_s if self.total_s > 0 and n else 0.0
        first = f"{self.first_token_s:.1f}s" if self.first_token_s is not None else "n/a"
        return f"first token {first} | {n} tokens | {tps:.1f} tok/s overall"
