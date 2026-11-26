"""Standard built-in utility tools for Jarvis.

Provides out-of-the-box functions that Jarvis can invoke:
1. `calculate`: Safe mathematical expression evaluation.
2. `current_time`: Get current local date, time, and timezone.
3. `search_wikipedia`: Quick summary lookup from Wikipedia.
"""

import datetime
import math
import urllib.parse
import urllib.request
import json
from typing import Annotated

from jarvis.tools.registry import tool


@tool
def calculate(expression: Annotated[str, "The mathematical expression to evaluate, e.g. '25 * 4 + sqrt(144)'"]) -> str:
    """Safely calculate the result of a mathematical expression."""
    # Allow safe mathematical functions only
    allowed_names = {
        k: v for k, v in math.__dict__.items() if not k.startswith("__")
    }
    allowed_names.update({
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "pow": pow,
    })
    try:
        # Strip dangerous characters
        cleaned = expression.strip().replace("^", "**")
        code = compile(cleaned, "<string>", "eval")
        for name in code.co_names:
            if name not in allowed_names:
                return f"Error: function or variable '{name}' is not allowed."
        result = eval(code, {"__builtins__": {}}, allowed_names)
        return str(result)
    except Exception as e:
        return f"Calculation error: {e}"


@tool
def current_time(timezone_name: Annotated[str, "Optional timezone descriptor or 'local'"] = "local") -> str:
    """Get the current date and local time."""
    now = datetime.datetime.now()
    return now.strftime("%A, %B %d, %Y at %I:%M:%S %p")


@tool
def wikipedia_summary(query: Annotated[str, "Topic or entity to look up on Wikipedia"]) -> str:
    """Look up a brief factual summary of a topic on Wikipedia."""
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "JarvisAssistant/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                extract = data.get("extract")
                if extract:
                    return extract
        return f"No summary found for '{query}'."
    except Exception as e:
        return f"Lookup error: {e}"
