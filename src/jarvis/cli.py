"""Command-line interface (CLI) for chatting with Jarvis directly in the terminal.

Features:
- Live streaming output directly in the console.
- An animated spinner showing real-time elapsed time while waiting for initial tokens.
- Automatic resume of the most recent session upon launch.
- Interactive slash commands:
    `/new`         : Start a fresh conversation session.
    `/sessions`    : List past conversation sessions with turn counts and timestamps.
    `/resume <id>` : Resume a specific past conversation by ID or ID prefix.
    `/quit`        : Exit the application.
- Real-time generation statistics (TTFT, token speed, history trimming).

Usage:
    ```bash
    # Run the interactive CLI:
    python -m jarvis.cli
    ```
"""

import asyncio
import itertools
import sys
import time

from jarvis.context import fit_to_budget
from jarvis.llm import LLMClient, StreamStats
from jarvis.prompts import system_prompt
from jarvis.store import Store

# Default system prompt for text channel interaction
SYSTEM_PROMPT = system_prompt("text")


class Spinner:
    """Terminal spinner animation with elapsed time counter running as an asyncio background task.

    Example:
        ```python
        spinner = Spinner("Thinking")
        spinner.start()
        # do async work...
        await spinner.stop()
        ```
    """

    FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, label: str = "Jarvis is thinking") -> None:
        """Initialize the spinner with a custom status label.

        Args:
            label: Text displayed alongside the spinning animation frames.
        """
        self.label = label
        self._task: asyncio.Task | None = None

    async def _spin(self) -> None:
        """Internal loop updating the terminal line with current frame and elapsed seconds."""
        t0 = time.perf_counter()
        for frame in itertools.cycle(self.FRAMES):
            elapsed = time.perf_counter() - t0
            sys.stdout.write(f"\r{frame} {self.label}... {elapsed:.0f}s")
            sys.stdout.flush()
            await asyncio.sleep(0.1)

    def start(self) -> None:
        """Launch the spinner background task."""
        self._task = asyncio.create_task(self._spin())

    async def stop(self) -> None:
        """Stop the spinner and clear the current console line."""
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
            # ANSI escape \r\033[K moves cursor to start of line and clears it
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()


async def main() -> None:
    """Main interactive REPL (Read-Eval-Print Loop) for the Jarvis CLI."""
    llm = LLMClient()
    store = Store()

    # Automatically reconnect to the latest conversation session if one exists
    session_id = store.latest_session()
    history = store.messages(session_id) if session_id else []
    if session_id:
        print(f"Resumed session {session_id} ({len(history) // 2} turns).")
    print("Commands: /new  /sessions  /resume <id>  /quit")

    while True:
        try:
            user = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            # Graceful exit on Ctrl+C or Ctrl+D
            break
        if not user:
            continue

        # Handle commands
        if user == "/quit":
            break
        if user == "/new":
            session_id, history = None, []  # A new row is lazily created upon first reply
            print("Started a new session.")
            continue
        if user == "/sessions":
            for s in store.list_sessions():
                mark = "*" if s["id"] == session_id else " "
                print(f"{mark} {s['id']}  {s['updated_at'][:16]}  {s['n'] // 2:>3} turns  {s['title']}")
            continue
        if user.startswith("/resume"):
            found = store.find_session(user.removeprefix("/resume").strip())
            if not found:
                print("No unique session matches that id. Use /sessions.")
                continue
            session_id, history = found, store.messages(found)
            print(f"Resumed session {found} ({len(history) // 2} turns).")
            continue

        # Prepare messages fitted to context window limits
        user_msg = {"role": "user", "content": user}
        messages = fit_to_budget(SYSTEM_PROMPT, [*history, user_msg])
        dropped = len(history) + 1 - (len(messages) - 1)

        # Stream response with animated spinner
        stats = StreamStats()
        parts: list[str] = []
        spinner = Spinner()
        spinner.start()
        try:
            async for piece in llm.stream(messages, stats=stats):
                if not parts:
                    # Stop spinner as soon as the first token arrives
                    await spinner.stop()
                    print("jarvis> ", end="", flush=True)
                print(piece, end="", flush=True)
                parts.append(piece)
        except Exception as e:
            await spinner.stop()
            print(f"[error: {e}]")
            continue
        finally:
            await spinner.stop()

        reply = "".join(parts)
        # Create a new session row if this was a new conversation
        if session_id is None:
            session_id = store.new_session()
        # Persist the turn into SQLite
        store.add_turn(session_id, user, reply)
        history += [user_msg, {"role": "assistant", "content": reply}]

        # Display generation performance summary
        note = f" | trimmed {dropped} old msgs" if dropped else ""
        print(f"\n[{stats.summary()}{note}]")


if __name__ == "__main__":
    asyncio.run(main())
