"""Token budgeting and history window truncation."""

CHARS_PER_TOKEN = 3.0


def estimate_token(text: str) -> int:
    """Estimate token count for a text snippet with safety overhead."""
    return int(len(text) / CHARS_PER_TOKEN) + 4


def fit_to_budget(
    system_prompt: str, history: list[dict], budget: int
) -> list[dict]:
    """Fit conversation history within a specified token budget."""
    remaining = budget - estimate_token(system_prompt)

    kept: list[dict] = []
    for msg in reversed(history):
        cost = estimate_token(msg["content"])
        if kept and cost > remaining:
            break
        kept.append(msg)
        remaining -= cost
    kept.reverse()

    while len(kept) > 1 and kept[0]["role"] != "user":
        kept.pop(0)

    return [{"role": "system", "content": system_prompt}, *kept]
