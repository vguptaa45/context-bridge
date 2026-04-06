---
name: codex-context
description: Search and retrieve context from previous Codex (OpenAI) coding sessions to understand past work, decisions, and architecture
allowed-tools:
  - Bash
  - Read
---

# Codex Context Bridge

Use this skill when:
- The user references past work done in Codex / OpenAI Codex Desktop
- The user asks "what did we do with X", "we built Y before", "remember when we..."
- You need architecture or decision context from prior Codex sessions on this repo
- Starting work on a repo that has existing Codex history
- The user asks to check or search Codex history

## Setup

The CLI is located at `~/.claude/skills/context-bridge/bin/context-bridge`.
If installed elsewhere, check: `which context-bridge` or `ls ~/.claude/skills/context-bridge/bin/`.

## Commands

All commands output concise, token-efficient text. Always start with the lightest query.

### 1. Check what repos have Codex history

```bash
python3 ~/.claude/skills/context-bridge/bin/context-bridge repos
```

### 2. See recent Codex work on the current repo

```bash
python3 ~/.claude/skills/context-bridge/bin/context-bridge recent --source codex --repo REPO_NAME --days 14
```

Replace `REPO_NAME` with the basename of the current working directory (e.g., `my-backend-api`).

### 3. Search for a specific topic

```bash
python3 ~/.claude/skills/context-bridge/bin/context-bridge search "QUERY" --source codex --repo REPO_NAME
```

Add `--days 60` to limit to recent history. Add `--deep` for full transcript search (slower).

### 4. Read a specific thread

After finding a relevant thread ID from search/recent:

```bash
python3 ~/.claude/skills/context-bridge/bin/context-bridge thread THREAD_ID --source codex
```

Thread IDs look like `01a2b3c4-d5e6-7f89-0abc-def012345678`. You can use a prefix (e.g., `01a2b3c4`).

### 5. Generate a context summary for this repo

```bash
python3 ~/.claude/skills/context-bridge/bin/context-bridge sync --repo REPO_NAME
```

This produces a markdown section you can paste into CLAUDE.md.

## Tips
- Start with `recent` or `repos` to orient yourself
- Use `search` with specific keywords from what the user mentioned
- Only use `thread` when you need the full conversation detail
- The output labels messages as YOU (user) and CODEX (assistant)
- Thread IDs can be shortened to their prefix (first 8 chars)
