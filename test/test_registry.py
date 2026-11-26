import json
from typing import Annotated

from jarvis.tools.registry import run_tool, schemas, tool


@tool
def add(a: Annotated[int, "first number"], b: int = 0) -> str:
    """Add two integers."""
    return str(a + b)


@tool
def boom() -> str:
    """Always fails."""
    raise RuntimeError("kaboom")


def test_schema_is_generated_from_the_function():
    spec = next(s for s in schemas() if s["function"]["name"] == "add")
    assert spec == {
        "type": "function",
        "function": {
            "name": "add",
            "description": "Add two integers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "integer", "description": "first number"},
                    "b": {"type": "integer"},
                },
                "required": ["a"],
            },
        },
    }


def test_decorated_function_still_works_normally():
    assert add(1, 2) == "3"


def test_run_tool_happy_path():
    
    assert run_tool("add", json.dumps({"a": 2, "b": 3})) == "5"


def test_errors_become_text_the_model_can_read():
    assert "kaboom" in run_tool("boom", "")           # empty args string = no args
    assert run_tool("nope", "{}").startswith("Error")  # unknown tool
    assert run_tool("add", "{not json").startswith("Error")
    assert run_tool("add", '{"a": 1, "zzz": 2}').startswith("Error")  # unexpected argument
    assert run_tool("add", "{}").startswith("Error")   # missing required argument


def test_long_output_is_truncated():
    @tool
    def spam() -> str:
        """Returns a lot of text."""
        return "x" * 10_000

    assert len(run_tool("spam", "{}")) < 2100