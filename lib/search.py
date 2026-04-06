"""Tiered search engine with fuzzy matching and recency weighting."""

import re
from difflib import SequenceMatcher
from datetime import datetime, timezone
from typing import List, Optional
from lib.types import Session


def _fuzzy_contains(query: str, text: str, threshold: float = 0.75) -> bool:
    """Check if query words are found in text, with fuzzy tolerance.

    Each word in query must match a word in text with SequenceMatcher ratio >= threshold, OR be a substring.
    Fast path: if entire query is a substring of text, return True immediately.
    """
    if not query or not text:
        return False
    query_lower = query.lower()
    text_lower = text.lower()

    if query_lower in text_lower:
        return True

    query_words = query_lower.split()
    text_words = re.split(r'\W+', text_lower)

    for qw in query_words:
        found = False
        for tw in text_words:
            if not tw:
                continue
            if qw in tw or tw in qw:
                found = True
                break
            ratio = SequenceMatcher(None, qw, tw).ratio()
            if ratio >= threshold:
                found = True
                break
        if not found:
            return False
    return True


def _score_match(query, title, first_prompt, days_old, prompts_text=""):
    """Score how well a session matches. Returns 0.0 for no match."""
    score = 0.0
    if _fuzzy_contains(query, title):
        score += 10.0
    if _fuzzy_contains(query, first_prompt):
        score += 5.0
    if prompts_text and _fuzzy_contains(query, prompts_text):
        score += 3.0
    if score == 0.0:
        return 0.0
    # Recency multiplier
    if days_old <= 7:
        score *= 3.0
    elif days_old <= 30:
        score *= 2.0
    elif days_old <= 90:
        score *= 1.5
    return score


def search_sessions(sessions, query, user_prompts=None, deep=False):
    """Search sessions using tiered matching. Returns sessions sorted by score."""
    now = datetime.now(timezone.utc)
    scored = []
    for session in sessions:
        days_old = max(0, (now - session.updated_at).days)
        prompts_text = ""
        if user_prompts and session.id in user_prompts:
            prompts_text = " ".join(user_prompts[session.id])
        score = _score_match(
            query=query,
            title=session.title,
            first_prompt=session.first_prompt,
            days_old=days_old,
            prompts_text=prompts_text,
        )
        if score > 0:
            scored.append((score, session))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored]
