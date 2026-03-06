from __future__ import annotations

import re
from datetime import datetime, timedelta

from src.agent.context import Context
from src.integrations.gmail import GmailProvider
from src.integrations.llm import LLMProvider
from src.models.schemas import SkillResult


class EmailSkill:
    name = "email"

    def __init__(self, provider: GmailProvider, llm: LLMProvider) -> None:
        self.provider = provider
        self.llm = llm

    def can_handle(self, intent: str) -> bool:
        return "email" in intent or "inbox" in intent or "unread" in intent

    def execute(self, action: str, payload: dict, context: Context) -> SkillResult:
        if action == "summarize_unread":
            return self._summarize_unread(context)
        if action == "extract_action_items":
            return self._extract_action_items(context)
        if action == "classify":
            return self._classify(payload)
        return SkillResult(success=False, skill=self.name, action=action, message="Unsupported action")

    def _summarize_unread(self, context: Context) -> SkillResult:
        unread_messages = self.provider.list_unread_messages()
        summary = [
            {
                "id": message.id,
                "subject": message.subject,
                "sender": message.sender,
                "snippet": message.body[:120],
            }
            for message in unread_messages
        ]
        llm_summary = self.llm.generate_json(
            system_prompt="Summarize unread emails into key priorities. Return JSON: {\"summary\": string}.",
            user_prompt=f"emails={summary}",
        )
        context.set("last_email_summary", summary)
        return SkillResult(
            success=True,
            skill=self.name,
            action="summarize_unread",
            message=f"Summarized {len(summary)} unread email(s)",
            data={"emails": summary, "llm_summary": llm_summary.get("summary", "")},
        )

    def _classify(self, payload: dict) -> SkillResult:
        text = f"{payload.get('subject', '')} {payload.get('body', '')}".lower()
        if any(word in text for word in ["invoice", "payment", "bill"]):
            label = "finance"
        elif any(word in text for word in ["meeting", "schedule", "deadline"]):
            label = "work"
        elif any(word in text for word in ["event", "meetup", "conference"]):
            label = "events"
        else:
            label = "general"

        return SkillResult(success=True, skill=self.name, action="classify", message="Email classified", data={"label": label})

    def _extract_action_items(self, context: Context) -> SkillResult:
        unread_messages = self.provider.list_unread_messages()
        items: list[dict] = []

        for message in unread_messages:
            combined_text = f"{message.subject} {message.body}".lower()

            llm_result = self.llm.generate_json(
                system_prompt=(
                    "Extract action items from an email. "
                    "Return JSON: {\"items\": [{\"title\": string, \"due_at\": string|null}]}"
                ),
                user_prompt=(
                    f"subject={message.subject}\n"
                    f"body={message.body}\n"
                    "Use ISO datetime for due_at if possible, else null."
                ),
            )

            parsed_items = llm_result.get("items", []) if isinstance(llm_result, dict) else []
            if parsed_items:
                for parsed in parsed_items:
                    items.append(
                        {
                            "title": parsed.get("title") or message.subject,
                            "due_at": parsed.get("due_at"),
                            "source_email_id": message.id,
                        }
                    )
                continue

            looks_actionable = any(
                token in combined_text
                for token in [
                    "please",
                    "prepare",
                    "review",
                    "share",
                    "pay",
                    "invite",
                    "invitation",
                    "meeting",
                    "event",
                    "conference",
                    "webinar",
                    "meetup",
                    "call",
                    "schedule",
                ]
            )
            if looks_actionable:
                due_at = self._extract_due_time(combined_text)
                items.append(
                    {
                        "title": message.subject,
                        "due_at": due_at.isoformat() if due_at else None,
                        "source_email_id": message.id,
                    }
                )

        context.set("email_action_items", items)
        return SkillResult(
            success=True,
            skill=self.name,
            action="extract_action_items",
            message=f"Extracted {len(items)} action item(s)",
            data={"items": items},
        )

    @staticmethod
    def _extract_due_time(body: str) -> datetime | None:
        now = datetime.now()
        if "monday" in body:
            days_to_monday = (0 - now.weekday()) % 7
            return (now + timedelta(days=days_to_monday)).replace(hour=10, minute=0, second=0, microsecond=0)
        if "friday" in body:
            days_to_friday = (4 - now.weekday()) % 7
            return (now + timedelta(days=days_to_friday)).replace(hour=10, minute=0, second=0, microsecond=0)

        time_match = re.search(r"(\d{1,2}):(\d{2})", body)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            return now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=1)
        return None