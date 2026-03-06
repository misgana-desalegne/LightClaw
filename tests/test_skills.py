from __future__ import annotations

from src.agent.context import Context
from src.integrations.gmail import GmailProvider
from src.integrations.google_calendar import CalendarProvider
from src.integrations.llm import MockLLMProvider
from src.integrations.web_search import WebSearchProvider
from src.skills.calendar.skill import CalendarSkill
from src.skills.email.skill import EmailSkill
from src.skills.events.skill import EventsSkill


def test_calendar_create_conflict_detection() -> None:
    skill = CalendarSkill(CalendarProvider())
    context = Context()

    first = skill.execute(
        "create",
        {
            "title": "Planning",
            "start_time": "2026-03-08T09:00:00",
            "end_time": "2026-03-08T10:00:00",
        },
        context,
    )
    assert first.success is True

    conflict = skill.execute(
        "create",
        {
            "title": "Overlap",
            "start_time": "2026-03-08T09:30:00",
            "end_time": "2026-03-08T10:30:00",
        },
        context,
    )
    assert conflict.success is False


def test_email_extract_action_items() -> None:
    skill = EmailSkill(GmailProvider(), MockLLMProvider())
    result = skill.execute("extract_action_items", {}, Context())
    assert result.success is True
    assert len(result.data["items"]) >= 1


def test_email_summarize_unread_contains_llm_summary() -> None:
    skill = EmailSkill(GmailProvider(), MockLLMProvider())
    result = skill.execute("summarize_unread", {}, Context())
    assert result.success is True
    assert "llm_summary" in result.data


def test_events_search_returns_suggestions() -> None:
    skill = EventsSkill(WebSearchProvider(), MockLLMProvider())
    result = skill.execute("search", {"query": "AI events this weekend"}, Context())
    assert result.success is True
    assert len(result.data["events"]) >= 1