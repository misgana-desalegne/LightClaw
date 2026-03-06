from __future__ import annotations

import logging
from typing import Callable

from src.agent.context import Context
from src.agent.registry import Skill, SkillRegistry
from src.integrations.llm import LLMProvider
from src.integrations.whatsapp import WhatsAppProvider
from src.models.schemas import IntentRequest, SkillResult


class Orchestrator:
    def __init__(
        self,
        skill_registry: SkillRegistry,
        context: Context,
        llm: LLMProvider,
        retries: int = 2,
        logger: logging.Logger | None = None,
    ) -> None:
        self.skill_registry = skill_registry
        self.context = context
        self.llm = llm
        self.retries = retries
        self.logger = logger or logging.getLogger(__name__)

    def route(self, request: IntentRequest) -> Skill | None:
        if request.preferred_skill:
            return self.skill_registry.get_skill(request.preferred_skill)
        return self.skill_registry.resolve_by_intent(request.text)

    def handle_request(self, request: IntentRequest) -> SkillResult:
        intent_text = request.text.lower()
        self._enrich_context_for_intent(intent_text)

        if "summarize my unread emails" in intent_text and "add action items to calendar" in intent_text:
            return self._email_to_calendar_flow()

        if "find ai events this weekend" in intent_text and "schedule the best option" in intent_text:
            return self._event_discovery_to_calendar_flow()

        skill = self.route(request)
        if skill is None:
            return SkillResult(
                success=False,
                skill="orchestrator",
                action=request.action or "route",
                message="No skill could handle the request",
                data={"available_skills": self.skill_registry.list_skills()},
            )

        action = request.action or "run"
        return self._with_retries(lambda: skill.execute(action, request.payload, self.context), skill.name, action)

    def handle_whatsapp_command(self, text: str, sender: str, provider: WhatsAppProvider) -> SkillResult:
        normalized = provider.normalize_incoming(text=text, sender=sender)
        parsed = self.llm.generate_json(
            system_prompt=(
                "Parse WhatsApp command for productivity assistant. "
                "Return JSON: {\"intent\": string, \"payload\": object}. "
                "Supported intents: calendar_create, email_to_calendar, events_to_calendar, fallback."
            ),
            user_prompt=normalized["text"],
        )

        intent = parsed.get("intent", "fallback") if isinstance(parsed, dict) else "fallback"
        payload = parsed.get("payload", {}) if isinstance(parsed, dict) else {}

        if intent == "calendar_create":
            result = self.handle_request(
                IntentRequest(
                    text=normalized["text"],
                    preferred_skill="calendar",
                    action="create",
                    payload=payload,
                )
            )
        elif intent == "email_to_calendar":
            result = self.handle_request(IntentRequest(text="Summarize my unread emails and add action items to calendar"))
        elif intent == "events_to_calendar":
            result = self.handle_request(IntentRequest(text="Find AI events this weekend and schedule the best option"))
        else:
            result = self.handle_request(IntentRequest(text=normalized["text"]))

        provider.send_message(to=sender, message=result.message)
        return result

    def _with_retries(self, operation: Callable[[], SkillResult], skill_name: str, action: str) -> SkillResult:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                return operation()
            except Exception as error:
                last_error = error
                self.logger.warning(
                    "Skill execution failed",
                    extra={"skill": skill_name, "action": action, "attempt": attempt + 1},
                )

        return SkillResult(
            success=False,
            skill=skill_name,
            action=action,
            message=f"Execution failed after retries: {last_error}",
        )

    def _email_to_calendar_flow(self) -> SkillResult:
        email_skill = self.skill_registry.get_skill("email")
        calendar_skill = self.skill_registry.get_skill("calendar")
        if email_skill is None or calendar_skill is None:
            return SkillResult(
                success=False,
                skill="orchestrator",
                action="email_to_calendar",
                message="Email or Calendar skill is not registered",
            )

        email_skill.execute("summarize_unread", {}, self.context)
        extracted = email_skill.execute("extract_action_items", {}, self.context)
        if not extracted.success:
            return extracted

        try:
            scheduled = calendar_skill.execute(
                "schedule_action_items",
                {"items": extracted.data.get("items", [])},
                self.context,
            )
        except Exception as error:  # noqa: BLE001
            return SkillResult(
                success=False,
                skill="orchestrator",
                action="email_to_calendar",
                message=f"Failed scheduling action items: {error}",
            )
        return SkillResult(
            success=scheduled.success,
            skill="orchestrator",
            action="email_to_calendar",
            message=scheduled.message,
            data={"action_items": extracted.data.get("items", []), "scheduled_events": scheduled.data.get("events", [])},
        )

    def _event_discovery_to_calendar_flow(self) -> SkillResult:
        events_skill = self.skill_registry.get_skill("events")
        calendar_skill = self.skill_registry.get_skill("calendar")
        if events_skill is None or calendar_skill is None:
            return SkillResult(
                success=False,
                skill="orchestrator",
                action="events_to_calendar",
                message="Events or Calendar skill is not registered",
            )

        found = events_skill.execute("search", {"query": "AI events this weekend"}, self.context)
        if not found.success:
            return found

        best = events_skill.execute("best_option", {"query": "AI events this weekend"}, self.context)
        if not best.success:
            return SkillResult(
                success=False,
                skill="orchestrator",
                action="events_to_calendar",
                message="No matching events found",
            )

        best_option = best.data.get("event")
        if not best_option:
            return SkillResult(
                success=False,
                skill="orchestrator",
                action="events_to_calendar",
                message="No matching events found",
            )

        scheduled = calendar_skill.execute("create", best_option, self.context)
        return SkillResult(
            success=scheduled.success,
            skill="orchestrator",
            action="events_to_calendar",
            message=scheduled.message,
            data={"chosen_event": best_option, "calendar_event": scheduled.data.get("event")},
        )

    def _enrich_context_for_intent(self, intent_text: str) -> None:
        email_skill = self.skill_registry.get_skill("email")
        events_skill = self.skill_registry.get_skill("events")

        if email_skill and any(token in intent_text for token in ["email", "inbox", "task"]):
            email_skill.execute("summarize_unread", {}, self.context)

        if events_skill and any(token in intent_text for token in ["event", "conference", "meetup", "search"]):
            query = "AI events this weekend" if "weekend" in intent_text else "upcoming events"
            events_skill.execute("search", {"query": query}, self.context)