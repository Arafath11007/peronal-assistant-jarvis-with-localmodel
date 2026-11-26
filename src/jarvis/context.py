"""Context window budgeting and token estimation for LLM chat history.

Models have a fixed context window (e.g., 4096 tokens). If chat history grows
indefinitely, requests will fail or exceed memory/computation limits.

This module provides:
1. Fast rule-of-thumb token estimation without heavy tokenizer dependencies.
2. Trimming algorithm (`fit_to_budget`) that keeps the system prompt and the
   most recent conversation turns, dropping older messages while preserving valid
   turn alternating structure.

Example:
    ```python
    from jarvis.context import fit_to_budget

    system = "You are a helpful assistant."
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
        {"role": "user", "content": "What is 2+2?"},
    ]

    # Truncates older messages if budget is exceeded
    messages_to_send = fit_to_budget(system, history, budget=500)
    ```
"""

from jarvis.config import settings

# Characters per token heuristic:
# English text typically averages ~4 characters per token.
# Using 3.0 characters/token is conservative: it deliberately overestimates token usage,
# ensuring we never accidentally blow past the model's physical context limit.
CHARS_PER_TOKEN = 3.0


def estimate_token(text: str) -> int:
    """Estimate token count for a text snippet with safety overhead.

    Args:
        text: The text string to estimate.

    Returns:
        Estimated number of tokens including per-message formatting overhead (+4).

    Example:
        >>> estimate_token("Hello world")
        7
    """
    return int(len(text) / CHARS_PER_TOKEN) + 4  # +4 for chat template delimiters


def fit_to_budget(
    system_prompt: str, history: list[dict], budget: int | None = None
) -> list[dict]:
    """Fit conversation history within a specified token budget.

    Guarantees:
    1. Always includes the system prompt at the beginning (`[{"role": "system", ...}]`).
    2. Drops the oldest messages first when history exceeds budget.
    3. Trims leading assistant messages if history starts on one, so the window
       always opens with a user query for natural conversational context.

    Args:
        system_prompt: The base instructions for the assistant.
        history: Chronological list of message dicts: [{"role": "user"|"assistant", "content": str}, ...]
        budget: Maximum token budget. If None, calculated as
                `(settings.context_token - settings.replay_reserve_tokens)`.

    Returns:
        List of message dicts formatted for OpenAI-compatible chat completion endpoints.

    Example:
        >>> fit_to_budget("You are Jarvis", [{"role": "user", "content": "Hi"}], budget=100)
        [{'role': 'system', 'content': 'You are Jarvis'}, {'role': 'user', 'content': 'Hi'}]
    """
    if budget is None:
        budget = settings.context_token - settings.replay_reserve_tokens

    remaining = budget - estimate_token(system_prompt)

    kept: list[dict] = []
    # Walk backwards from the most recent message to preserve newest context
    for msg in reversed(history):
        cost = estimate_token(msg["content"])
        if kept and cost > remaining:
            break
        kept.append(msg)
        remaining -= cost
    kept.reverse()

    # Never start the chat window with an isolated assistant response
    while len(kept) > 1 and kept[0]["role"] != "user":
        kept.pop(0)

    return [{"role": "system", "content": system_prompt}, *kept]
