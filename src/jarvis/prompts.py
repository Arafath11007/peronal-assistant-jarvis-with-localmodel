"""System prompts and channel adaptations for Jarvis.

This module provides system instructions that shape the persona and behavior
of the assistant across different output channels (e.g. text vs voice).

Channels:
- text: Standard conversational assistant. Output can contain punctuation, markdown, etc.
- voice: Formatted for Text-To-Speech (TTS). Output uses simple phrasing, avoids markdown,
         emojis, bullet points, and formats numbers as spoken words.

Example:
    ```python
    from jarvis.prompts import system_prompt

    prompt_text = system_prompt("text")
    prompt_voice = system_prompt("voice")
    ```
"""

BASE = (
    "You are Jarvis, a concise and helpful personal assistant. "
    "Answer directly. If you are unsure, say so."
)

VOICE = (
    " Your reply will be spoken aloud: use short, plain sentences, "
    "no markdown, no lists, no emoji, and write numbers the way you would say them."
)


def system_prompt(channel: str = "text") -> str:
    """Build the system prompt customized for the specified communication channel.

    Args:
        channel: The output modality. Can be 'text' or 'voice'.

    Returns:
        A formatted system prompt string.

    Example:
        >>> system_prompt("voice")
        'You are Jarvis, a concise and helpful personal assistant. Answer directly. ...'
    """
    return BASE + (VOICE if channel == "voice" else "")
