# Context Bridge - Contributor Guide (Codex)

## Quick Start
```bash
./setup
python3 bin/context-bridge recent --source both --days 7
```

## Architecture
- `bin/context-bridge` — CLI entry point, delegates to subcommands
- `lib/codex_reader.py` — Reads Codex SQLite + rollout JSONL files
- `lib/claude_reader.py` — Reads Claude Code session JSONL files
- `lib/search.py` — Tiered keyword search with fuzzy matching
- `lib/formatter.py` — Token-efficient output for AI consumption
- `lib/sync.py` — Generates CLAUDE.md / AGENTS.md context sections

## Testing
```bash
python3 -m pytest test/ -v
```

## Design Principles
- Zero external dependencies (Python stdlib only)
- Recency-first ordering everywhere
- Token-efficient output (skip tool outputs, keep user prompts + assistant conclusions)
- Tiered search: metadata first, full scan only when needed
