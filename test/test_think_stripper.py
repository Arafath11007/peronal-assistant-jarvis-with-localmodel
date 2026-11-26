from jarvis.llm import ThinkStripper


def run(chunks):
    s = ThinkStripper()
    return "".join(s.feed(c) for c in chunks) + s.flush()


def test_plain_text():
    assert run(["hel", "lo"]) == "hello"


def test_think_block_removed():
    assert run(["<think>secret</think>hi"]) == "hi"


def test_tags_split_across_chunks():
    assert run(["<th", "ink>sec", "ret</thi", "nk>hi"]) == "hi"


def test_partial_tag_that_is_not_a_tag():
    assert run(["a <", "b"]) == "a <b"