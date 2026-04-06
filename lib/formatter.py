"""Token-efficient output formatting for AI consumption."""

from typing import List
from lib.types import Session, Message


def format_session_list(sessions: List[Session], verbose: bool = False) -> str:
    """Format a list of sessions as concise text output."""
    if not sessions:
        return "No sessions found."
    lines = []
    for s in sessions:
        date = s.updated_at.strftime("%Y-%m-%d")
        source_tag = s.source.upper()
        prompt_preview = s.first_prompt[:120].replace("\n", " ")
        if len(s.first_prompt) > 120:
            prompt_preview += "..."
        line = f"[{source_tag}] {date} | {s.repo} | {s.id}"
        if s.title:
            line += f"\n  Title: {s.title}"
        line += f"\n  Prompt: {prompt_preview}"
        if verbose and s.model:
            line += f"\n  Model: {s.model}"
            if s.git_branch:
                line += f" | Branch: {s.git_branch}"
        lines.append(line)
    return "\n\n".join(lines)


def format_thread_messages(session: Session, messages: List[Message], max_assistant_chars: int = 1000) -> str:
    """Format a full thread conversation for AI consumption."""
    header = (
        f"=== [{session.source.upper()}] {session.updated_at.strftime('%Y-%m-%d')} "
        f"| {session.repo} | {session.id} ===\n"
    )
    if session.title:
        header += f"Title: {session.title}\n"
    if session.model:
        header += f"Model: {session.model}\n"
    header += "---"
    parts = [header]
    for msg in messages:
        label = "YOU" if msg.role == "user" else session.source.upper()
        text = msg.text
        if msg.role == "assistant" and len(text) > max_assistant_chars:
            text = text[:max_assistant_chars] + "\n  [... truncated]"
        text_lines = text.split("\n")
        formatted = text_lines[0]
        if len(text_lines) > 1:
            formatted += "\n" + "\n".join("  " + l for l in text_lines[1:])
        parts.append(f"\n{label}: {formatted}")
    return "\n".join(parts)


def format_repos(repos: list) -> str:
    """Format a list of (repo_name, codex_count, claude_count) tuples."""
    if not repos:
        return "No repositories found."
    lines = ["REPO                              CODEX  CLAUDE"]
    lines.append("-" * 50)
    for repo_name, codex_count, claude_count in repos:
        lines.append(f"{repo_name:<34}{codex_count:>5}  {claude_count:>6}")
    return "\n".join(lines)
