from __future__ import annotations

from src.agent.context import Context
from src.agent.orchestrator import Orchestrator
from src.agent.registry import SkillRegistry
from src.integrations.gmail import GmailProvider
from src.integrations.google_calendar import CalendarProvider
from src.integrations.llm import MockLLMProvider
from src.integrations.whatsapp import WhatsAppProvider
from src.integrations.web_search import WebSearchProvider
from src.models.schemas import IntentRequest
from src.skills.calendar.skill import CalendarSkill
from src.skills.email.skill import EmailSkill
from src.skills.events.skill import EventsSkill


def build_orchestrator() -> Orchestrator:
    llm = MockLLMProvider()
    registry = SkillRegistry()
    registry.register_skill(CalendarSkill(CalendarProvider()))
    registry.register_skill(EmailSkill(GmailProvider(), llm))
    registry.register_skill(EventsSkill(WebSearchProvider(), llm))
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


def test_events_to_calendar_compound_intent() -> None:
    orchestrator = build_orchestrator()
    result = orchestrator.handle_request(
        IntentRequest(text="Find AI events this weekend and schedule the best option")
    )
    assert result.success is True
    assert result.action == "events_to_calendar"


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