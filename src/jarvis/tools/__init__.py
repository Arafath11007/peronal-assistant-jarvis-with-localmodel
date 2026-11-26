"""Jarvis tools module.

Auto-imports built-in tools so they are registered in REGISTRY upon import.
"""

from jarvis.tools.registry import REGISTRY, Tool, run_tool, schemas, tool
import jarvis.tools.builtin  # Registers calculate, current_time, wikipedia_summary

__all__ = ["REGISTRY", "Tool", "tool", "schemas", "run_tool"]
