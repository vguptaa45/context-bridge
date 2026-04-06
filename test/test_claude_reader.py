"""Tests for the Claude Code session reader."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from lib.claude_reader import ClaudeReader


FIXTURE_DIR = Path(__file__).parent / "fixtures"


class TestClaudeReader:
    """Tests for ClaudeReader covering list_sessions and read_session."""

    def setup_method(self):
        """Create a temp directory mimicking ~/.claude/ with a project."""
        self.tmp = tempfile.mkdtemp()
        self.claude_home = Path(self.tmp)

        # Create project directory: -Users-test-repos-my-project
        self.project_dir = self.claude_home / "projects" / "-Users-test-repos-my-project"
        self.project_dir.mkdir(parents=True)

        # Copy the fixture JSONL as test-claude-001.jsonl
        src = FIXTURE_DIR / "claude_session.jsonl"
        dst = self.project_dir / "test-claude-001.jsonl"
        shutil.copy(src, dst)

        # Create sessions-index.json
        index = [
            {
                "sessionId": "test-claude-001",
                "firstPrompt": "How does the auth middleware work?",
                "summary": "Auth middleware and rate limiting discussion",
                "created": "2026-04-01T11:00:00.000Z",
                "modified": "2026-04-01T11:01:30.000Z",
                "gitBranch": "main",
                "projectPath": "/Users/test/repos/my-project",
                "isSidechain": False,
            }
        ]
        (self.project_dir / "sessions-index.json").write_text(json.dumps(index))

        self.reader = ClaudeReader(claude_home=self.claude_home)

    def teardown_method(self):
        """Remove the temp directory."""
        shutil.rmtree(self.tmp)

    def test_list_sessions_returns_at_least_one(self):
        sessions = self.reader.list_sessions()
        assert len(sessions) >= 1

    def test_list_sessions_filter_by_repo(self):
        sessions = self.reader.list_sessions(repo="my-project")
        assert len(sessions) >= 1
        for s in sessions:
            assert s.repo == "my-project"

    def test_list_sessions_filter_by_repo_no_match(self):
        sessions = self.reader.list_sessions(repo="nonexistent-repo")
        assert len(sessions) == 0

    def test_session_fields(self):
        sessions = self.reader.list_sessions()
        s = sessions[0]
        assert s.source == "claude"
        assert s.title == "Auth middleware and rate limiting discussion"
        assert s.model == "claude-opus-4-6"

    def test_session_id_and_repo(self):
        sessions = self.reader.list_sessions()
        s = sessions[0]
        assert s.id == "test-claude-001"
        assert s.repo == "my-project"
        assert s.cwd == "/Users/test/repos/my-project"

    def test_read_session_message_count(self):
        """Should return 2 user + 2 assistant messages (streaming partials deduped)."""
        messages = self.reader.read_session("test-claude-001", cwd="/Users/test/repos/my-project")
        user_msgs = [m for m in messages if m.role == "user"]
        asst_msgs = [m for m in messages if m.role == "assistant"]
        assert len(user_msgs) == 2
        assert len(asst_msgs) == 2

    def test_thinking_blocks_excluded(self):
        """Thinking blocks must NOT appear in message text."""
        messages = self.reader.read_session("test-claude-001", cwd="/Users/test/repos/my-project")
        for m in messages:
            assert "Let me look at the auth code" not in m.text

    def test_tool_use_blocks_excluded(self):
        """tool_use blocks must NOT be included -- only text blocks from assistant."""
        messages = self.reader.read_session("test-claude-001", cwd="/Users/test/repos/my-project")
        for m in messages:
            assert "cat auth.py" not in m.text
            assert "toolu_001" not in m.text

    def test_assistant_text_content(self):
        """Verify the actual text content of assistant messages."""
        messages = self.reader.read_session("test-claude-001", cwd="/Users/test/repos/my-project")
        asst_msgs = [m for m in messages if m.role == "assistant"]
        assert "JWT tokens" in asst_msgs[0].text
        assert "rate limiter" in asst_msgs[1].text

    def test_user_text_content(self):
        """Verify user message content."""
        messages = self.reader.read_session("test-claude-001", cwd="/Users/test/repos/my-project")
        user_msgs = [m for m in messages if m.role == "user"]
        assert user_msgs[0].text == "How does the auth middleware work?"
        assert user_msgs[1].text == "Can you add rate limiting to the auth layer?"
