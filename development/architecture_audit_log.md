# Architecture Audit Log & System Specification

**Project:** Jarvis AI Personal Assistant  
**Date:** 2026-11-26  
**Status:** Approved & Implemented  
**Target Architecture:** Hexagonal / Clean Architecture (Ports & Adapters) with Event-Driven Pipeline  

---

## 1. Context & Motivation

Jarvis was initially implemented as a tightly coupled set of root modules (`service.py`, `llm.py`, `store.py`, `api.py`). While functional, scaling to support enterprise features (multiple model providers, vector databases, tool plugins, desktop/voice frontends) requires an architecture where:
1. Core business logic (context window calculation, persona prompts, reasoning tag stripping) is 100% independent of any database, UI, or AI vendor SDK.
2. External systems (Ollama, SQLite, Web APIs) can be swapped or tested without modifying business rules.
3. Every external boundary is guarded by an explicit typed contract (`Protocol`).

---

## 2. Structural Blueprint

```
src/jarvis/
├── domain/                         # Core Business Domain (No external I/O)
│   ├── entities.py                 # Message, SessionSummary, StreamStats
│   ├── context.py                  # Token budgeting & window trimming algorithm
│   ├── prompts.py                  # Persona definitions & channel templates
│   └── think_stripper.py           # Stream filter for <think> reasoning tags
│
├── ports/                          # Dependency Inversion Contracts
│   └── __init__.py                 # StorePort, LLMProviderPort protocols
│
├── application/                    # Application Use Cases & Orchestration
│   └── chat_service.py             # ChatService (Turn execution & tool calling loop)
│
├── infrastructure/                 # Concrete I/O Adapters
│   ├── llm/
│   │   └── openai_adapter.py       # OpenAICompatibleLLMAdapter (Ollama, vLLM)
│   ├── persistence/
│   │   └── sqlite_adapter.py       # SQLiteStoreAdapter (Transactional SQLite)
│   └── tools/
│       ├── registry.py             # @tool decorator & JSON schema generator
│       └── builtin.py              # Math calculator, current time, Wikipedia
│
├── presentation/                   # Driving Adapters
│   └── web/
│       ├── api.py                  # FastAPI ASGI endpoints & SSE streaming
│       └── static/index.html       # Claude.ai-style Web UI
│
├── config.py                       # Runtime settings (Pydantic-Settings)
└── [shims]                         # api.py, cli.py, store.py, llm.py, etc. (Zero-breakage)
```

---

## 3. Layer Specifications & Responsibilities

### 3.1 Domain Layer (`jarvis.domain`)
- **Purity:** Contains zero I/O imports (no `fastapi`, `sqlite3`, `openai`, `requests`).
- **`entities.py`**: Declares foundational value objects (`Message`, `StreamStats`, `SessionSummary`).
- **`context.py`**: Pure algorithms for token estimation (`CHARS_PER_TOKEN = 3.0`) and history budget truncation (`fit_to_budget`).
- **`think_stripper.py`**: Real-time state machine that suppresses `<think>...</think>` tokens without blocking the stream.
- **`prompts.py`**: Channel adaptations (`text` vs TTS-ready `voice`).

### 3.2 Ports Layer (`jarvis.ports`)
- Uses Python `typing.Protocol` with `@runtime_checkable` to enforce contracts at runtime and compile-time:
  - **`StorePort`**: Defines persistence operations (`add_turn`, `messages`, `list_sessions`, `delete_session`, `rename_session`).
  - **`LLMProviderPort`**: Defines streaming generation contracts (`stream(messages, tier, think, stats, tools)`).

### 3.3 Application Layer (`jarvis.application`)
- **`chat_service.py`**: Orchestrates a complete turn:
  1. Per-session mutex acquisition (`_session_locks`).
  2. History retrieval from `StorePort`.
  3. Window truncation using domain `fit_to_budget`.
  4. Concurrency throttling (`asyncio.Semaphore`).
  5. Multi-step tool execution loop with dynamic schema feeding.
  6. Final turn persistence via `StorePort.add_turn`.
  7. SSE-compatible event emission.

### 3.4 Infrastructure Layer (`jarvis.infrastructure`)
- **`OpenAICompatibleLLMAdapter`**: Connects to OpenAI-compliant local endpoints (Ollama).
- **`SQLiteStoreAdapter`**: Manages SQLite connections with WAL mode, foreign keys, and atomic commits.
- **`jarvis.tools`**: Decorator-driven runtime tool registry with type annotation inspection.

### 3.5 Presentation Layer (`jarvis.presentation`)
- **`api.py`**: FastAPI routing layer providing `/health`, `/sessions`, `/chat` (SSE), and static file delivery.
- **`cli.py`**: Interactive console REPL with animated terminal spinners.

---

## 4. Backward Compatibility Guarantee

To guarantee zero regression for existing tests, deployment scripts, and users, root-level module shims are maintained:
- `jarvis.api` $\to$ re-exports `presentation.web.api`
- `jarvis.service` $\to$ re-exports `application.chat_service`
- `jarvis.store` $\to$ re-exports `infrastructure.persistence.sqlite_adapter`
- `jarvis.llm` $\to$ re-exports `infrastructure.llm.openai_adapter`
- `jarvis.context` $\to$ re-exports `domain.context`
- `jarvis.prompts` $\to$ re-exports `domain.prompts`

---

## 5. Verification Results

All unit tests execute successfully under the new architecture without modification:
```
============================== 20 passed in 0.71s ==============================
test/test_api.py ....                                                    [ 20%]
test/test_context.py ...                                                 [ 35%]
test/test_registry.py .....                                              [ 60%]
test/test_store.py ...                                                   [ 75%]
test/test_think_stripper.py ....                                         [ 95%]
test/test_tools_service.py .                                             [100%]
```
