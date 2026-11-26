import json
import pytest
from jarvis.llm import LLMClient
from jarvis.service import ChatService
from jarvis.store import Store
from jarvis.tools.registry import tool, REGISTRY


class ToolMockLLM:
    """Simulates an LLM calling a tool on the first pass and synthesizing an answer on the second pass."""

    def __init__(self):
        self.call_count = 0

    async def stream(self, messages, tier="fast", think=False, stats=None, tools=None):
        self.call_count += 1
        if self.call_count == 1:
            # Emit a tool call to 'multiply'
            yield {
                "type": "tool_call",
                "id": "call_123",
                "name": "multiply",
                "arguments": json.dumps({"x": 6, "y": 7}),
            }
        else:
            # Model receives tool response and answers user
            for chunk in ["The ", "result ", "is ", "42."]:
                yield {"type": "token", "content": chunk}


@tool
def multiply(x: int, y: int) -> str:
    """Multiply two integers."""
    return str(x * y)


@pytest.mark.anyio
async def test_tool_calling_flow_in_service():
    store = Store(":memory:")
    mock_llm = ToolMockLLM()
    service = ChatService(store=store, llm=mock_llm)

    events = []
    async for ev in service.chat("What is 6 * 7?"):
        events.append(ev)

    event_types = [e["event"] for e in events]
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "token" in event_types
    assert "done" in event_types

    # Validate tool call event data
    tc_event = next(e for e in events if e["event"] == "tool_call")
    assert tc_event["data"]["name"] == "multiply"

    # Validate tool result event data
    tr_event = next(e for e in events if e["event"] == "tool_result")
    assert tr_event["data"]["output"] == "42"

    # Validate assembled final reply in DB
    sid = events[-1]["data"]["session_id"]
    messages = store.messages(sid)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "The result is 42."
