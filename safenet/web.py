"""Local web adapter. All security analysis still runs through build_graph()."""

import logging
import os
import threading
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .graph import build_graph
from .history import History, now
from .models import CyberSafetyState

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"
logger = logging.getLogger(__name__)


class NewConversation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(default="New conversation", min_length=1, max_length=80)


class RenameConversation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=80)


class Message(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=6000)
    request_id: UUID


def create_app(database_path: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        load_dotenv(PROJECT_ROOT / ".env")
        path = database_path or Path(os.getenv("SAFENET_DATA_DIR", str(PROJECT_ROOT / ".safenet"))) / "history.sqlite3"
        app.state.history = History(path)
        app.state.graph = build_graph()
        yield

    app = FastAPI(title="SafeNet", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])
    busy: set[str] = set()
    guard = threading.Lock()

    @contextmanager
    def conversation_lock(conversation_id: str):
        with guard:
            if conversation_id in busy:
                raise HTTPException(409, "This conversation is still processing. Please wait and try again.")
            busy.add(conversation_id)
        try:
            yield
        finally:
            with guard:
                busy.discard(conversation_id)

    def get_conversation(conversation_id: UUID) -> dict:
        conversation = app.state.history.get(str(conversation_id))
        if conversation is None:
            raise HTTPException(404, "This conversation was deleted or is no longer available.")
        return conversation

    @app.middleware("http")
    async def local_client(request: Request, call_next):
        # A custom header prevents cross-origin forms from changing local history.
        if request.method in {"POST", "PATCH", "DELETE"} and request.headers.get("x-safenet-client") != "web":
            return JSONResponse({"detail": "Please use the SafeNet app to make this request."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/config")
    def config():
        return {
            "live_available": bool(os.getenv("OPENAI_API_KEY", "").strip()),
            "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            "analysis_mode": "live",
            "max_message_length": 6000,
        }

    @app.get("/api/conversations")
    def conversations():
        return app.state.history.list()

    # Flow: create a conversation ID; the same ID becomes the LangGraph thread ID.
    @app.post("/api/conversations", status_code=201)
    def create_conversation(body: NewConversation):
        return app.state.history.create(body.title, "live")

    @app.get("/api/conversations/{conversation_id}")
    def conversation(conversation_id: UUID):
        return get_conversation(conversation_id)

    @app.patch("/api/conversations/{conversation_id}")
    def rename(conversation_id: UUID, body: RenameConversation):
        with conversation_lock(str(conversation_id)):
            get_conversation(conversation_id)
            app.state.history.rename(str(conversation_id), body.title)
            return get_conversation(conversation_id)

    @app.delete("/api/conversations/{conversation_id}")
    def delete(conversation_id: UUID):
        with conversation_lock(str(conversation_id)):
            get_conversation(conversation_id)
            app.state.history.delete(str(conversation_id))
            app.state.graph.checkpointer.delete_thread(str(conversation_id))
        return {"deleted": True}

    # Flow: send only the newest message; LangGraph retrieves the rest from its thread checkpoint.
    @app.post("/api/conversations/{conversation_id}/messages")
    def send(conversation_id: UUID, body: Message):
        with conversation_lock(str(conversation_id)):
            conversation = get_conversation(conversation_id)
            for turn in conversation["turns"]:
                if turn["id"] == str(body.request_id):
                    if turn["user"] != body.message:
                        raise HTTPException(409, "This message ID has already been used.")
                    return conversation

            if not os.getenv("OPENAI_API_KEY", "").strip():
                raise HTTPException(503, "OpenAI API key is missing. Add OPENAI_API_KEY to .env and restart SafeNet.")

            # Flow: the conversation ID is also the LangGraph thread ID; the thread owns incident context.
            try:
                values = app.state.graph.invoke(
                    {"user_message": body.message, "use_live_llm": True},
                    config={"configurable": {"thread_id": str(conversation_id)}},
                )
                state = CyberSafetyState.model_validate(values)
            except Exception as exc:
                logger.exception("SafeNet analysis failed")
                raise
                status = getattr(exc, "status_code", None)
                if status in {401, 403}:
                    detail = "OpenAI authentication failed. Check OPENAI_API_KEY and model access."
                elif status == 429:
                    detail = "OpenAI API rate or credit limit reached. Check your OpenAI billing or try again later."
                else:
                    detail = "Live OpenAI analysis is unavailable. Check your API key, model setting, and connection, then try again."
                raise HTTPException(502, detail) from None

            turn = {
                "id": str(body.request_id), "user": body.message, "mode": "live",
                "created_at": now(), "assessment": state.model_dump(exclude={"user_message"}),
            }
            app.state.history.save_turn(conversation, turn)
            return get_conversation(conversation_id)

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


def main():
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Start SafeNet's local web interface")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"\n  SafeNet is starting at http://localhost:{args.port}\n  Press Ctrl+C to stop.\n")
    uvicorn.run(create_app(), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
