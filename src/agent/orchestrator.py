from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Callable

from src.agent.context import Context
from src.agent.registry import Skill, SkillRegistry
from src.integrations.llm import LLMProvider
from src.models.schemas import IntentRequest, SkillResult

INTENT_PROMPT = """Classify user message into a specific action intent.

Current datetime: {current_datetime}

Return JSON: {{"intent": "intent_name", "payload": {{}}}}

Supported intents:
- calendar_create: add event (extract title, start_time, end_time in ISO format YYYY-MM-DDTHH:MM:SS)
- calendar_list: show all events
- calendar_today: show today's events
- review_email: summarize last 10 emails
- review_email_today: summarize today's emails
- check_day: show today's calendar and emails
- email_reply: craft reply (extract email_text from message)
- email_analyze: analyze email (extract email_text from message)
- news_fetch: fetch latest news videos (extract category: news/tech/trending, max_results)
- fallback: if no clear action

Date/Time Extraction Rules:
- "tomorrow" = add 1 day to current date
- "13 march 2026" or "march 13 2026" = 2026-03-13
- "6pm" = 18:00, "2pm" = 14:00, "9am" = 09:00
- Default duration: 1 hour if end time not specified
- Always use ISO format: YYYY-MM-DDTHH:MM:SS

Examples:
- "lunch tomorrow 2pm" → {{"intent": "calendar_create", "payload": {{"title": "lunch", "start_time": "2026-03-08T14:00:00", "end_time": "2026-03-08T15:00:00"}}}}
- "Meeting with Marcus for 13 march 2026, 6pm" → {{"intent": "calendar_create", "payload": {{"title": "Meeting with Marcus", "start_time": "2026-03-13T18:00:00", "end_time": "2026-03-13T19:00:00"}}}}
- "check my day" → {{"intent": "check_day", "payload": {{}}}}
- "review email" → {{"intent": "review_email", "payload": {{}}}}
- "fetch latest news" → {{"intent": "news_fetch", "payload": {{"category": "news", "max_results": 5}}}}
- "get tech news" → {{"intent": "news_fetch", "payload": {{"category": "tech", "max_results": 5}}}}
- "show trending videos" → {{"intent": "news_fetch", "payload": {{"category": "trending", "max_results": 10}}}}

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
        
        try:
            result = self.llm.generate_json(system_prompt="", user_prompt=prompt)
            self.logger.info(f"LLM raw result: {result}")
        except Exception as e:
            self.logger.error(f"LLM error: {e}")
            result = {}
            
        if not isinstance(result, dict):
            self.logger.warning(f"LLM returned non-dict: {type(result)}")
            result = {}
            
        # Check for error responses from LLM
        if "error" in result:
            self.logger.error(f"LLM error response: {result}")
            # Try to match simple patterns as fallback
            text_lower = text.lower()
            if "check" in text_lower and "day" in text_lower:
                return {"intent": "check_day", "payload": {}}
            elif "review" in text_lower and "email" in text_lower:
                return {"intent": "review_email", "payload": {}}
            elif any(word in text_lower for word in ["news", "viral", "trending", "tech news"]):
                category = "tech" if "tech" in text_lower else ("trending" if "trending" in text_lower else "news")
                return {"intent": "news_fetch", "payload": {"category": category, "max_results": 5}}
            elif any(word in text_lower for word in ["lunch", "meeting", "dinner", "event"]):
                return {"intent": "calendar_create", "payload": {"title": text}}
            return {"intent": "fallback", "payload": {}}
            
        return {
            "intent": result.get("intent", "fallback"),
            "payload": result.get("payload", {}),
        }

    def _execute_intent(self, classification: dict, sender: str, text: str) -> SkillResult:
        """Route intent to appropriate handler."""
        intent = classification["intent"]
        payload = classification.get("payload", {})

        # Calendar create - execute directly
        if intent == "calendar_create":
            result = self._create_calendar_event(payload, text)
            return result

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
            
        # Email analysis and reply crafting
        if intent == "email_analyze":
            return self._analyze_email(payload)
        if intent == "email_reply":
            return self._craft_email_reply(payload)
            
        # Check day - show today's calendar and recent emails together
        if intent == "check_day":
            return self._check_day(sender)
        
        # News fetching
        if intent == "news_fetch":
            return self._fetch_news(payload)

        # Fallback
        return SkillResult(
            success=False,
            skill="orchestrator",
            action="fallback",
            message="❌ Command not recognized. Try:\n• 'lunch tomorrow at 2pm'\n• 'check my day'\n• 'review email'\n• 'analyze this email: [text]'\n• 'craft reply to: [text]'",
        )

    def _analyze_email(self, payload: dict) -> SkillResult:
        """Analyze an email for sentiment, priority, and key points."""
        email_text = payload.get("email_text", "")
        if not email_text:
            return SkillResult(
                success=False, 
                skill="orchestrator", 
                action="email_analyze",
                message="Please provide the email text to analyze. Example: 'analyze this email: [paste email content]'"
            )
            
        email_skill = self.skill_registry.get_skill("email")
        if not email_skill:
            return SkillResult(
                success=False, 
                skill="orchestrator", 
                action="email_analyze",
                message="Email analysis unavailable - email skill not found"
            )
            
        return email_skill.execute("analyze_email", {"email_text": email_text}, self.context)

    def _craft_email_reply(self, payload: dict) -> SkillResult:
        """Craft a professional reply to an email."""
        email_text = payload.get("email_text", "")
        tone = payload.get("tone", "professional")  # professional, friendly, brief
        intent = payload.get("intent", "acknowledge")  # acknowledge, accept, decline, request_info
        
        if not email_text:
            return SkillResult(
                success=False, 
                skill="orchestrator", 
                action="email_reply",
                message="Please provide the email text to reply to. Example: 'craft reply to: [paste email content]'"
            )
            
        email_skill = self.skill_registry.get_skill("email")
        if not email_skill:
            return SkillResult(
                success=False, 
                skill="orchestrator", 
                action="email_reply",
                message="Email reply unavailable - email skill not found"
            )
            
        return email_skill.execute("craft_reply", {
            "email_text": email_text, 
            "tone": tone, 
            "intent": intent
        }, self.context)

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

    def _fetch_news(self, payload: dict) -> SkillResult:
        """Fetch news, tech, or trending videos."""
        category = payload.get("category", "news")
        max_results = payload.get("max_results", 5)
        
        news_skill = self.skill_registry.get_skill("news_extractor")
        if not news_skill:
            return SkillResult(
                success=False,
                skill="orchestrator",
                action="fetch_news",
                message="News extractor unavailable - skill not loaded"
            )
        
        # Map category to action
        action_map = {
            "news": "fetch_news",
            "tech": "fetch_tech",
            "trending": "fetch_trending"
        }
        
        action = action_map.get(category, "fetch_news")
        return news_skill.execute(action, {"max_results": max_results}, self.context)

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
