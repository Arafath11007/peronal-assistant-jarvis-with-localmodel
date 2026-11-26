"""OpenAI-compatible LLM adapter implementing LLMProviderPort."""

import time
from typing import AsyncIterator, Literal

from openai import AsyncOpenAI

from jarvis.config import settings
from jarvis.domain.entities import StreamStats
from jarvis.domain.think_stripper import ThinkStripper


class OpenAICompatibleLLMAdapter:
    """Asynchronous client for interacting with OpenAI-compatible LLM servers (Ollama, vLLM, etc.)."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self._client = AsyncOpenAI(
            base_url=base_url or settings.llm_base_url,
            api_key=api_key or settings.llm_api_key,
            timeout=timeout or settings.llm_timeout_s,
            max_retries=0,
        )

    @staticmethod
    def model_for(tier: Literal["fast", "smart"]) -> str:
        return settings.fast_model if tier == "fast" else settings.smart_model

    @staticmethod
    def _prepare(messages: list[dict], model: str, think: bool) -> list[dict]:
        return [dict(m) for m in messages]

    async def stream(
        self,
        messages: list[dict],
        tier: Literal["fast", "smart"] = "fast",
        think: bool = False,
        stats: StreamStats | None = None,
        tools: list[dict] | None = None,
    ) -> AsyncIterator[dict]:
        """Stream generated response tokens and tool calls asynchronously."""
        model = self.model_for(tier)
        stats = stats if stats is not None else StreamStats()
        stripper = ThinkStripper()
        started = False
        t0 = time.perf_counter()
        tool_call_acc: dict[int, dict] = {}

        kwargs = {
            "model": model,
            "messages": self._prepare(messages, model, think),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = tools

        try:
            resp = await self._client.chat.completions.create(**kwargs)
            async for chunk in resp:
                if chunk.usage:
                    stats.completion_tokens = chunk.usage.completion_tokens
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_call_acc:
                            tool_call_acc[idx] = {
                                "id": tc.id or f"call_{idx}",
                                "name": tc.function.name or "",
                                "arguments": "",
                            }
                        if tc.function.name:
                            tool_call_acc[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_call_acc[idx]["arguments"] += tc.function.arguments

                content = delta.content or ""
                if content:
                    piece = stripper.feed(content)
                    if not started:
                        piece = piece.lstrip()
                    if piece:
                        if not started:
                            started = True
                            stats.first_token_s = time.perf_counter() - t0
                        stats.chunks += 1
                        yield {"type": "token", "content": piece}

            tail = stripper.flush()
            tail = tail if started else tail.lstrip()
            if tail:
                yield {"type": "token", "content": tail}

            for call in tool_call_acc.values():
                yield {"type": "tool_call", **call}

        finally:
            stats.total_s = time.perf_counter() - t0


# Default alias
LLMClient = OpenAICompatibleLLMAdapter
