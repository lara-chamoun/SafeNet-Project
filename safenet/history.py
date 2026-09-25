"""SQLite stores UI conversation history; LangGraph threads own analysis context."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class History:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, mode TEXT NOT NULL,
                turns TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def list(self) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT id, title, mode, created_at, updated_at FROM conversations "
                "ORDER BY updated_at DESC, id"
            )]

    def get(self, conversation_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["turns"] = json.loads(result["turns"])
        return result

    def create(self, title: str, mode: str) -> dict:
        conversation_id = str(uuid.uuid4())
        timestamp = now()
        with self.connect() as db:
            db.execute(
                "INSERT INTO conversations (id, title, mode, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (conversation_id, title, mode, timestamp, timestamp),
            )
        return self.get(conversation_id)

    def rename(self, conversation_id: str, title: str):
        with self.connect() as db:
            db.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id))

    # Flow: save only what the UI needs to display/reopen a conversation; analysis context stays in LangGraph.
    def save_turn(self, conversation: dict, turn: dict):
        turns = [*conversation["turns"], turn]
        with self.connect() as db:
            db.execute(
                "UPDATE conversations SET turns = ?, mode = ?, updated_at = ? WHERE id = ?",
                (json.dumps(turns, ensure_ascii=False), turn["mode"], now(), conversation["id"]),
            )

    def delete(self, conversation_id: str):
        with self.connect() as db:
            db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
