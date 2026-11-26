"""FastAPI web server and Server-Sent Events (SSE) streaming API for Jarvis.

This module exposes REST and streaming endpoints to interact with the assistant:
- `GET  /health`                   : Health check, returns current models & status.
- `GET  /sessions`                 : List recent sessions and message counts.
- `GET  /sessions/{session_id}/messages` : Get full history of a session.
- `POST /chat`                     : Stream responses via Server-Sent Events (SSE).

Example:
    To run the API server locally:
    ```bash
    uvicorn jarvis.api:app --reload --port 8000
    ```

    To test the streaming chat endpoint using curl:
    ```bash
    curl -N -X POST http://localhost:8000/chat \\
         -H "Content-Type: application/json" \\
         -d '{"message": "Hello Jarvis!", "channel": "text"}'
    ```
"""

import json
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pathlib import Path
from fastapi.responses import FileResponse, StreamingResponse 

from jarvis.config import settings
from jarvis.llm import LLMClient
from jarvis.service import ChatService
from jarvis.store import Store

STATIC_DIR = Path(__file__).parent / "static"

class ChatRequest(BaseModel):
    """Payload schema for the `/chat` endpoint.

    Attributes:
        message: The user's input prompt (1 to 8000 characters).
        session_id: Optional session identifier. If omitted, a new session is created.
        channel: Prompt styling target ('text' for standard formatting, 'voice' for TTS-ready prose).
        tier: Model performance tier ('fast' or 'smart').
    """

    message: str = Field(min_length=1, max_length=8000, description="The message from the user.")
    session_id: str | None = Field(
        default=None, description="Optional session ID to continue an existing conversation."
    )
    channel: Literal["text", "voice"] = Field(
        default="text", description="Target channel styling: 'text' or 'voice'."
    )
    tier: Literal["fast", "smart"] = Field(
        default="fast", description="Model tier: 'fast' or 'smart'."
    )


def sse(event: str, data: dict) -> str:
    """Format an event name and dictionary payload as a standard SSE (Server-Sent Event) frame.

    Args:
        event: The event name (e.g. 'status', 'token', 'done', 'error').
        data: Dict containing event payload to serialize as JSON.

    Returns:
        Formatted SSE wire string ending with double newline (`\\n\\n`).

    Example:
        >>> sse("token", {"text": "Hello"})
        'event: token\\ndata: {"text": "Hello"}\\n\\n'
    """
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def create_app(store: Store | None = None, llm: LLMClient | None = None) -> FastAPI:
    """Create and configure the FastAPI application instance with dependency injection.

    Args:
        store: Optional pre-configured Store instance (useful for unit testing with in-memory DB).
        llm: Optional pre-configured LLMClient instance (useful for mock testing).

    Returns:
        FastAPI application ready to serve requests.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Manage application startup and shutdown lifecycle resources."""
        app.state.store = store or Store()
        app.state.service = ChatService(app.state.store, llm or LLMClient())
        yield

    app = FastAPI(
        title="Jarvis",
        description="Local personal assistant service with persistent memory and SSE streaming.",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(STATIC_DIR / "index.html")
    
    @app.get("/health", summary="Health Check")
    async def health():
        """Return server status and configured model names."""
        return {
            "status": "ok",
            "fast_model": settings.fast_model,
            "smart_model": settings.smart_model,
        }

    @app.get("/sessions", summary="List Sessions")
    async def sessions():
        """Retrieve the 50 most recent chat sessions with titles and message counts."""
        return [dict(r) for r in app.state.store.list_sessions(limit=50)]

    @app.get("/sessions/{session_id}/messages", summary="Get Session History")
    async def session_messages(session_id: str):
        """Retrieve all messages in chronological order for a specific session."""
        if not app.state.store.exists(session_id):
            raise HTTPException(status_code=404, detail="unknown session")
        return app.state.store.messages(session_id)

    @app.post("/chat", summary="Stream Chat Completion")
    async def chat(req: ChatRequest):
        """Stream a chat conversation response as Server-Sent Events (SSE).

        Yields SSE events:
        - `status`: Lifecycle updates ('queued', 'thinking').
        - `token`: Partial text tokens as they are generated.
        - `done`: Final metadata (token count, generation time, trimmed message count).
        - `error`: Error details if generation or persistence failed.
        """
        if req.session_id and not app.state.store.exists(req.session_id):
            raise HTTPException(status_code=404, detail="unknown session")

        async def events():
            try:
                async for ev in app.state.service.chat(
                    req.message, req.session_id, req.channel, req.tier
                ):
                    yield sse(ev["event"], ev["data"])
            except Exception as e:
                # Once streaming headers are sent with 200 OK, errors must be delivered as SSE frames
                yield sse("error", {"message": str(e)})

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


# Default application instance for ASGI servers (e.g. uvicorn)
app = create_app()
