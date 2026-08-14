from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from .models import ProcessDefinition


class ProjectRepository:
    def __init__(self, path: str | Path = "data/sop_builder.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def connect(self):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        return con

    def _init(self):
        with self.connect() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,title TEXT NOT NULL,process_json TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'discovery',created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,project_id TEXT,role TEXT,content TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS artifacts(id INTEGER PRIMARY KEY,project_id TEXT,kind TEXT,payload TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY,project_id TEXT,path TEXT,validation_json TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY,project_id TEXT NOT NULL,reviewer TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'submitted',comment TEXT NOT NULL DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            """)

    def create(self, title: str) -> str:
        pid = str(uuid.uuid4())
        p = ProcessDefinition()
        p.sop_title.value = title
        p.sop_title.provenance = p.sop_title.provenance.USER
        with self.connect() as c:
            c.execute(
                "INSERT INTO projects(id,title,process_json) VALUES(?,?,?)",
                (pid, title, json.dumps(p.to_dict())),
            )
        return pid

    def save_process(self, pid: str, p: ProcessDefinition, status="discovery"):
        p.validate()
        title = str(p.sop_title.value or "Untitled SOP")
        with self.connect() as c:
            c.execute(
                "UPDATE projects SET title=?,process_json=?,status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (title, json.dumps(p.to_dict()), status, pid),
            )

    def load(self, pid: str):
        with self.connect() as c:
            row = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        if not row:
            return None
        return {
            **dict(row),
            "process": ProcessDefinition.from_dict(json.loads(row["process_json"])),
        }

    def list_projects(self):
        with self.connect() as c:
            return [
                dict(x)
                for x in c.execute(
                    "SELECT id,title,status,updated_at FROM projects ORDER BY updated_at DESC"
                )
            ]

    def message(self, pid, role, content):
        with self.connect() as c:
            c.execute(
                "INSERT INTO messages(project_id,role,content) VALUES(?,?,?)",
                (pid, role, content),
            )

    def messages(self, pid):
        with self.connect() as c:
            return [
                dict(x)
                for x in c.execute(
                    "SELECT role,content,created_at FROM messages WHERE project_id=? ORDER BY id",
                    (pid,),
                )
            ]

    def artifact(self, pid, kind, payload):
        with self.connect() as c:
            c.execute(
                "INSERT INTO artifacts(project_id,kind,payload) VALUES(?,?,?)",
                (pid, kind, json.dumps(payload, default=str)),
            )

    def artifacts(self, pid, kind=None):
        sql = "SELECT kind,payload,created_at FROM artifacts WHERE project_id=?"
        args = [pid]
        if kind:
            sql += " AND kind=?"
            args.append(kind)
        with self.connect() as c:
            return [
                {**dict(x), "payload": json.loads(x["payload"])}
                for x in c.execute(sql, args)
            ]

    def generated_file(self, pid, path, validation):
        with self.connect() as c:
            c.execute(
                "INSERT INTO files(project_id,path,validation_json) VALUES(?,?,?)",
                (pid, str(path), json.dumps(validation)),
            )

    def list_generated_files(self, pid):
        """Return generated files newest first for a persisted SOP project."""
        with self.connect() as c:
            return [
                {**dict(row), "validation": json.loads(row["validation_json"])}
                for row in c.execute(
                    "SELECT path,validation_json,created_at FROM files WHERE project_id=? ORDER BY id DESC",
                    (pid,),
                )
            ]

    def files(self, pid):
        """Backward-compatible alias for callers from the previous MVP iteration."""
        return self.list_generated_files(pid)

    def submit_for_review(self, pid: str, reviewer: str = "") -> None:
        with self.connect() as c:
            c.execute(
                "UPDATE projects SET status='submitted',updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (pid,),
            )
            c.execute(
                "INSERT INTO reviews(project_id,reviewer,status,comment) VALUES(?,?,'submitted','')",
                (pid, reviewer),
            )

    def record_review(self, pid: str, status: str, reviewer: str, comment: str) -> None:
        if status not in {"changes_requested", "validated"}:
            raise ValueError("Review status must be changes_requested or validated")
        if not reviewer.strip():
            raise ValueError("Internal controller name is required")
        with self.connect() as c:
            c.execute(
                "UPDATE projects SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, pid),
            )
            c.execute(
                "INSERT INTO reviews(project_id,reviewer,status,comment) VALUES(?,?,?,?)",
                (pid, reviewer, status, comment),
            )
            if status == "changes_requested":
                feedback = (
                    f"⚠️ **Internal review corrections requested by {reviewer}.**\n\n"
                    f"{comment or 'Please contact the internal controller for details.'}\n\n"
                    "Reply here with the corrected information, then run the quality review again."
                )
                c.execute(
                    "INSERT INTO messages(project_id,role,content) VALUES(?,'assistant',?)",
                    (pid, feedback),
                )

    def review_history(self, pid: str):
        with self.connect() as c:
            return [
                dict(row)
                for row in c.execute(
                    "SELECT reviewer,status,comment,created_at FROM reviews WHERE project_id=? ORDER BY id",
                    (pid,),
                )
            ]

    def projects_by_status(self, statuses: tuple[str, ...]):
        placeholders = ",".join("?" for _ in statuses)
        with self.connect() as c:
            return [
                dict(row)
                for row in c.execute(
                    f"SELECT id,title,status,updated_at FROM projects WHERE status IN ({placeholders}) ORDER BY updated_at DESC",
                    statuses,
                )
            ]
