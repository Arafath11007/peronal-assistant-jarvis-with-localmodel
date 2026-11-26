"""Backward compatibility shims for jarvis modules.

Allows existing code and tests to import from top-level `jarvis.*` without breaking.
"""

from jarvis.domain.context import CHARS_PER_TOKEN, estimate_token, fit_to_budget as _fit_to_budget
from jarvis.config import settings

def fit_to_budget(system_prompt: str, history: list[dict], budget: int | None = None) -> list[dict]:
    if budget is None:
        budget = settings.context_token - settings.replay_reserve_tokens
    return _fit_to_budget(system_prompt, history, budget)

__all__ = ["CHARS_PER_TOKEN", "estimate_token", "fit_to_budget"]
