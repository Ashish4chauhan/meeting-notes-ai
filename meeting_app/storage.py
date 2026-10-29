import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class MeetingStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS meetings (id INTEGER PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL, transcript TEXT NOT NULL, summary TEXT NOT NULL, segments_json TEXT NOT NULL)")

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def save_meeting(self, title: str, transcript: str, summary: str, segments_json: str = "[]") -> int:
        if not title.strip(): title = "Untitled meeting"
        with self._connect() as db:
            cursor = db.execute("INSERT INTO meetings(title, created_at, transcript, summary, segments_json) VALUES (?, ?, ?, ?, ?)", (title.strip(), datetime.now(timezone.utc).isoformat(), transcript, summary, segments_json))
            return int(cursor.lastrowid)

    def list_meetings(self, limit: int = 100):
        with self._connect() as db:
            return [dict(row) for row in db.execute("SELECT id,title,created_at FROM meetings ORDER BY id DESC LIMIT ?", (limit,))]

    def get_meeting(self, meeting_id: int):
        with self._connect() as db:
            row = db.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone()
            return dict(row) if row else None
