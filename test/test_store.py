from jarvis.store import Store


def test_turns_persist_in_order():
    s = Store(":memory:")
    sid = s.new_session()
    s.add_turn(sid, "hi", "hello")
    s.add_turn(sid, "how are you", "fine")
    assert [m["content"] for m in s.messages(sid)] == ["hi", "hello", "how are you", "fine"]
    assert s.latest_session() == sid


def test_title_comes_from_first_message_only():
    s = Store(":memory:")
    sid = s.new_session()
    s.add_turn(sid, "first question", "a")
    s.add_turn(sid, "second question", "b")
    assert s.list_sessions()[0]["title"] == "first question"


def test_find_session_by_prefix():
    s = Store(":memory:")
    sid = s.new_session()
    assert s.find_session(sid[:4]) == sid
    assert s.find_session("zzzz") is None