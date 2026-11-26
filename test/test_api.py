import json

from fastapi.testclient import TestClient

from jarvis.api import create_app
from jarvis.store import Store


class FakeLLM:
    async def stream(self, messages, tier="fast", think=False, stats=None):
        for piece in ["Hel", "lo ", "there"]:
            yield piece
        if stats is not None:
            stats.chunks = 3
            stats.total_s = 0.01


def parse_sse(lines):
    events, name = [], None
    for line in lines:
        if line.startswith("event: "):
            name = line[7:]
        elif line.startswith("data: "):
            events.append((name, json.loads(line[6:])))
    return events


def chat(client, **body):
    with client.stream("POST", "/chat", json=body) as r:
        assert r.status_code == 200
        return parse_sse(list(r.iter_lines()))


def make_client():
    return TestClient(create_app(store=Store(":memory:"), llm=FakeLLM()))


def test_chat_streams_and_persists():
    with make_client() as c:
        events = chat(c, message="hi")
        names = [n for n, _ in events]
        assert names[0] == "status" and names[-1] == "done"
        assert "".join(d["text"] for n, d in events if n == "token") == "Hello there"
        sid = events[-1][1]["session_id"]
        roles = [m["role"] for m in c.get(f"/sessions/{sid}/messages").json()]
        assert roles == ["user", "assistant"]


def test_session_continues():
    with make_client() as c:
        sid = chat(c, message="one")[-1][1]["session_id"]
        chat(c, message="two", session_id=sid)
        assert len(c.get(f"/sessions/{sid}/messages").json()) == 4


def test_unknown_session_is_404():
    with make_client() as c:
        r = c.post("/chat", json={"message": "x", "session_id": "nope"})
        assert r.status_code == 404

def test_index_page_served():
    with make_client() as c:
        r = c.get("/")
        assert r.status_code == 200
        assert "Jarvis" in r.text