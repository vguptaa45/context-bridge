"""Tests for lib/codex_reader.py — Codex SQLite + JSONL rollout parsing."""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

# Ensure the project root is importable
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.codex_reader import CodexReader
from lib.types import Session, Message

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ROLLOUT_FIXTURE = FIXTURES / "codex_rollout.jsonl"
HISTORY_FIXTURE = FIXTURES / "codex_history.jsonl"


class TestCodexReader(unittest.TestCase):
    """Tests for CodexReader."""

    def setup_method(self, method):
        """Create a temporary SQLite database with a threads table."""
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()

        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE threads (
                id TEXT PRIMARY KEY,
                rollout_path TEXT,
                created_at INTEGER,
                updated_at INTEGER,
                source TEXT,
                model_provider TEXT,
                cwd TEXT,
                title TEXT,
                first_user_message TEXT DEFAULT '',
                model TEXT,
                git_branch TEXT,
                agent_nickname TEXT,
                archived INTEGER DEFAULT 0
            )
        """)

        # Thread 1: my-project, updated more recently
        conn.execute("""
            INSERT INTO threads
            (id, rollout_path, created_at, updated_at, source, model_provider,
             cwd, title, first_user_message, model, git_branch, agent_nickname, archived)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "thread-001",
            str(ROLLOUT_FIXTURE),
            1743505200,   # 2025-04-01 ~10:00 UTC
            1743505500,   # 2025-04-01 ~10:05 UTC
            "vscode",
            "openai",
            "/Users/test/repos/my-project",
            "Payment webhook flow",
            "How do we handle the payment webhook flow?",
            "gpt-5.2",
            "feature/payments",
            None,
            0,
        ))

        # Thread 2: other-project, updated earlier
        conn.execute("""
            INSERT INTO threads
            (id, rollout_path, created_at, updated_at, source, model_provider,
             cwd, title, first_user_message, model, git_branch, agent_nickname, archived)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "thread-002",
            "/tmp/nonexistent_rollout.jsonl",
            1743418800,   # 2025-03-31 ~10:00 UTC
            1743419100,   # 2025-03-31 ~10:05 UTC
            "terminal",
            "openai",
            "/Users/test/repos/other-project",
            "Database migration check",
            "Please check the database migration status",
            "gpt-5.2",
            "main",
            None,
            0,
        ))

        # Thread 3: archived thread — should be excluded
        conn.execute("""
            INSERT INTO threads
            (id, rollout_path, created_at, updated_at, source, model_provider,
             cwd, title, first_user_message, model, git_branch, agent_nickname, archived)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "thread-003",
            "/tmp/archived.jsonl",
            1743418800,
            1743419100,
            "vscode",
            "openai",
            "/Users/test/repos/my-project",
            "Archived thread",
            "This is archived",
            "gpt-5.2",
            "main",
            None,
            1,
        ))

        # Thread 4: subagent thread — source starts with '{'
        conn.execute("""
            INSERT INTO threads
            (id, rollout_path, created_at, updated_at, source, model_provider,
             cwd, title, first_user_message, model, git_branch, agent_nickname, archived)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "thread-004",
            "/tmp/subagent.jsonl",
            1743418800,
            1743510000,
            '{"parent":"thread-001"}',
            "openai",
            "/Users/test/repos/my-project",
            "Subagent task",
            "Sub-task for parent",
            "gpt-5.2",
            "feature/payments",
            None,
            0,
        ))

        conn.commit()
        conn.close()

        self.reader = CodexReader(
            db_path=self.db_path,
            history_path=str(HISTORY_FIXTURE),
        )

    def teardown_method(self, method):
        """Remove the temporary SQLite file."""
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    # ── list_sessions tests ──────────────────────────────────────────────

    def test_list_sessions_returns_all_non_archived(self):
        """list_sessions() returns all non-archived, non-subagent threads."""
        sessions = self.reader.list_sessions()
        assert len(sessions) == 2
        # All should be non-archived
        ids = [s.id for s in sessions]
        assert "thread-003" not in ids  # archived
        assert "thread-004" not in ids  # subagent

    def test_list_sessions_ordered_by_updated_at_desc(self):
        """Sessions are returned newest-first."""
        sessions = self.reader.list_sessions()
        assert sessions[0].id == "thread-001"  # updated_at 1743505500
        assert sessions[1].id == "thread-002"  # updated_at 1743419100

    def test_list_sessions_filter_by_repo(self):
        """list_sessions(repo='my-project') returns only matching threads."""
        sessions = self.reader.list_sessions(repo="my-project")
        assert len(sessions) == 1
        assert sessions[0].id == "thread-001"
        assert sessions[0].repo == "my-project"

    def test_list_sessions_days_back_zero(self):
        """list_sessions(days_back=0) returns nothing for past fixtures."""
        sessions = self.reader.list_sessions(days_back=0)
        assert len(sessions) == 0

    def test_session_fields(self):
        """Verify session fields are populated correctly."""
        sessions = self.reader.list_sessions(repo="my-project")
        s = sessions[0]
        assert s.source == "codex"
        assert s.cwd == "/Users/test/repos/my-project"
        assert s.title == "Payment webhook flow"
        assert s.model == "gpt-5.2"
        assert s.repo == "my-project"
        assert s.git_branch == "feature/payments"
        assert s.first_prompt == "How do we handle the payment webhook flow?"

    def test_list_sessions_excludes_subagents(self):
        """Subagent threads (source starts with '{') should be excluded."""
        sessions = self.reader.list_sessions()
        ids = [s.id for s in sessions]
        assert "thread-004" not in ids

    # ── read_thread tests ────────────────────────────────────────────────

    def test_read_thread_extracts_messages(self):
        """read_thread parses rollout JSONL and returns user + assistant messages."""
        messages = self.reader.read_thread(str(ROLLOUT_FIXTURE))
        # Should have 2 user + 2 assistant = 4 messages (skip function_call, function_call_output)
        assert len(messages) == 4

    def test_read_thread_roles(self):
        """Messages alternate user, assistant, user, assistant."""
        messages = self.reader.read_thread(str(ROLLOUT_FIXTURE))
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"
        assert messages[2].role == "user"
        assert messages[3].role == "assistant"

    def test_read_thread_content(self):
        """Verify message text content is extracted correctly."""
        messages = self.reader.read_thread(str(ROLLOUT_FIXTURE))
        assert "payment webhook flow" in messages[0].text.lower()
        assert "three-step verification" in messages[1].text.lower()
        assert "retry logic" in messages[2].text.lower()
        assert "exponential backoff" in messages[3].text.lower()

    def test_read_thread_skips_function_calls(self):
        """function_call and function_call_output events are excluded."""
        messages = self.reader.read_thread(str(ROLLOUT_FIXTURE))
        for msg in messages:
            assert "exec_command" not in msg.text
            assert "PaymentHandler" not in msg.text

    # ── get_compacted_summaries tests ────────────────────────────────────

    def test_get_compacted_summaries(self):
        """get_compacted_summaries extracts user messages from compacted events."""
        summaries = self.reader.get_compacted_summaries(str(ROLLOUT_FIXTURE))
        assert len(summaries) == 2
        assert "payment webhook flow" in summaries[0].lower()
        assert "retry logic" in summaries[1].lower()

    # ── get_user_prompts tests ───────────────────────────────────────────

    def test_get_user_prompts(self):
        """get_user_prompts groups prompts by session_id from history.jsonl."""
        prompts = self.reader.get_user_prompts()
        assert "test-codex-001" in prompts
        assert "test-codex-002" in prompts
        assert len(prompts["test-codex-001"]) == 2
        assert len(prompts["test-codex-002"]) == 1
        assert "payment webhook flow" in prompts["test-codex-001"][0].lower()
        assert "database migration" in prompts["test-codex-002"][0].lower()

    # ── resolve_rollout_path tests ───────────────────────────────────────

    def test_resolve_rollout_path(self):
        """resolve_rollout_path looks up rollout_path from SQLite."""
        path = self.reader.resolve_rollout_path("thread-001")
        assert path == str(ROLLOUT_FIXTURE)

    def test_resolve_rollout_path_missing(self):
        """resolve_rollout_path returns None for unknown session_id."""
        path = self.reader.resolve_rollout_path("nonexistent")
        assert path is None


if __name__ == "__main__":
    unittest.main()
