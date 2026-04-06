# context-bridge

**Bidirectional conversation context between Claude Code and Codex.**

When you switch between Claude Code and Codex, your conversation history stays siloed. context-bridge lets each tool search the other's history — so Claude knows what you built in Codex, and Codex knows what you discussed in Claude.

## Without context-bridge

| Situation | What happens |
|-----------|-------------|
| You built a feature in Codex last week, now using Claude | Claude has no idea. You re-explain everything. |
| You discussed architecture in Claude, now in Codex | Codex starts from scratch. |
| You switch tools mid-project | Context is lost. Both tools ask the same questions. |

## With context-bridge

| Situation | What happens |
|-----------|-------------|
| You built a feature in Codex last week, now using Claude | Claude runs `/codex-context`, finds the thread, and continues where Codex left off. |
| You discussed architecture in Claude, now in Codex | Codex runs `/claude-context`, reads the Claude session, and has full context. |
| You switch tools mid-project | Both tools see the complete history across both platforms. |

## Install

```bash
git clone https://github.com/vguptaa45/context-bridge.git ~/.claude/skills/context-bridge
cd ~/.claude/skills/context-bridge && ./setup
```

That's it. The setup script:
- Installs the `/codex-context` skill in Claude Code
- Installs the `/claude-context` skill in Codex
- Verifies your Python and data sources
- Creates no background processes, installs no dependencies

## How It Works

context-bridge is a Python CLI script with zero external dependencies. It reads directly from the local data stores that Codex and Claude Code already maintain:

| Source | What it reads | Format |
|--------|-------------|--------|
| **Codex** | `~/.codex/state_5.sqlite` (thread index) + `~/.codex/sessions/**/*.jsonl` (transcripts) | SQLite + JSONL |
| **Claude Code** | `~/.claude/projects/*/*.jsonl` (sessions) + `sessions-index.json` (metadata) | JSONL + JSON |

Two SKILL.md files teach each AI tool when and how to invoke the CLI. The AI calls it via `Bash`, reads the stdout, and uses the context.

## Commands

```bash
# See which repos have history in both tools
context-bridge repos

# Recent sessions across both tools
context-bridge recent --days 7

# Search past conversations
context-bridge search "payment webhook" --repo my-project

# Read a specific thread in full
context-bridge thread 01a2b3c4

# Generate a context summary for CLAUDE.md / AGENTS.md
context-bridge sync --repo my-project
```

## Search

Search uses tiered matching for speed:

1. **Tier 1** (instant): Searches thread titles + first user message
2. **Tier 2** (fast): Searches all user prompts across the conversation
3. **Tier 3** (`--deep`): Searches full transcripts including assistant responses

Results are ranked by relevance and weighted by recency — recent conversations always surface first.

## Requirements

- Python 3.8+
- macOS or Linux
- At least one of: Codex (`~/.codex/`) or Claude Code (`~/.claude/`)

No `pip install`. No `npm`. No external dependencies. Just Python stdlib.

## License

MIT
