"""Reader for Claude Code conversation sessions stored as JSONL files."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from lib.types import Message, Session, extract_repo_name


class ClaudeReader:
    """Reads Claude Code session data from ~/.claude/ project directories."""

    def __init__(self, claude_home: Optional[Path] = None):
        if claude_home is None:
            claude_home = Path.home() / ".claude"
        self.claude_home = Path(claude_home)

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _decode_project_path(self, project_dir: Path) -> str:
        """Recover the original absolute path for a project directory.

        Claude encodes paths by replacing '/' with '-', but that encoding is
        lossy when directory names themselves contain hyphens.  We try, in
        order:
        1. Read 'originalPath' from sessions-index.json (authoritative).
        2. Read 'cwd' from the first line of any JSONL file in the directory.
        3. Fall back to the directory name itself (best-effort, may be wrong).
        """
        index_file = project_dir / "sessions-index.json"
        if index_file.exists():
            try:
                data = json.loads(index_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("originalPath"):
                    return data["originalPath"]
            except (json.JSONDecodeError, OSError):
                pass

        # Try reading cwd from first JSONL line
        for jsonl_file in project_dir.glob("*.jsonl"):
            try:
                with open(jsonl_file, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        entry = json.loads(line)
                        cwd = entry.get("cwd")
                        if cwd:
                            return cwd
                        break
            except (json.JSONDecodeError, OSError):
                continue

        # Last resort: naive decode
        dir_name = project_dir.name
        if dir_name.startswith("-"):
            return "/" + dir_name[1:].replace("-", "/")
        return dir_name

    def _find_session_file(self, session_id: str) -> Optional[Path]:
        """Search across all project directories for a session JSONL file."""
        projects_dir = self.claude_home / "projects"
        if not projects_dir.exists():
            return None
        for project_dir in projects_dir.iterdir():
            if not project_dir.is_dir():
                continue
            candidate = project_dir / f"{session_id}.jsonl"
            if candidate.exists():
                return candidate
        return None

    # ------------------------------------------------------------------
    # Model detection
    # ------------------------------------------------------------------

    def _detect_model(self, jsonl_path: str) -> Optional[str]:
        """Read the model from the first assistant message in a JSONL file."""
        path = Path(jsonl_path)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") == "assistant":
                    model = entry.get("message", {}).get("model")
                    if model:
                        return model
        return None

    # ------------------------------------------------------------------
    # list_sessions
    # ------------------------------------------------------------------

    def list_sessions(
        self,
        repo: Optional[str] = None,
        days_back: Optional[int] = None,
        limit: int = 50,
    ) -> List[Session]:
        """List available Claude Code sessions.

        Scans projects/*/ directories.  If a sessions-index.json exists it is
        used (it has summaries, firstPrompt, created/modified).  Otherwise we
        fall back to scanning .jsonl files directly.

        Sidechains are filtered out.  Results are sorted by updated_at DESC.
        """
        projects_dir = self.claude_home / "projects"
        if not projects_dir.exists():
            return []

        sessions: List[Session] = []
        cutoff = None
        if days_back is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

        for project_dir in projects_dir.iterdir():
            if not project_dir.is_dir():
                continue

            project_path = self._decode_project_path(project_dir)

            index_file = project_dir / "sessions-index.json"
            if index_file.exists():
                sessions.extend(
                    self._sessions_from_index(index_file, project_path, cutoff, repo)
                )
            else:
                project_repo = extract_repo_name(project_path)
                if repo is not None and project_repo != repo:
                    continue
                sessions.extend(
                    self._sessions_from_jsonl_scan(project_dir, project_path, project_repo, cutoff)
                )

        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions[:limit]

    def _sessions_from_index(
        self,
        index_file: Path,
        project_path: str,
        cutoff: Optional[datetime],
        repo_filter: Optional[str] = None,
    ) -> List[Session]:
        """Build Session objects from a sessions-index.json file."""
        results: List[Session] = []
        try:
            data = json.loads(index_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return results

        entries = data.get("entries", []) if isinstance(data, dict) else data

        for entry in entries:
            if entry.get("isSidechain", False):
                continue

            session_id = entry.get("sessionId", "")
            created_str = entry.get("created", "")
            modified_str = entry.get("modified", "")

            created_at = self._parse_timestamp(created_str)
            updated_at = self._parse_timestamp(modified_str)

            if cutoff and updated_at < cutoff:
                continue

            # Use projectPath from the index entry as the authoritative path
            cwd = entry.get("projectPath", project_path)
            session_repo = extract_repo_name(cwd)

            if repo_filter is not None and session_repo != repo_filter:
                continue

            # Detect model from the JSONL file
            jsonl_path = index_file.parent / f"{session_id}.jsonl"
            model = self._detect_model(str(jsonl_path))

            results.append(
                Session(
                    id=session_id,
                    source="claude",
                    repo=session_repo,
                    cwd=cwd,
                    title=entry.get("summary", entry.get("firstPrompt", "")),
                    first_prompt=entry.get("firstPrompt", ""),
                    created_at=created_at,
                    updated_at=updated_at,
                    model=model,
                    git_branch=entry.get("gitBranch"),
                )
            )
        return results

    def _sessions_from_jsonl_scan(
        self,
        project_dir: Path,
        project_path: str,
        project_repo: str,
        cutoff: Optional[datetime],
    ) -> List[Session]:
        """Fallback: build Session objects by scanning JSONL files directly."""
        results: List[Session] = []
        for jsonl_file in project_dir.glob("*.jsonl"):
            session_id = jsonl_file.stem
            first_prompt = ""
            model = None
            first_ts = None
            last_ts = None
            cwd = project_path
            git_branch = None
            is_sidechain = False

            with open(jsonl_file, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if entry.get("isSidechain", False):
                        is_sidechain = True
                        break

                    ts_str = entry.get("timestamp", "")
                    ts = self._parse_timestamp(ts_str)
                    if first_ts is None:
                        first_ts = ts
                    last_ts = ts

                    if entry.get("cwd"):
                        cwd = entry["cwd"]
                    if entry.get("gitBranch"):
                        git_branch = entry["gitBranch"]

                    if entry.get("type") == "user" and not first_prompt:
                        content = entry.get("message", {}).get("content", "")
                        if isinstance(content, str):
                            first_prompt = content

                    if entry.get("type") == "assistant" and model is None:
                        model = entry.get("message", {}).get("model")

            if is_sidechain:
                continue

            if first_ts is None:
                continue

            if cutoff and last_ts and last_ts < cutoff:
                continue

            results.append(
                Session(
                    id=session_id,
                    source="claude",
                    repo=project_repo,
                    cwd=cwd,
                    title=first_prompt,
                    first_prompt=first_prompt,
                    created_at=first_ts,
                    updated_at=last_ts or first_ts,
                    model=model,
                    git_branch=git_branch,
                )
            )
        return results

    # ------------------------------------------------------------------
    # read_session
    # ------------------------------------------------------------------

    def read_session(self, session_id: str, cwd: str) -> List[Message]:
        """Read messages from a session JSONL file.

        - User messages: extracts message.content only when it is a string
          (skips tool_result arrays).
        - Assistant messages: ONLY processes lines where
          message.stop_reason == "end_turn" (skips streaming partials).
          From assistant content blocks, only extracts type=="text" blocks
          (skips thinking, tool_use).
        - Skips isSidechain == true lines.
        """
        jsonl_path = self._find_session_file(session_id)
        if jsonl_path is None:
            return []

        messages: List[Message] = []

        with open(jsonl_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("isSidechain", False):
                    continue

                msg_type = entry.get("type")
                timestamp = entry.get("timestamp", "")
                msg_data = entry.get("message", {})

                if msg_type == "user":
                    content = msg_data.get("content", "")
                    # Only include string content (skip tool_result arrays)
                    if isinstance(content, str) and content:
                        messages.append(
                            Message(role="user", text=content, timestamp=timestamp)
                        )

                elif msg_type == "assistant":
                    # Skip streaming partials — only process end_turn
                    if msg_data.get("stop_reason") != "end_turn":
                        continue
                    content_blocks = msg_data.get("content", [])
                    if not isinstance(content_blocks, list):
                        continue
                    # Extract only text blocks (skip thinking, tool_use)
                    text_parts = []
                    for block in content_blocks:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                    if text_parts:
                        messages.append(
                            Message(
                                role="assistant",
                                text="\n\n".join(text_parts),
                                timestamp=timestamp,
                            )
                        )

        return messages

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_timestamp(ts: str) -> datetime:
        """Parse an ISO-8601 timestamp string into a timezone-aware datetime."""
        if not ts:
            return datetime.min.replace(tzinfo=timezone.utc)
        # Handle trailing Z
        ts = ts.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(ts)
            # Ensure timezone-aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)
