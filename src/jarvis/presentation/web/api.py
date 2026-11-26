"""FastAPI web presentation adapter for Jarvis."""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from jarvis.application.chat_service import ChatService
from jarvis.config import settings
from jarvis.infrastructure.llm.openai_adapter import OpenAICompatibleLLMAdapter
from jarvis.infrastructure.persistence.sqlite_adapter import SQLiteStoreAdapter
from jarvis.ports import LLMProviderPort, StorePort

STATIC_DIR = Path(__file__).resolve().parent / "static"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000, description="The message from the user.")
    session_id: str | None = Field(default=None, description="Optional session ID.")
    channel: Literal["text", "voice"] = Field(default="text", description="Target channel styling.")
    tier: Literal["fast", "smart"] = Field(default="fast", description="Model tier.")


class RenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def create_app(
    store: StorePort | None = None, llm: LLMProviderPort | None = None
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = store or SQLiteStoreAdapter()
        app.state.service = ChatService(app.state.store, llm or OpenAICompatibleLLMAdapter())
        yield

    app = FastAPI(
        title="Jarvis",
        description="Local personal assistant service built on Clean Architecture.",
        version="0.2.0",
        lifespan=lifespan,
    )

    @app.get("/", summary="Web Chat UI")
    async def index():
        # Fallback to src/jarvis/static/index.html if presentation static isn't populated
        p_static = STATIC_DIR / "index.html"
        if not p_static.exists():
            p_static = Path(__file__).resolve().parent.parent.parent / "static" / "index.html"
        return FileResponse(p_static)

    @app.get("/health", summary="Health Check")
    async def health():
        return {
            "status": "ok",
            "fast_model": settings.fast_model,
            "smart_model": settings.smart_model,
        }

    @app.get("/sessions", summary="List Sessions")
    async def sessions():
        return [dict(r) for r in app.state.store.list_sessions(limit=50)]

    @app.get("/sessions/{session_id}/messages", summary="Get Session History")
    async def session_messages(session_id: str):
        if not app.state.store.exists(session_id):
            raise HTTPException(status_code=404, detail="unknown session")
        return app.state.store.messages(session_id)

    @app.delete("/sessions/{session_id}", summary="Delete Session")
    async def delete_session(session_id: str):
        if not app.state.store.exists(session_id):
            raise HTTPException(status_code=404, detail="unknown session")
        app.state.store.delete_session(session_id)
        return {"status": "ok", "deleted": session_id}

    @app.patch("/sessions/{session_id}", summary="Rename Session")
    async def rename_session(session_id: str, req: RenameRequest):
        if not app.state.store.exists(session_id):
            raise HTTPException(status_code=404, detail="unknown session")
        app.state.store.rename_session(session_id, req.title)
        return {"status": "ok", "id": session_id, "title": req.title}

    @app.post("/chat", summary="Stream Chat Completion")
    async def chat(req: ChatRequest):
        if req.session_id and not app.state.store.exists(req.session_id):
            raise HTTPException(status_code=404, detail="unknown session")

        async def events():
            try:
                async for ev in app.state.service.chat(
                    req.message, req.session_id, req.channel, req.tier
                ):
                    yield sse(ev["event"], ev["data"])
            except Exception as e:
                yield sse("error", {"message": str(e)})

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


app = create_app()
