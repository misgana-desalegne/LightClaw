from __future__ import annotations

import re
from datetime import datetime, timedelta

from src.agent.context import Context
from src.integrations.gmail import GmailProvider
from src.integrations.llm import LLMProvider
from src.models.schemas import SkillResult


class EmailSkill:
    name = "email"
    version = "1.0.0"
    description = "Summarize inbox messages, extract actionable items, and craft email replies."
    actions = ["summarize_unread", "summarize", "summarize_today", "extract_action_items", "classify", "craft_reply", "analyze_email"]
    required_env = ["GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET"]

    def __init__(self, provider: GmailProvider, llm: LLMProvider) -> None:
        self.provider = provider
        self.llm = llm

    def can_handle(self, intent: str) -> bool:
        return "email" in intent or "inbox" in intent or "unread" in intent

    def execute(self, action: str, payload: dict, context: Context) -> SkillResult:
        if action == "summarize_unread":
            return self._summarize_unread(context)
        if action == "summarize":
            return self._summarize_recent(context, limit=payload.get("limit", 10))
        if action == "summarize_today":
            return self._summarize_today(context)
        if action == "extract_action_items":
            return self._extract_action_items(context)
        if action == "classify":
            return self._classify(payload)
        if action == "craft_reply":
            return self._craft_reply(payload, context)
        if action == "analyze_email":
            return self._analyze_email(payload, context)
        return SkillResult(success=False, skill=self.name, action=action, message="Unsupported action")

    def _summarize_recent(self, context: Context, limit: int = 10) -> SkillResult:
        messages = self.provider.list_recent_messages(limit=limit)
        if not messages:
            return SkillResult(
                success=True,
                skill=self.name,
                action="summarize",
                message="No emails found. Connect Gmail via /admin to access your inbox.",
                data={"emails": [], "llm_summary": ""},
            )
        summary = [
            {
                "id": message.id,
                "subject": message.subject,
                "sender": message.sender,
                "snippet": message.body[:120],
                "unread": message.unread,
            }
            for message in messages
        ]
        llm_summary = self.llm.generate_json(
            system_prompt="Summarize emails into key priorities. Return JSON: {\"summary\": string}.",
            user_prompt=f"emails={summary}",
        )
        context.set("last_email_summary", summary)
        return SkillResult(
            success=True,
            skill=self.name,
            action="summarize",
            message=f"Summarized {len(summary)} recent email(s)",
            data={"emails": summary, "llm_summary": llm_summary.get("summary", "")},
        )

    def _summarize_today(self, context: Context) -> SkillResult:
        messages = self.provider.list_today_messages()
        if not messages:
            return SkillResult(
                success=True,
                skill=self.name,
                action="summarize_today",
                message="No emails received today. Connect Gmail via /admin if not already connected.",
                data={"emails": [], "llm_summary": ""},
            )
        summary = [
            {
                "id": message.id,
                "subject": message.subject,
                "sender": message.sender,
                "snippet": message.body[:120],
                "unread": message.unread,
            }
            for message in messages
        ]
        llm_summary = self.llm.generate_json(
            system_prompt="Summarize today's emails into key priorities. Return JSON: {\"summary\": string}.",
            user_prompt=f"emails={summary}",
        )
        context.set("last_email_summary", summary)
        return SkillResult(
            success=True,
            skill=self.name,
            action="summarize_today",
            message=f"Summarized {len(summary)} email(s) from today",
            data={"emails": summary, "llm_summary": llm_summary.get("summary", "")},
        )

    def _summarize_unread(self, context: Context) -> SkillResult:
        unread_messages = self.provider.list_unread_messages()
        if not unread_messages:
            return SkillResult(
                success=True,
                skill=self.name,
                action="summarize_unread",
                message="No unread emails. Connect Gmail via /admin if not already connected.",
                data={"emails": [], "llm_summary": ""},
            )
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
        messages = self.provider.list_recent_messages(limit=10)
        if not messages:
            return SkillResult(
                success=True,
                skill=self.name,
                action="extract_action_items",
                message="No emails to extract action items from. Connect Gmail via /admin.",
                data={"items": []},
            )
        items: list[dict] = []

        for message in messages:
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

    def _craft_reply(self, payload: dict, context: Context) -> SkillResult:
        """Craft a professional email reply based on the input email content."""
        email_text = payload.get("email_text", "").strip()
        reply_tone = payload.get("tone", "professional")  # professional, friendly, brief
        reply_intent = payload.get("intent", "acknowledge")  # acknowledge, accept, decline, request_info
        
        if not email_text:
            return SkillResult(
                success=False,
                skill=self.name,
                action="craft_reply",
                message="No email text provided. Please include the email content to reply to.",
            )

        # Use LLM to craft a contextual reply
        system_prompt = f"""You are an email assistant. Craft a {reply_tone} email reply based on the intent: {reply_intent}.

Reply guidelines:
- Be {reply_tone} in tone
- Keep it concise but complete
- Include appropriate greetings and closings
- Address the main points from the original email
- Return JSON: {{"reply": "email content", "subject": "suggested subject line"}}
"""
        
        user_prompt = f"""Original email content:
{email_text}

Intent: {reply_intent}
Tone: {reply_tone}

Craft an appropriate reply."""

        llm_result = self.llm.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
        
        if not isinstance(llm_result, dict) or "reply" not in llm_result:
            return SkillResult(
                success=False,
                skill=self.name,
                action="craft_reply",
                message="Failed to generate reply. Please try again.",
                data={"error": llm_result},
            )

        reply_text = llm_result.get("reply", "")
        suggested_subject = llm_result.get("subject", "Re: Your Email")
        
        # Store in context for potential sending later
        context.set("last_crafted_reply", {
            "reply": reply_text,
            "subject": suggested_subject,
            "original_email": email_text,
            "tone": reply_tone,
            "intent": reply_intent,
            "created_at": datetime.now().isoformat()
        })
        
        return SkillResult(
            success=True,
            skill=self.name,
            action="craft_reply",
            message=f"📧 **Crafted {reply_tone} reply ({reply_intent}):**\n\n**Subject:** {suggested_subject}\n\n**Reply:**\n{reply_text}",
            data={
                "reply": reply_text,
                "subject": suggested_subject,
                "tone": reply_tone,
                "intent": reply_intent
            },
        )

    def _analyze_email(self, payload: dict, context: Context) -> SkillResult:
        """Analyze an email and provide summary, sentiment, and key points."""
        email_text = payload.get("email_text", "").strip()
        
        if not email_text:
            return SkillResult(
                success=False,
                skill=self.name,
                action="analyze_email",
                message="No email text provided. Please include the email content to analyze.",
            )

        system_prompt = """Analyze the email content and provide insights. Return JSON with:
{
  "summary": "brief summary in 1-2 sentences",
  "sentiment": "positive/neutral/negative/urgent",
  "key_points": ["point1", "point2", "point3"],
  "action_required": "yes/no",
  "priority": "low/medium/high",
  "category": "work/personal/finance/event/other"
}"""

        user_prompt = f"Email content to analyze:\n{email_text}"
        
        llm_result = self.llm.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
        
        if not isinstance(llm_result, dict):
            return SkillResult(
                success=False,
                skill=self.name,
                action="analyze_email",
                message="Failed to analyze email. Please try again.",
                data={"error": llm_result},
            )

        summary = llm_result.get("summary", "No summary available")
        sentiment = llm_result.get("sentiment", "neutral")
        key_points = llm_result.get("key_points", [])
        action_required = llm_result.get("action_required", "no")
        priority = llm_result.get("priority", "medium")
        category = llm_result.get("category", "other")
        
        # Format the response
        emoji_map = {
            "positive": "😊",
            "neutral": "😐", 
            "negative": "😟",
            "urgent": "🚨"
        }
        
        priority_emoji_map = {
            "low": "🟢",
            "medium": "🟡", 
            "high": "🔴"
        }
        
        sentiment_emoji = emoji_map.get(sentiment, "📧")
        priority_emoji = priority_emoji_map.get(priority, "⚪")
        
        message = f"""📧 **Email Analysis:**

**Summary:** {summary}

**Sentiment:** {sentiment_emoji} {sentiment.title()}
**Priority:** {priority_emoji} {priority.title()}
**Category:** {category.title()}
**Action Required:** {"✅ Yes" if action_required == "yes" else "❌ No"}

**Key Points:**"""

        for i, point in enumerate(key_points, 1):
            message += f"\n{i}. {point}"
            
        context.set("last_email_analysis", {
            "analysis": llm_result,
            "email_text": email_text,
            "analyzed_at": datetime.now().isoformat()
        })
        
        return SkillResult(
            success=True,
            skill=self.name,
            action="analyze_email",
            message=message,
            data=llm_result,
        )


def create_skill(dependencies: dict[str, object]) -> EmailSkill:
    provider = dependencies.get("gmail_provider")
    llm = dependencies.get("llm_provider")
    if not isinstance(provider, GmailProvider):
        raise ValueError("Missing dependency: gmail_provider")
    if not isinstance(llm, LLMProvider):
        raise ValueError("Missing dependency: llm_provider")
    return EmailSkill(provider, llm)