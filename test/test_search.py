"""Tests for lib/search.py — tiered search with fuzzy matching."""

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import unittest

# Ensure the project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.search import _fuzzy_contains, _score_match, search_sessions
from lib.types import Session


class TestFuzzyContains(unittest.TestCase):
    """Tests for _fuzzy_contains."""

    def test_exact_substring_match(self):
        assert _fuzzy_contains("webhook", "Setting up a webhook integration") is True

    def test_case_insensitive(self):
        assert _fuzzy_contains("Webhook", "setting up a webhook integration") is True
        assert _fuzzy_contains("webhook", "Setting Up A WEBHOOK Integration") is True

    def test_partial_word_match(self):
        assert _fuzzy_contains("hook", "webhook integration") is True

    def test_no_match_returns_false(self):
        assert _fuzzy_contains("database", "webhook integration") is False

    def test_fuzzy_typo_webhok(self):
        """'webhok' should fuzzy-match 'webhook'."""
        assert _fuzzy_contains("webhok", "webhook integration") is True

    def test_multi_word_all_must_match(self):
        """All query words must match somewhere in text."""
        assert _fuzzy_contains("webhook integration", "Setting up a webhook integration") is True
        assert _fuzzy_contains("webhook database", "Setting up the webhook integration") is False

    def test_empty_query_returns_false(self):
        assert _fuzzy_contains("", "some text") is False

    def test_empty_text_returns_false(self):
        assert _fuzzy_contains("query", "") is False


class TestScoreMatch(unittest.TestCase):
    """Tests for _score_match."""

    def test_title_match_scores_higher_than_prompt_only(self):
        title_score = _score_match(
            query="webhook",
            title="webhook integration",
            first_prompt="unrelated prompt",
            days_old=1,
        )
        prompt_score = _score_match(
            query="webhook",
            title="unrelated title",
            first_prompt="webhook integration",
            days_old=1,
        )
        assert title_score > prompt_score

    def test_recent_scores_higher_than_old(self):
        recent = _score_match(
            query="webhook",
            title="webhook integration",
            first_prompt="setting up webhook",
            days_old=1,
        )
        old = _score_match(
            query="webhook",
            title="webhook integration",
            first_prompt="setting up webhook",
            days_old=90,
        )
        assert recent > old

    def test_no_match_returns_zero(self):
        score = _score_match(
            query="database",
            title="webhook integration",
            first_prompt="setting up webhook",
            days_old=1,
        )
        assert score == 0.0


class TestSearchSessions(unittest.TestCase):
    """Tests for search_sessions."""

    def _make_session(self, id, title, first_prompt, days_old=0):
        now = datetime.now(timezone.utc)
        return Session(
            id=id,
            source="claude",
            repo="test-repo",
            cwd="/tmp/test-repo",
            title=title,
            first_prompt=first_prompt,
            created_at=now - timedelta(days=days_old),
            updated_at=now - timedelta(days=days_old),
        )

    def test_returns_matching_sessions_sorted_by_score(self):
        s1 = self._make_session("1", "webhook setup", "configure hooks", days_old=1)
        s2 = self._make_session("2", "database migration", "webhook handler", days_old=1)
        s3 = self._make_session("3", "unrelated topic", "nothing relevant", days_old=1)

        results = search_sessions([s1, s2, s3], "webhook")
        assert len(results) == 2
        # s1 has title match (higher score), should come first
        assert results[0].id == "1"
        assert results[1].id == "2"

    def test_no_matches_returns_empty(self):
        s1 = self._make_session("1", "webhook setup", "configure hooks")
        results = search_sessions([s1], "database")
        assert results == []

    def test_recency_affects_order(self):
        s_recent = self._make_session("1", "webhook setup", "configure", days_old=1)
        s_old = self._make_session("2", "webhook setup", "configure", days_old=90)

        results = search_sessions([s_old, s_recent], "webhook")
        assert results[0].id == "1"  # recent first

    def test_user_prompts_boost(self):
        s1 = self._make_session("1", "general topic", "unrelated prompt", days_old=1)
        s2 = self._make_session("2", "general topic", "unrelated prompt", days_old=1)

        user_prompts = {"1": ["webhook configuration details"]}
        results = search_sessions([s1, s2], "webhook", user_prompts=user_prompts)
        assert len(results) == 1
        assert results[0].id == "1"


if __name__ == "__main__":
    unittest.main()
