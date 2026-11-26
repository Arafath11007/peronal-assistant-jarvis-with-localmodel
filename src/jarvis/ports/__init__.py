"""Abstract Ports (interfaces) for Jarvis.

Ports define the contracts that outside adapters (database, LLM, tools) must satisfy.
"""

from typing import AsyncIterator, Literal, Protocol, runtime_checkable
from jarvis.domain.entities import StreamStats


@runtime_checkable
class StorePort(Protocol):
    """Persistence contract for conversation sessions and messages."""

    def new_id(self) -> str:
        ...

    def exists(self, session_id: str) -> bool:
        ...

    def new_session(self) -> str:
        ...

    def latest_session(self) -> str | None:
        ...

    def find_session(self, prefix: str) -> str | None:
        ...

    def add_turn(self, session_id: str, user: str, assistant: str) -> None:
        ...

    def messages(self, session_id: str) -> list[dict]:
        ...

    def list_sessions(self, limit: int = 10) -> list:
        ...

    def delete_session(self, session_id: str) -> bool:
        ...

    def rename_session(self, session_id: str, new_title: str) -> bool:
        ...


@runtime_checkable
class LLMProviderPort(Protocol):
    """Contract for streaming completions from LLM backends."""

    def stream(
        self,
        messages: list[dict],
        tier: Literal["fast", "smart"] = "fast",
        think: bool = False,
        stats: StreamStats | None = None,
        tools: list[dict] | None = None,
    ) -> AsyncIterator[dict]:
        ...
