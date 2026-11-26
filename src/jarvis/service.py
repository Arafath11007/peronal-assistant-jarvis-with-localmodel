"""Core chat orchestration and concurrency management service.

This module provides `ChatService`, which ties together:
1. Session persistence (`Store`)
2. Context window budgeting (`fit_to_budget`)
3. Prompt engineering (`system_prompt`)
4. Streaming LLM client (`LLMClient`)
5. Safe concurrency controls:
   - Per-session async locks (`_session_locks`) to prevent race conditions on chat turns.
   - Global concurrency semaphore (`_gate`) to throttle local LLM load and prevent CPU/GPU thrashing.

Example:
    ```python
    import asyncio
    from jarvis.store import Store
    from jarvis.llm import LLMClient
    from jarvis.service import ChatService

    async def main():
        service = ChatService(Store(":memory:"), LLMClient())
        async for event in service.chat("Hello Jarvis!", channel="text"):
            if event["event"] == "token":
                print(event["data"]["text"], end="")
            elif event["event"] == "done":
                print(f"\\nFinished session {event['data']['session_id']}")

    asyncio.run(main())
    ```
"""

import asyncio
from typing import AsyncIterator

from jarvis.config import settings
from jarvis.context import fit_to_budget
from jarvis.llm import LLMClient, StreamStats
from jarvis.prompts import system_prompt
from jarvis.store import Store


class ChatService:
    """Coordinates chat interactions, history truncation, concurrency, and persistence."""

    def __init__(self, store: Store, llm: LLMClient) -> None:
        """Initialize the ChatService with dependencies.

        Args:
            store: The persistence store for message history and sessions.
            llm: The LLM client for streaming text generations.
        """
        self.store = store
        self.llm = llm
        # Semaphore limits how many concurrent calls can actively query the LLM
        self._gate = asyncio.Semaphore(settings.max_parallel_generations)
        # Dictionary of locks guaranteeing serialized turns per individual session
        self._session_locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, sid: str) -> asyncio.Lock:
        """Get or create an asyncio.Lock specific to a given session ID.

        Args:
            sid: Session identifier string.

        Returns:
            An asyncio.Lock instance guarding this session.
        """
        return self._session_locks.setdefault(sid, asyncio.Lock())

    async def chat(
        self,
        message: str,
        session_id: str | None = None,
        channel: str = "text",
        tier: str = "fast",
    ) -> AsyncIterator[dict]:
        """Execute a full conversational turn with streaming responses and event publishing.

        Events yielded:
        - `{"event": "status", "data": {"state": "queued"|"thinking", "session_id": str}}`
        - `{"event": "token", "data": {"text": str}}`
        - `{"event": "done", "data": {"session_id": str, "trimmed": int, ...}}`
        - `{"event": "error", "data": {"message": str}}`

        Args:
            message: User prompt string.
            session_id: Optional existing session ID. If None, a new ID is generated.
            channel: 'text' or 'voice' (determines prompt persona).
            tier: 'fast' or 'smart' model selection.

        Yields:
            Dictionary event objects suited for SSE (Server-Sent Events) or frontend ingestion.
        """
        sid = session_id or self.store.new_id()

        # Step 1: Acquire session-specific lock so multiple messages in the same session don't interleave
        async with self._lock_for(sid):
            # Step 2: Retrieve existing conversation history from the store
            history = self.store.messages(sid)
            user_msg = {"role": "user", "content": message}

            # Step 3: Trim history to fit comfortably within the LLM's context token window
            messages = fit_to_budget(system_prompt(channel), [*history, user_msg])
            trimmed = len(history) + 1 - (len(messages) - 1)

            # Step 4: Manage global LLM generation concurrency gate
            if self._gate.locked():
                yield {"event": "status", "data": {"state": "queued", "session_id": sid}}
            async with self._gate:
                yield {"event": "status", "data": {"state": "thinking", "session_id": sid}}
                stats = StreamStats()
                parts: list[str] = []

                # Step 5: Stream generated tokens from the LLM
                async for piece in self.llm.stream(messages, tier=tier, stats=stats):
                    parts.append(piece)
                    yield {"event": "token", "data": {"text": piece}}

            reply = "".join(parts)
            # Step 6: Validate output
            if not reply.strip():
                yield {"event": "error", "data": {"message": "The model returned an empty reply."}}
                return

            # Step 7: Atomically save the user query and complete assistant reply
            self.store.add_turn(sid, message, reply)

            # Step 8: Signal completion with telemetry
            yield {
                "event": "done",
                "data": {
                    "session_id": sid,
                    "trimmed": trimmed,
                    "first_token_s": stats.first_token_s,
                    "total_s": round(stats.total_s, 2),
                    "tokens": stats.completion_tokens or stats.chunks,
                },
            }
