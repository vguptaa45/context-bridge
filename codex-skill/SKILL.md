---
name: claude-context
description: Search and retrieve context from previous Claude Code conversations to understand past work, decisions, and architecture
allowed-tools:
  - shell
  - read_file
---

# Claude Code Context Bridge

Use this skill when:
- The user references past work done in Claude Code
- The user asks "what did we do with X", "we built Y before", "remember when we..."
- You need architecture or decision context from prior Claude Code sessions on this repo
- Starting work on a repo that has existing Claude Code history
- The user asks to check or search Claude Code history

## Setup

The CLI is located at `~/.codex/skills/context-bridge/bin/context-bridge`.
If installed elsewhere, check: `ls ~/.codex/skills/context-bridge/bin/`.

## Commands

All commands output concise, token-efficient text. Always start with the lightest query.

### 1. Check what repos have Claude Code history

```bash
python3 ~/.codex/skills/context-bridge/bin/context-bridge repos
```

### 2. See recent Claude Code work on the current repo

```bash
python3 ~/.codex/skills/context-bridge/bin/context-bridge recent --source claude --repo REPO_NAME --days 14
```

Replace `REPO_NAME` with the basename of the current working directory.

### 3. Search for a specific topic

```bash
python3 ~/.codex/skills/context-bridge/bin/context-bridge search "QUERY" --source claude --repo REPO_NAME
```

Add `--days 60` to limit to recent history. Add `--deep` for full transcript search (slower).

### 4. Read a specific thread

After finding a relevant session ID from search/recent:

```bash
python3 ~/.codex/skills/context-bridge/bin/context-bridge thread SESSION_ID --source claude
```

Session IDs look like `a1b2c3d4-e5f6-7890-abcd-ef0123456789`. You can use a prefix.

### 5. Generate a context summary for this repo

```bash
python3 ~/.codex/skills/context-bridge/bin/context-bridge sync --repo REPO_NAME
```

This produces a markdown section you can paste into AGENTS.md.

## Tips
- Start with `recent` or `repos` to orient yourself
- Use `search` with specific keywords from what the user mentioned
- Only use `thread` when you need the full conversation detail
- The output labels messages as YOU (user) and CLAUDE (assistant)
- Session IDs can be shortened to their prefix (first 8 chars)
