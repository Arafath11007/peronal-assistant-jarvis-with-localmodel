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
from jarvis.tools import run_tool, schemas


class ChatService:
    """Coordinates chat interactions, history truncation, tool execution, and persistence."""

    def __init__(self, store: Store, llm: LLMClient) -> None:
        """Initialize the ChatService with dependencies."""
        self.store = store
        self.llm = llm
        self._gate = asyncio.Semaphore(settings.max_parallel_generations)
        self._session_locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, sid: str) -> asyncio.Lock:
        return self._session_locks.setdefault(sid, asyncio.Lock())

    async def chat(
        self,
        message: str,
        session_id: str | None = None,
        channel: str = "text",
        tier: str = "fast",
    ) -> AsyncIterator[dict]:
        """Execute a full conversational turn with streaming responses and event publishing."""
        sid = session_id or self.store.new_id()

        async with self._lock_for(sid):
            history = self.store.messages(sid)
            user_msg = {"role": "user", "content": message}
            messages = fit_to_budget(system_prompt(channel), [*history, user_msg])
            trimmed = len(history) + 1 - (len(messages) - 1)

            if self._gate.locked():
                yield {"event": "status", "data": {"state": "queued", "session_id": sid}}
            
            async with self._gate:
                yield {"event": "status", "data": {"state": "thinking", "session_id": sid}}
                stats = StreamStats()
                parts: list[str] = []
                tool_calls: list[dict] = []
                available_tools = schemas()

                # Step 1: Initial LLM Stream call (with tools provided if any exist)
                async for ev in self.llm.stream(
                    messages, tier=tier, stats=stats, tools=available_tools if available_tools else None
                ):
                    if ev["type"] == "token":
                        parts.append(ev["content"])
                        yield {"event": "token", "data": {"text": ev["content"]}}
                    elif ev["type"] == "tool_call":
                        tool_calls.append(ev)

                # Step 2: If model decided to invoke tools, execute them and stream final answer
                if tool_calls:
                    assistant_tool_msg = {
                        "role": "assistant",
                        "content": "".join(parts) or None,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": tc["arguments"],
                                },
                            }
                            for tc in tool_calls
                        ],
                    }
                    messages.append(assistant_tool_msg)

                    for tc in tool_calls:
                        yield {
                            "event": "tool_call",
                            "data": {
                                "id": tc["id"],
                                "name": tc["name"],
                                "arguments": tc["arguments"],
                            },
                        }
                        # Execute registered tool
                        output = run_tool(tc["name"], tc["arguments"])
                        yield {
                            "event": "tool_result",
                            "data": {
                                "id": tc["id"],
                                "name": tc["name"],
                                "output": output,
                            },
                        }
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "name": tc["name"],
                                "content": output,
                            }
                        )

                    # Stream follow-up completion taking tool outputs into account
                    parts = []
                    async for ev in self.llm.stream(messages, tier=tier, stats=stats):
                        if ev["type"] == "token":
                            parts.append(ev["content"])
                            yield {"event": "token", "data": {"text": ev["content"]}}

            reply = "".join(parts)
            if not reply.strip():
                yield {"event": "error", "data": {"message": "The model returned an empty reply."}}
                return

            self.store.add_turn(sid, message, reply)

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
