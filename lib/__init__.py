"""context-bridge: Bidirectional conversation context between Claude Code and Codex."""

from pathlib import Path

VERSION = (Path(__file__).parent.parent / "VERSION").read_text().strip()

CODEX_HOME = Path.home() / ".codex"
CLAUDE_HOME = Path.home() / ".claude"
