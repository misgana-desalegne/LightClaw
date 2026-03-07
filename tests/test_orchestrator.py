from __future__ import annotations

from datetime import datetime, timedelta

from src.agent.context import Context
from src.agent.orchestrator import Orchestrator
from src.agent.registry import SkillRegistry
from src.integrations.gmail import GmailProvider
from src.integrations.google_calendar import CalendarProvider
from src.integrations.llm import MockLLMProvider
from src.integrations.whatsapp import WhatsAppProvider
from src.models.schemas import EmailMessage, IntentRequest
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


class TelegramProvider:
    def __init__(self) -> None:
        self.outbox: list[dict[str, str]] = []

    def normalize_incoming(self, text: str, sender: str) -> dict[str, str]:
        return {"text": text, "sender": sender}

    def send_message(self, to: str, message: str) -> dict[str, str]:
        payload = {"to": to, "message": message}
        self.outbox.append(payload)
        return payload


def build_orchestrator() -> Orchestrator:
    llm = MockLLMProvider()
    registry = SkillRegistry()
    registry.register_skill(CalendarSkill(CalendarProvider()))
    registry.register_skill(EmailSkill(GmailProvider(test_emails=_test_emails()), llm))
    return Orchestrator(skill_registry=registry, context=Context(), llm=llm, retries=1)


def test_routes_to_explicit_skill() -> None:
    orchestrator = build_orchestrator()
    result = orchestrator.handle_request(
        IntentRequest(
            text="create a calendar event",
            preferred_skill="calendar",
            action="create",
            payload={
                "title": "Team sync",
                "start_time": "2026-03-07T10:00:00",
                "end_time": "2026-03-07T11:00:00",
            },
        )
    )
    assert result.success is True
    assert result.skill == "calendar"


def test_email_to_calendar_compound_intent() -> None:
    orchestrator = build_orchestrator()
    result = orchestrator.handle_request(
        IntentRequest(text="Summarize my unread emails and add action items to calendar")
    )
    assert result.success is True
    assert result.action == "email_to_calendar"
    assert len(result.data["scheduled_events"]) >= 1


def test_whatsapp_add_task_command() -> None:
    orchestrator = build_orchestrator()
    whatsapp = WhatsAppProvider()
    result = orchestrator.handle_whatsapp_command(
        text="add task prepare sprint summary",
        sender="+15551234567",
        provider=whatsapp,
    )
    assert result.success is True
    assert len(whatsapp.list_outbox()) == 1


def test_telegram_email_review_requires_confirmation_before_calendar_write() -> None:
    orchestrator = build_orchestrator()
    telegram = TelegramProvider()
    sender = "tg-user"

    prepared = orchestrator.handle_channel_command(
        text="review email",
        sender=sender,
        provider=telegram,
    )
    assert prepared.success is True
    assert prepared.action == "telegram_prepare_email_review"

    listed_before = orchestrator.handle_request(
        IntentRequest(text="list events", preferred_skill="calendar", action="list")
    )
    assert listed_before.success is True
    assert len(listed_before.data.get("events", [])) == 0

    approved = orchestrator.handle_channel_command(
        text="keep 1",
        sender=sender,
        provider=telegram,
    )
    assert approved.action == "telegram_review_finalize"

    listed_after = orchestrator.handle_request(
        IntentRequest(text="list events", preferred_skill="calendar", action="list")
    )
    assert listed_after.success is True
    assert len(listed_after.data.get("events", [])) >= 1