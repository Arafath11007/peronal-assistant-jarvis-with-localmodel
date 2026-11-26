# Jarvis - Personal AI Assistant (Phase 1)

A fast, lightweight, and robust local personal assistant built in Python. Jarvis connects to OpenAI-compatible local LLM engines (like [Ollama](https://ollama.com/) or vLLM), persists conversation histories with SQLite, manages token budgeting dynamically, and provides an interactive terminal interface (CLI) as well as a streaming Web & REST interface powered by FastAPI (Server-Sent Events).

---

## Features

- **Local LLM Streaming**: Real-time token streaming with performance telemetry (Time-To-First-Token, tokens/sec, total duration).
- **Web UI & SSE Streaming**: Built-in dark-themed web chat interface served directly at `/` using Server-Sent Events (SSE).
- **Reasoning Tag Stripping (`<think>`)**: Real-time state machine that filters internal reasoning tags (e.g., from Qwen 3 or DeepSeek-R1) to prevent "thinking aloud" from leaking to terminal, Web, or TTS.
- **Tool Calling System**: Decorator-based extensible tool registry (`@tool`) that automatically extracts JSON schemas from Python type annotations and docstrings, handles errors cleanly, and truncates long outputs.
- **Context Window Budgeting**: Conservative rule-of-thumb token estimator that keeps the system prompt and the newest conversation turns, gracefully pruning oldest messages without exceeding model context limits.
- **Persistent Memory (SQLite)**: Thread-safe storage with WAL mode, foreign keys, cascade deletion, and auto-generated conversation titles based on initial user prompts.
- **Interactive Terminal CLI**:
  - Live animated spinner showing elapsed thinking time.
  - Automatic resumption of previous sessions.
  - Slash commands: `/new`, `/sessions`, `/resume <id>`, `/quit`.
- **Channel Adaptation**: Support for `text` (standard markdown chat) and `voice` (concise, spoken English tailored for TTS synthesis).
- **Concurrency & Resource Throttling**: Per-session mutex locks and a global LLM concurrency semaphore to prevent CPU/GPU saturation.

---

## Architecture Overview

```
                                  +-------------------+
                                  |   User / Client   |
                                  +---------+---------+
                                            |
                         +------------------+------------------+
                         |                                     |
                  [ Web UI / HTTP / SSE ]              [ Interactive CLI ]
                       (jarvis.api)                       (jarvis.cli)
                         |                                     |
                         +------------------+------------------+
                                            |
                                            v
                             +-----------------------------+
                             |  ChatService Orchestrator   |
                             |       (jarvis.service)      |
                             +--------------+--------------+
                                            |
                    +-----------------------+-----------------------+
                    |                       |                       |
                    v                       v                       v
         +--------------------+   +-------------------+   +--------------------+
         |  Context Budgeter  |   |  SQLite Storage   |   |   Tool Registry    |
         |  (jarvis.context)  |   |  (jarvis.store)   |   | (jarvis.tools.reg) |
         +--------------------+   +-------------------+   +--------------------+
                    |                       |                       |
                    +-----------------------+-----------------------+
                                            |
                                            v
                                   +-----------------+
                                   |   LLM Client    |
                                   |  (jarvis.llm)   |
                                   +--------+--------+
                                            |
                                 [ Streaming & ThinkStripper ]
                                            |
                                            v
                                 [ Local LLM (Ollama) ]
                                  http://localhost:11434/v1
```

---

## Project Structure

```
jarvis/
├── data/
│   └── jarvis.db              # SQLite conversation database
├── src/
│   └── jarvis/
│       ├── __init__.py        # Package initialization
│       ├── api.py             # FastAPI web application, static routes & SSE endpoints
│       ├── cli.py             # Interactive terminal client
│       ├── config.py          # Settings & environment configuration (Pydantic)
│       ├── context.py         # Token budgeting and history window truncation
│       ├── llm.py             # LLM streaming client, ThinkStripper, and StreamStats
│       ├── prompts.py         # System prompts and channel persona adapters
│       ├── service.py         # Core chat coordinator & concurrency gate
│       ├── static/
│       │   └── index.html     # Built-in Web chat UI (HTML/CSS/JS)
│       ├── store.py           # SQLite persistence layer
│       └── tools/
│           ├── __init__.py
│           └── registry.py    # @tool decorator & function-calling registry
├── test/
│   ├── test_api.py            # API, Web UI, & SSE endpoint tests
│   ├── test_context.py        # Token estimation & budgeting tests
│   ├── test_registry.py       # Tool schema generation & execution tests
│   ├── test_store.py          # SQLite schema & session transaction tests
│   └── test_think_stripper.py # Tag filtering and chunk split edge cases
├── pyproject.toml             # Project configuration and dependencies
└── README.md                  # Project documentation
```

---

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended) or standard `pip`
- A local LLM server running (e.g. [Ollama](https://ollama.com/)) with a model pulled (default: `qwen3:4b`):
  ```bash
  ollama pull qwen3:4b
  ```

### Installation

1. **Clone the repository and navigate to the project directory**:
   ```bash
   cd phase1/jarvis
   ```

2. **Set up the virtual environment**:
   ```bash
   # Using uv:
   uv venv
   source .venv/bin/activate
   uv sync

   # Or using standard venv:
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

---

## Configuration

Jarvis uses `pydantic-settings` and can be configured through environment variables prefixed with `JARVIS_` or a `.env` file.

| Setting | Environment Variable | Default | Description |
| :--- | :--- | :--- | :--- |
| `llm_base_url` | `JARVIS_LLM_BASE_URL` | `http://localhost:11434/v1` | OpenAI-compatible endpoint URL |
| `llm_api_key` | `JARVIS_LLM_API_KEY` | `not-needed` | API key (if required by endpoint) |
| `llm_timeout_s` | `JARVIS_LLM_TIMEOUT_S` | `120` | Timeout in seconds for LLM requests |
| `fast_model` | `JARVIS_FAST_MODEL` | `qwen3:4b` | Default low-latency model |
| `smart_model` | `JARVIS_SMART_MODEL` | `qwen3:4b` | High-reasoning model tier |
| `db_path` | `JARVIS_DB_PATH` | `data/jarvis.db` | Path to SQLite database file |
| `context_token` | `JARVIS_CONTEXT_TOKEN` | `4096` | Context window size |
| `replay_reserve_tokens` | `JARVIS_REPLAY_RESERVE_TOKENS` | `768` | Tokens reserved for answer generation |
| `max_parallel_generations`| `JARVIS_MAX_PARALLEL_GENERATIONS`| `1` | Max concurrent active LLM runs |

Example `.env` file:
```env
JARVIS_FAST_MODEL="qwen3:4b"
JARVIS_DB_PATH="data/jarvis.db"
JARVIS_MAX_PARALLEL_GENERATIONS=1
```

---

## Usage

### 1. Web UI & FastAPI Server

Start the web application:

```bash
uvicorn jarvis.api:app --reload --port 8000
```

Once running:
- **Web Chat UI**: Open your browser at [http://localhost:8000](http://localhost:8000)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
- **List Sessions**: [http://localhost:8000/sessions](http://localhost:8000/sessions)
- **Session Messages**: `GET /sessions/{session_id}/messages`

#### Streaming Chat over SSE (cURL):
```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Explain how black holes form in 2 sentences.",
    "channel": "text",
    "tier": "fast"
  }'
```

**SSE Event Lifecycle**:
```
event: status
data: {"state": "thinking", "session_id": "a3f89b1c"}

event: token
data: {"text": "Black holes form when..."}

event: done
data: {"session_id": "a3f89b1c", "trimmed": 0, "first_token_s": 0.42, "total_s": 1.15, "tokens": 34}
```

---

### 2. Interactive Terminal CLI

Launch the interactive chat interface directly in your console:

```bash
python -m jarvis.cli
```

#### Terminal Commands:
- `/new` : Start a fresh conversation session.
- `/sessions` : List past conversations with timestamps and turn counts.
- `/resume <id>` : Resume a past conversation by full ID or prefix (e.g., `/resume a1b2`).
- `/quit` : Exit the CLI.

---

### 3. Tool Calling System

Jarvis includes a decorator-based tool registry (`jarvis.tools.registry`) that turns standard Python functions into schemas compatible with LLM function calling:

```python
from typing import Annotated
from jarvis.tools.registry import tool, schemas, run_tool

@tool
def calculate(expression: Annotated[str, "mathematical expression to evaluate"]) -> str:
    """Evaluate simple arithmetic expressions."""
    # Custom tool logic here
    return str(eval(expression))

# Inspect generated OpenAI-compatible schemas:
print(schemas())

# Safely run tools with JSON argument strings:
result = run_tool("calculate", '{"expression": "24 * 7"}')
```

---

## Testing

Run the automated test suite using `pytest`:

```bash
.venv/bin/pytest
```

---

## License

This project is licensed under the MIT License.
