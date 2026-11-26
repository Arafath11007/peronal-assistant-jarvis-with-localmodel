import inspect
import json
from dataclasses import dataclass
from typing import Annotated, Callable, get_args, get_origin, get_type_hints

PY_TO_JSON = {str: "string", int: "integer", float: "number", bool: "boolean"}
MAX_OUTPUT_CHARS = 2000


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    func: Callable


REGISTRY: dict[str, Tool] = {}


def tool(func: Callable) -> Callable:
    hints = get_type_hints(func, include_extras=True)
    properties = {}
    required = []

    for pname, param in inspect.signature(func).parameters.items():
        hint = hints[pname]
        description = None
        if get_origin(hint) is Annotated:
            hint, description = get_args(hint)[0], get_args(hint)[1]

        properties[pname] = {"type": PY_TO_JSON[hint]}
        if description:
            properties[pname]["description"] = description
        if param.default is inspect.Parameter.empty:
            required.append(pname)

    REGISTRY[func.__name__] = Tool(
        name=func.__name__,
        description=inspect.getdoc(func) or "",
        parameters={"type": "object", "properties": properties, "required": required},
        func=func,
    )
    return func


def schemas() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in REGISTRY.values()
    ]


"""
REGISTRY.get(name) looks up the tool like REGISTRY[name] did, but returns None when the name isn't found instead of crashing. We check for that on the next line and return a helpful message that lists the valid tool names, which gives the model what it needs to pick a correct one.
try / except Exception as e is the same idea as PHP's try { } catch (Exception $e) { }. If anything inside the try block fails, Python jumps to the except block with the error in e, instead of crashing.
type(e).__name__ is the error's class name, such as TypeError or JSONDecodeError. Together with e (the error's message), it tells the model what went wrong.
raw_args or "{}" means "if the argument text is empty, use {} instead." Some tools take no arguments, and a model may send an empty string for them. This is what the boom test checks.
The json.loads and the tool call are both inside the same try. One except catches broken JSON, missing or unexpected arguments (Python raises TypeError for those by itself), and errors raised inside the tool.
"""
def run_tool(name: str, raw_args: str) -> str:
    t = REGISTRY.get(name)
    if t is None:
        return f"Error: unknown tool '{name}'. Available tools: {', '.join(REGISTRY)}"
    try:
        args = json.loads(raw_args or "{}")
        result = t.func(**args)
    except Exception as e:
        return f"Error running {name}: {type(e).__name__}: {e}"
    return str(result)
