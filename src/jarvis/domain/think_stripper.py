"""Stateful streaming filter for reasoning tags.

Strips `<think>...</think>` from an incoming text stream even when tags are split across chunks.
"""


class ThinkStripper:
    """Removes `<think>...</think>` sections from a token stream in real-time."""

    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self) -> None:
        self.buf = ""
        self.inside = False

    def feed(self, text: str) -> str:
        """Feed a new chunk of streamed text and return printable text with thinking tags stripped."""
        self.buf += text
        out: list[str] = []
        while True:
            tag = self.CLOSE if self.inside else self.OPEN
            i = self.buf.find(tag)
            if i != -1:
                if not self.inside:
                    out.append(self.buf[:i])
                self.buf = self.buf[i + len(tag) :]
                self.inside = not self.inside
                continue

            keep = 0
            for k in range(min(len(tag) - 1, len(self.buf)), 0, -1):
                if tag.startswith(self.buf[-k:]):
                    keep = k
                    break
            cut = len(self.buf) - keep
            if not self.inside:
                out.append(self.buf[:cut])
            self.buf = self.buf[cut:]
            break
        return "".join(out)

    def flush(self) -> str:
        """Flush remaining buffered text once generation finishes."""
        rest = "" if self.inside else self.buf
        self.buf = ""
        return rest
