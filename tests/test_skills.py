from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.agent.context import Context
from src.integrations.gmail import GmailProvider
from src.integrations.google_calendar import CalendarProvider
from src.integrations.llm import MockLLMProvider
from src.models.schemas import EmailMessage
from src.skills.calendar.skill import CalendarSkill
from src.skills.email.skill import EmailSkill


def _test_emails() -> list[EmailMessage]:
    now = datetime.now()
    return [
        EmailMessage(
            id="m1",
            subject="Project sync next Monday",
            sender="teamlead@example.com",
            body="Please prepare demo notes before Monday 10:00.",
            received_at=now - timedelta(hours=3),
            unread=True,
        ),
    ]


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
    skill = EmailSkill(GmailProvider(test_emails=_test_emails()), MockLLMProvider())
    result = skill.execute("extract_action_items", {}, Context())
    assert result.success is True
    assert len(result.data["items"]) >= 1


def test_email_summarize_unread_contains_llm_summary() -> None:
    skill = EmailSkill(GmailProvider(test_emails=_test_emails()), MockLLMProvider())
    result = skill.execute("summarize_unread", {}, Context())
    assert result.success is True
    assert "llm_summary" in result.data


def test_calendar_list_today_handles_timezone_aware_events() -> None:
    skill = CalendarSkill(CalendarProvider())
    context = Context()

    start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    end = start + timedelta(hours=1)

    created = skill.execute(
        "create",
        {
            "title": "Timezone Aware Event",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        },
        context,
    )
    assert created.success is True

    listed = skill.execute("list_today", {}, context)
    assert listed.success is True
    assert len(listed.data.get("events", [])) >= 1


def test_calendar_create_accepts_natural_language_date() -> None:
    skill = CalendarSkill(CalendarProvider())
    context = Context()

    result = skill.execute(
        "create",
        {
            "title": "Meeting with Malika",
            "start_time": "13 March 2026",
            "end_time": "13 March 2026",
        },
        context,
    )

    assert result.success is True
    event = result.data.get("event", {})
    assert event.get("start_time")
    assert event.get("end_time")


def test_calendar_create_invalid_datetime_returns_user_error() -> None:
    skill = CalendarSkill(CalendarProvider())
    context = Context()

    result = skill.execute(
        "create",
        {
            "title": "Broken date",
            "start_time": "not-a-date",
            "end_time": "still-not-a-date",
        },
        context,
    )

    assert result.success is False
    assert "Invalid date/time format" in result.message


def test_calendar_create_auth_error_returns_friendly_message() -> None:
    class FailingCalendarProvider(CalendarProvider):
        def create_event(self, event_data: dict):  # type: ignore[override]
            raise RuntimeError("Invalid Credentials")

    skill = CalendarSkill(FailingCalendarProvider())
    context = Context()

    result = skill.execute(
        "create",
        {
            "title": "Auth failure test",
            "start_time": "2026-03-13 14:00",
            "end_time": "2026-03-13 15:00",
        },
        context,
    )

    assert result.success is False
    assert "Reconnect Google" in result.message