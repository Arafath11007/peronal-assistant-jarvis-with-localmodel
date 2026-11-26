from jarvis.context import fit_to_budget


def convo(turns, size=300):
    out = []
    for _ in range(turns):
        out.append({"role": "user", "content": "u" * size})
        out.append({"role": "assistant", "content": "a" * size})
    return out


def test_short_history_kept_whole():
    h = convo(2)
    out = fit_to_budget("sys", h, budget=4000)
    assert out[0]["role"] == "system"
    assert out[1:] == h


def test_oldest_dropped_first_and_never_starts_on_assistant():
    h = convo(10)
    out = fit_to_budget("sys", h, budget=400)
    assert out[-1] == h[-1]          # newest survives
    assert len(out) - 1 < len(h)     # something was dropped
    assert out[1]["role"] == "user"  # window starts on a user turn


def test_newest_message_kept_even_if_huge():
    h = [{"role": "user", "content": "x" * 50_000}]
    out = fit_to_budget("sys", h, budget=100)
    assert out[-1] == h[0]