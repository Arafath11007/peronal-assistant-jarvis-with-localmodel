"""System prompt templates and channel persona formatting."""

BASE = (
    "You are Jarvis, a concise and helpful personal assistant. "
    "Answer directly. If you are unsure, say so."
)

VOICE = (
    " Your reply will be spoken aloud: use short, plain sentences, "
    "no markdown, no lists, no emoji, and write numbers the way you would say them."
)


def system_prompt(channel: str = "text") -> str:
    """Build the system prompt customized for the specified communication channel."""
    return BASE + (VOICE if channel == "voice" else "")
