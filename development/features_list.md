# Jarvis AI Personal Assistant — Features Roadmap

**Date:** 2026-11-26  
**Architecture:** Hexagonal / Clean Architecture (`domain/`, `ports/`, `application/`, `infrastructure/`, `presentation/`)

This document outlines the prioritized features to integrate into **Jarvis** to make it more **useful, smarter, and accurate**.

---

## 1. Accuracy & Intelligence (Making Jarvis Smarter)

| Feature | Description | Architecture Layer | Priority |
| :--- | :--- | :--- | :--- |
| **Live Web Search & URL Reader Tools** | Add `@tool` functions for DuckDuckGo/Tavily web search (`web_search(query)`) and webpage text extraction (`fetch_url(url)`) to eliminate knowledge cutoffs and hallucinations on live data. | `infrastructure/tools/` | High |
| **Multi-Step Tool Loop** | Upgrade `ChatService.chat()` from a single tool-call pass to an iterative `while` loop (capped at e.g. 5 iterations) so Jarvis can chain multiple tools before answering. | `application/chat_service.py` | High |
| **Rolling Conversation Summarization** | Automatically summarize older turns in the background every ~6–8 messages and inject a compact `"Summary so far: ..."` into the system context, preserving coherence without latency. | `application/` + `domain/` | High |
| **Long-Term Semantic Memory (Vector RAG)** | Store key facts, user preferences, and past decisions in a local vector store (e.g. `sqlite-vec` or ChromaDB) behind a `MemoryPort` so Jarvis recalls context across sessions. | `ports/` + `infrastructure/persistence/` | High |
| **Collapsible `<think>` Reasoning Accordion** | Emit `<think>...</think>` blocks as `event: thinking` SSE frames and render a collapsed *"Thought for Xs"* dropdown in the web UI. | `domain/` + `presentation/web/` | Medium |

---

## 2. Knowledge Base & File Uploads (Documents, PDFs & RAG)

| Feature | Description | Architecture Layer | Priority |
| :--- | :--- | :--- | :--- |
| **Multi-Format File Upload** | Drag-and-drop or paperclip button in the web UI supporting `.pdf`, `.txt`, `.md`, `.csv`, `.json`, `.docx`, and source code files. | `presentation/web/` + `api.py` | High |
| **Persistent Knowledge Base (Document Library)** | Upload PDFs and reference files into a persistent Knowledge Base (stored in SQLite + local disk) so Jarvis can use them across *all* future chats, not just the current session. | `infrastructure/persistence/` + `ports/` | High |
| **Document Chunking & Semantic Search (`search_knowledge` `@tool`)** | Automatically extract text from PDFs/files, split into overlapping chunks, embed/index them (e.g., `sqlite-vec` or FTS5), and expose a `search_knowledge(query)` `@tool` so Jarvis retrieves only relevant passages. | `infrastructure/tools/` + `domain/` | High |
| **Session-Scoped File Attachments** | Attach a file to a single message/session for immediate Q&A, summarization, or code review without polluting the global Knowledge Base. | `application/chat_service.py` | High |
| **Knowledge Base Manager UI** | Sidebar/modal view to list uploaded knowledge files, see chunk/page counts, toggle which documents are active, or delete outdated files. | `presentation/web/static/` | Medium |

---

## 3. Everyday Usefulness (Personal Assistant Capabilities)

| Feature | Description | Architecture Layer | Priority |
| :--- | :--- | :--- | :--- |
| **Persistent Tasks, Reminders & Notes** | Add `add_todo`, `list_todos`, `complete_todo`, and `save_note` `@tool`s backed by SQLite so Jarvis can manage personal tasks across sessions. | `infrastructure/tools/` + `infrastructure/persistence/` | Medium |
| **Sandboxed Local Workspace Tools** | Read-only or workspace-scoped `@tool` helpers (`read_file`, `list_files`, `run_python_sandbox`) for inspecting local scripts and running data calculations. | `infrastructure/tools/` | Medium |
| **Dynamic Model Switcher** | Query Ollama's `/api/tags` endpoint to list all installed local models and allow switching directly from the UI top bar. | `infrastructure/llm/` + `presentation/web/` | Medium |
| **Message Regeneration & Prompt Editing** | Add **Regenerate** and **Edit** buttons on chat messages in the web UI to retry responses or refine prompts without retyping. | `presentation/web/` | Low |

---

## 4. Accuracy Guardrails & Reliability

| Feature | Description | Architecture Layer | Priority |
| :--- | :--- | :--- | :--- |
| **Citation Grounding** | Instruct Jarvis to cite source URLs/titles when using `wikipedia_summary` or `web_search`, and explicitly state when no results are found. | `domain/prompts.py` | High |
| **Exact Tokenizer Counting** | Replace the `CHARS_PER_TOKEN = 3.0` heuristic in `domain/context.py` with `tiktoken` or model-specific token counting for exact budget enforcement. | `domain/context.py` | Medium |
| **User Profile / Custom Instructions** | Persistent settings modal in the UI (stored in SQLite) for user name, timezone, preferred coding language, and response style injected into every system prompt. | `infrastructure/persistence/` + `presentation/web/` | Medium |

---

## 5. Recommended Implementation Order

1. **Web Search + URL Fetch `@tool`s** — Immediate accuracy boost for live facts.
2. **Multi-Step Tool Loop in `ChatService`** — Enables chaining tools together.
3. **File / PDF Upload & Knowledge Base (RAG)** — Upload PDFs/docs into a persistent Knowledge Base with `search_knowledge` `@tool` and session attachments.
4. **Rolling Conversation Summary** — Keeps long-chat accuracy high while preserving fast TTFT.
5. **Long-Term Vector Memory (`sqlite-vec`)** — True cross-session personal assistant memory.
