"""Token-efficient output formatting for AI consumption."""

from typing import List
from lib.types import Session, Message


def format_session_list(
    sessions: List[Session],
    verbose: bool = False,
    last_prompts: dict = None,
) -> str:
    """Format a list of sessions as concise text output.

    Args:
        last_prompts: Optional dict of session_id -> list of user prompt strings.
                      If provided, shows the last 3 prompts to indicate what the
                      conversation is *currently* about (not just how it started).
    """
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
            title_short = s.title[:100].replace("\n", " ")
            if len(s.title) > 100:
                title_short += "..."
            line += f"\n  Title: {title_short}"
        line += f"\n  First: {prompt_preview}"

        # Show last few prompts if available (reveals current topic)
        if last_prompts and s.id in last_prompts:
            recent = last_prompts[s.id]
            if len(recent) > 1:
                tail = recent[-3:]  # Last 3 prompts
                line += f"\n  Recent ({len(recent)} turns):"
                for p in tail:
                    p_short = p[:100].replace("\n", " ")
                    if len(p) > 100:
                        p_short += "..."
                    line += f"\n    - {p_short}"

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
