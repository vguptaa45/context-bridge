"""Reads Codex conversation data from SQLite database and JSONL rollout files."""

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from lib import CODEX_HOME
from lib.types import Message, Session, extract_repo_name


class CodexReader:
    """Reader for Codex conversation data.

    Codex stores thread metadata in a SQLite database and conversation
    rollouts as JSONL files.  This class provides methods to list sessions,
    read individual threads, and extract user prompts from history.
    """

    def __init__(
        self,
        codex_home: Optional[str] = None,
        db_path: Optional[str] = None,
        history_path: Optional[str] = None,
    ):
        home = Path(codex_home) if codex_home else CODEX_HOME
        self._db_path = db_path or str(home / "state_5.sqlite")
        self._history_path = history_path or str(home / "history.jsonl")

    # ── Public API ───────────────────────────────────────────────────────

    def list_sessions(
        self,
        repo: Optional[str] = None,
        days_back: Optional[int] = None,
        limit: int = 50,
    ) -> List[Session]:
        """Return non-archived, non-subagent threads sorted by updated_at DESC.

        Args:
            repo: If provided, filter to sessions whose cwd ends with this name.
            days_back: If provided, only include sessions updated within this
                       many days from now.
            limit: Maximum number of sessions to return (default 50).
        """
        query = (
            "SELECT id, rollout_path, created_at, updated_at, source, "
            "cwd, title, first_user_message, model, git_branch "
            "FROM threads "
            "WHERE archived = 0 AND source NOT LIKE '{%}'"
        )
        params: list = []

        if days_back is not None:
            cutoff = int(time.time()) - (days_back * 86400)
            query += " AND updated_at >= ?"
            params.append(cutoff)

        if repo is not None:
            # Match cwd ending with /<repo> or being exactly <repo>
            query += " AND (cwd LIKE ? OR cwd LIKE ?)"
            params.append(f"%/{repo}")
            params.append(repo)

        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()

        sessions: List[Session] = []
        for row in rows:
            cwd = row["cwd"] or ""
            sessions.append(
                Session(
                    id=row["id"],
                    source="codex",
                    repo=extract_repo_name(cwd),
                    cwd=cwd,
                    title=row["title"] or "",
                    first_prompt=row["first_user_message"] or "",
                    created_at=datetime.fromtimestamp(
                        row["created_at"], tz=timezone.utc
                    ),
                    updated_at=datetime.fromtimestamp(
                        row["updated_at"], tz=timezone.utc
                    ),
                    model=row["model"],
                    git_branch=row["git_branch"],
                )
            )
        return sessions

    def read_thread(self, rollout_path: str) -> List[Message]:
        """Parse a rollout JSONL file and extract user/assistant messages.

        Only ``response_item`` events with ``payload.type == "message"`` and
        ``role`` in (``"user"``, ``"assistant"``) are included.  Function calls,
        function call outputs, and developer messages are skipped.
        """
        messages: List[Message] = []
        path = Path(rollout_path)
        if not path.exists():
            return messages

        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if event.get("type") != "response_item":
                    continue

                payload = event.get("payload", {})
                if payload.get("type") != "message":
                    continue

                role = payload.get("role")
                if role not in ("user", "assistant"):
                    continue

                timestamp = event.get("timestamp", "")
                content_list = payload.get("content", [])
                text = self._extract_text(content_list, role)
                if text:
                    messages.append(Message(role=role, text=text, timestamp=timestamp))

        return messages

    def get_compacted_summaries(self, rollout_path: str) -> List[str]:
        """Extract user messages from ``compacted`` events in a rollout file."""
        summaries: List[str] = []
        path = Path(rollout_path)
        if not path.exists():
            return summaries

        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if event.get("type") != "compacted":
                    continue

                payload = event.get("payload", {})
                for item in payload.get("replacement_history", []):
                    if item.get("type") != "message":
                        continue
                    if item.get("role") != "user":
                        continue
                    text = self._extract_text(item.get("content", []), "user")
                    if text:
                        summaries.append(text)

        return summaries

    def get_user_prompts(self) -> Dict[str, List[str]]:
        """Read history.jsonl and group user prompts by session_id.

        Returns a dict mapping session_id to an ordered list of prompt strings.
        """
        prompts: Dict[str, List[str]] = {}
        path = Path(self._history_path)
        if not path.exists():
            return prompts

        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                session_id = entry.get("session_id")
                text = entry.get("text", "")
                if session_id and text:
                    prompts.setdefault(session_id, []).append(text)

        return prompts

    def resolve_rollout_path(self, session_id: str) -> Optional[str]:
        """Look up the rollout_path for a given session_id from SQLite."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.execute(
                "SELECT rollout_path FROM threads WHERE id = ?", (session_id,)
            )
            row = cursor.fetchone()
        finally:
            conn.close()

        if row:
            return row[0]
        return None

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _extract_text(content_list: list, role: str) -> str:
        """Extract plain text from a content list.

        For user messages looks for ``input_text`` type; for assistant messages
        looks for ``output_text`` type.
        """
        target_type = "input_text" if role == "user" else "output_text"
        parts: List[str] = []
        for item in content_list:
            if item.get("type") == target_type:
                text = item.get("text", "")
                if text:
                    parts.append(text)
        return "\n".join(parts)
