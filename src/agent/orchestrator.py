from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Callable

from src.agent.context import Context
from src.agent.registry import Skill, SkillRegistry
from src.integrations.llm import LLMProvider
from src.models.schemas import IntentRequest, SkillResult

INTENT_PROMPT = """You are a productivity assistant. Classify the user's message and extract details.

Current datetime: {current_datetime}

Return JSON with: intent (calendar_create | calendar_list | calendar_today | review_email | review_email_today | check_day | fallback), payload (title, start_time, end_time for calendar), reasoning.

Rules:
- For calendar_create: extract title, start_time (ISO 8601), end_time from natural language
- "tomorrow at 2pm" = tomorrow's date at 14:00, default 1 hour duration
- For calendar_today: show today's calendar events
- For review_email: summarize last 10 emails
- For review_email_today: summarize today's emails only
- For check_day: check both today's emails and calendar events together

User message: {user_message}
"""


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

    def handle_request(self, request: IntentRequest) -> SkillResult:
        """Handle direct skill requests (internal or CLI)."""
        text = request.text.lower()
        
        # Compound intents
        if "summarize my unread emails" in text and "add action items to calendar" in text:
            return self._email_to_calendar_flow()

        skill = self._route(request)
        if skill is None:
            return SkillResult(
                success=False, skill="orchestrator", action="route",
                message=f"No skill for request. Available: {self.skill_registry.list_skills()}",
            )
        action = request.action or "run"
        return self._with_retries(lambda: skill.execute(action, request.payload, self.context), skill.name, action)

    def handle_channel_command(self, text: str, sender: str, provider: object) -> SkillResult:
        """Handle incoming Telegram message."""
        normalize = getattr(provider, "normalize_incoming")
        send_message = getattr(provider, "send_message")
        normalized = normalize(text=text, sender=sender)
        msg = normalized["text"]

        # Check for review commands first (keep, disregard, cancel)
        review_result = self._handle_review_command(msg, sender)
        if review_result:
            send_message(to=sender, message=review_result.message)
            return review_result

        # Classify intent with LLM
        classification = self._classify_intent(msg)
        result = self._execute_intent(classification, sender, msg)
        send_message(to=sender, message=result.message)
        return result

    def handle_whatsapp_command(self, text: str, sender: str, provider: object) -> SkillResult:
        """Backwards-compatible alias for channel command handling."""
        return self.handle_channel_command(text=text, sender=sender, provider=provider)

    def _route(self, request: IntentRequest) -> Skill | None:
        if request.preferred_skill:
            return self.skill_registry.get_skill(request.preferred_skill)
        return self.skill_registry.resolve_by_intent(request.text)

    def _with_retries(self, op: Callable[[], SkillResult], skill: str, action: str) -> SkillResult:
        for attempt in range(self.retries + 1):
            try:
                return op()
            except Exception as e:
                self.logger.warning(f"Retry {attempt+1}: {skill}.{action} failed: {e}")
        return SkillResult(success=False, skill=skill, action=action, message="Execution failed after retries")

    def _classify_intent(self, text: str) -> dict:
        """Use LLM to classify intent and extract payload."""
        prompt = INTENT_PROMPT.format(
            current_datetime=datetime.now().strftime("%Y-%m-%d %H:%M (%A)"),
            user_message=text,
        )
        result = self.llm.generate_json(system_prompt="", user_prompt=prompt)
        if not isinstance(result, dict):
            result = {}
        return {
            "intent": result.get("intent", "fallback"),
            "payload": result.get("payload", {}),
            "reasoning": result.get("reasoning", ""),
        }

    def _execute_intent(self, classification: dict, sender: str, text: str) -> SkillResult:
        """Route intent to appropriate handler."""
        intent = classification["intent"]
        payload = classification.get("payload", {})

        # Calendar create - execute directly
        if intent == "calendar_create":
            return self._create_calendar_event(payload, text)

        # Calendar list
        if intent == "calendar_list":
            return self.handle_request(IntentRequest(text=text, preferred_skill="calendar", action="list"))

        # Calendar today
        if intent == "calendar_today":
            return self.handle_request(IntentRequest(text=text, preferred_skill="calendar", action="list_today"))

        # Review flows - require confirmation
        if intent == "review_email":
            return self._prepare_email_review(sender)
        if intent == "review_email_today":
            return self._summarize_today_emails()
        # Check day - show today's calendar and recent emails together
        if intent == "check_day":
            return self._check_day(sender)

        # Fallback
        return SkillResult(
            success=True, skill="orchestrator", action="help",
            message="I can help with:\n• 'lunch with John tomorrow at 2pm' → add to calendar\n• 'check my day' → see today's schedule + emails\n• 'review email' → check last 10 emails",
        )

    # === Calendar ===
    def _create_calendar_event(self, payload: dict, text: str) -> SkillResult:
        title = payload.get("title") or text[:50]
        start = payload.get("start_time")
        end = payload.get("end_time")

        if not start or not end:
            return SkillResult(success=False, skill="calendar", action="create", message="Missing time. Try: 'lunch tomorrow at 2pm'")

        return self.handle_request(IntentRequest(
            text=text, preferred_skill="calendar", action="create",
            payload={"title": title, "start_time": start, "end_time": end},
        ))

    def _email_to_calendar_flow(self) -> SkillResult:
        """Compound: extract email action items and schedule them."""
        email = self.skill_registry.get_skill("email")
        calendar = self.skill_registry.get_skill("calendar")
        if not email or not calendar:
            return SkillResult(success=False, skill="orchestrator", action="email_to_calendar", message="Email or Calendar skill unavailable")

        email.execute("summarize", {"limit": 10}, self.context)
        extracted = email.execute("extract_action_items", {}, self.context)
        if not extracted.success:
            return extracted

        items = extracted.data.get("items", [])
        scheduled = calendar.execute("schedule_action_items", {"items": items}, self.context)
        return SkillResult(
            success=scheduled.success, skill="orchestrator", action="email_to_calendar",
            message=scheduled.message, data={"items": items, "scheduled_events": scheduled.data.get("events", [])},
        )

    def _summarize_today_emails(self) -> SkillResult:
        """Summarize today's emails."""
        email = self.skill_registry.get_skill("email")
        if not email:
            return SkillResult(success=False, skill="orchestrator", action="summarize_today_emails", message="Email skill unavailable")

        result = email.execute("summarize_today", {}, self.context)
        return SkillResult(
            success=result.success, skill="orchestrator", action="summarize_today_emails",
            message=result.message, data=result.data,
        )

    def _check_day(self, sender: str) -> SkillResult:
        """Check today's calendar events and recent emails together."""
        calendar = self.skill_registry.get_skill("calendar")
        email = self.skill_registry.get_skill("email")

        lines = ["📅 **Your Day Overview**\n"]

        # Today's calendar events
        if calendar:
            cal_result = calendar.execute("list_today", {}, self.context)
            events = cal_result.data.get("events", []) if cal_result.success else []
            if events:
                lines.append("**Today's Events:**")
                for e in events:
                    lines.append(f"• {e['title']} @ {e['start_time'][:16]}")
            else:
                lines.append("**Today's Events:** No events scheduled")
            lines.append("")

        # Recent emails (last 10)
        if email:
            email_result = email.execute("summarize", {"limit": 10}, self.context)
            emails = email_result.data.get("emails", []) if email_result.success else []
            llm_summary = email_result.data.get("llm_summary", "") if email_result.success else ""
            if emails:
                lines.append(f"**Recent Emails ({len(emails)}):**")
                if llm_summary:
                    lines.append(llm_summary)
                else:
                    for em in emails[:5]:
                        status = "📬" if em.get("unread") else "📭"
                        lines.append(f"{status} {em['subject'][:50]} - {em['sender'][:30]}")
            else:
                lines.append("**Recent Emails:** No emails found")

        return SkillResult(
            success=True, skill="orchestrator", action="check_day",
            message="\n".join(lines),
            data={"has_events": bool(events if calendar else False), "email_count": len(emails) if email else 0},
        )

    # === Review Flow ===
    def _review_key(self, sender: str) -> str:
        return f"review:{sender}"

    def _handle_review_command(self, text: str, sender: str) -> SkillResult | None:
        key = self._review_key(sender)
        pending = self.context.get(key)
        if not pending:
            return None

        cmd = text.strip().lower()
        candidates = pending.get("candidates", [])

        if cmd in {"show", "list", "review"}:
            return SkillResult(success=True, skill="orchestrator", action="review_show", message=self._render_candidates(candidates))

        if cmd in {"cancel", "clear"}:
            self.context.remove(key)
            return SkillResult(success=True, skill="orchestrator", action="review_cancel", message="Canceled. No items saved.")

        if cmd in {"keep all", "save all"}:
            return self._save_to_calendar(sender, list(range(len(candidates))))

        if cmd.startswith("keep "):
            indices = [int(x) - 1 for x in re.findall(r"\d+", cmd)]
            return self._save_to_calendar(sender, indices)

        if cmd.startswith(("disregard ", "drop ")):
            drop = {int(x) for x in re.findall(r"\d+", cmd)}
            pending["candidates"] = [c for i, c in enumerate(candidates, 1) if i not in drop]
            self.context.set(key, pending)
            return SkillResult(success=True, skill="orchestrator", action="review_update", message=self._render_candidates(pending["candidates"]))

        return SkillResult(success=True, skill="orchestrator", action="review_help", message="Reply: keep 1,3 | disregard 2 | keep all | cancel")

    def _save_to_calendar(self, sender: str, indices: list[int]) -> SkillResult:
        key = self._review_key(sender)
        pending = self.context.get(key)
        if not pending:
            return SkillResult(success=False, skill="orchestrator", action="review_save", message="No pending items")

        calendar = self.skill_registry.get_skill("calendar")
        if not calendar:
            return SkillResult(success=False, skill="orchestrator", action="review_save", message="Calendar unavailable")

        candidates = pending.get("candidates", [])
        saved = 0
        for i in indices:
            if 0 <= i < len(candidates):
                c = candidates[i]
                result = calendar.execute("create", {"title": c["title"], "start_time": c["start_time"], "end_time": c["end_time"]}, self.context)
                if result.success:
                    saved += 1

        self.context.remove(key)
        return SkillResult(success=saved > 0, skill="orchestrator", action="telegram_review_finalize", message=f"Saved {saved} event(s) to calendar")

    def _prepare_email_review(self, sender: str) -> SkillResult:
        email = self.skill_registry.get_skill("email")
        if not email:
            return SkillResult(success=False, skill="orchestrator", action="telegram_prepare_email_review", message="Email skill unavailable")

        email.execute("summarize", {"limit": 10}, self.context)
        extracted = email.execute("extract_action_items", {}, self.context)
        items = extracted.data.get("items", []) if extracted.success else []

        if not items:
            return SkillResult(success=True, skill="orchestrator", action="telegram_prepare_email_review", message="No action items found in recent emails")

        candidates = self._items_to_candidates(items, "email")
        self.context.set(self._review_key(sender), {"source": "email", "candidates": candidates})
        return SkillResult(success=True, skill="orchestrator", action="telegram_prepare_email_review", message=self._render_candidates(candidates), data={"count": len(candidates)})

    def _items_to_candidates(self, items: list[dict], source: str) -> list[dict]:
        cursor = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        candidates = []
        for item in items:
            start = cursor
            if item.get("due_at"):
                try:
                    start = datetime.fromisoformat(item["due_at"])
                except ValueError:
                    pass
            end = start + timedelta(minutes=30)
            cursor = end + timedelta(minutes=15)
            candidates.append({"title": f"Action: {item.get('title', 'Task')}", "start_time": start.isoformat(), "end_time": end.isoformat(), "source": source})
        return candidates

    def _render_candidates(self, candidates: list[dict]) -> str:
        if not candidates:
            return "No items in queue."
        lines = ["Review items:"]
        for i, c in enumerate(candidates, 1):
            source = c.get('source', '?').capitalize()
            lines.append(f"{i}. [{source}] {c['title']} | {c['start_time']} → {c['end_time']}")
        lines.append("\nReply: keep 1,3 | disregard 2 | keep all | cancel")
        return "\n".join(lines)
