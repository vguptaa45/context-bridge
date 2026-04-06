"""Shared data types for context-bridge."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Message:
    """A single message in a conversation."""
    role: str          # "user" or "assistant"
    text: str          # The message content
    timestamp: str     # ISO timestamp


@dataclass
class Session:
    """A conversation session from either Codex or Claude Code."""
    id: str
    source: str                    # "codex" or "claude"
    repo: str                      # Extracted repo name (e.g., "my-project")
    cwd: str                       # Full working directory path
    title: str                     # Thread title or AI-generated summary
    first_prompt: str              # First user message (truncated)
    created_at: datetime
    updated_at: datetime
    model: Optional[str] = None
    git_branch: Optional[str] = None
    messages: List[Message] = field(default_factory=list)
    is_subagent: bool = False


def extract_repo_name(cwd: str) -> str:
    """Extract the repository name from a full path.

    '/home/user/projects/my-app' -> 'my-app'
    '/home/user' -> '~'
    """
    parts = cwd.rstrip("/").split("/")
    # If it's just the home directory
    if len(parts) <= 3:
        return "~"
    return parts[-1]
