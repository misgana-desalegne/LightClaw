from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from src.agent.context import Context
from src.integrations.google_calendar import CalendarProvider
from src.models.schemas import SkillResult


class CalendarSkill:
    name = "calendar"
    version = "1.0.0"
    description = "Manage calendar events and scheduling."
    actions = ["create", "update", "delete", "list", "list_today", "schedule_action_items"]
    required_env = ["DEFAULT_TIMEZONE"]

    def __init__(self, provider: CalendarProvider) -> None:
        self.provider = provider

    def can_handle(self, intent: str) -> bool:
        return "calendar" in intent or "schedule" in intent or "event" in intent

    def execute(self, action: str, payload: dict, context: Context) -> SkillResult:
        if action == "create":
            return self._create(payload, context)
        if action == "update":
            return self._update(payload)
        if action == "delete":
            return self._delete(payload)
        if action == "list":
            return SkillResult(
                success=True,
                skill=self.name,
                action=action,
                message="Listed events",
                data={"events": [event.model_dump(mode="json") for event in self.provider.list_events()]},
            )
        if action == "list_today":
            return self._list_today()
        if action == "schedule_action_items":
            return self._schedule_action_items(payload, context)

        return SkillResult(success=False, skill=self.name, action=action, message="Unsupported action")

    def _create(self, payload: dict, context: Context) -> SkillResult:
        required_keys = {"title", "start_time", "end_time"}
        if not required_keys.issubset(payload.keys()):
            return SkillResult(
                success=False,
                skill=self.name,
                action="create",
                message="Missing required fields: title, start_time, end_time",
            )

        start = self._parse_datetime(payload.get("start_time"), default_hour=9, default_minute=0)
        end = self._parse_datetime(payload.get("end_time"), default_hour=10, default_minute=0)
        if start is None or end is None:
            return SkillResult(
                success=False,
                skill=self.name,
                action="create",
                message="Invalid date/time format. Try: '2026-03-13 14:00' or '13 March 2026 at 2pm'.",
            )
        if end <= start:
            end = start + timedelta(hours=1)

        normalized_payload = dict(payload)
        normalized_payload["start_time"] = start.isoformat()
        normalized_payload["end_time"] = end.isoformat()

        if self.provider.has_conflict(normalized_payload["start_time"], normalized_payload["end_time"]):
            return SkillResult(success=False, skill=self.name, action="create", message="Calendar conflict detected")

        try:
            event = self.provider.create_event(normalized_payload)
        except Exception as error:  # noqa: BLE001
            return SkillResult(success=False, skill=self.name, action="create", message=self._humanize_provider_error(error))
        
        context.append_memory("calendar_events", event.model_dump(mode="json"))
        
        # Format the success message with event details for Telegram
        formatted_date = start.strftime("%B %d, %Y")
        formatted_time = start.strftime("%I:%M %p").lstrip("0")
        success_message = f"📅 Calendar event created: '{event.title}' on {formatted_date} at {formatted_time}"
        
        return SkillResult(
            success=True,
            skill=self.name,
            action="create",
            message=success_message,
            data={"event": event.model_dump(mode="json")},
        )

    def _update(self, payload: dict) -> SkillResult:
        event_id = payload.get("id")
        if not event_id:
            return SkillResult(success=False, skill=self.name, action="update", message="Missing event id")

        normalized_payload = dict(payload)
        start_time = payload.get("start_time")
        end_time = payload.get("end_time")
        if start_time:
            parsed_start = self._parse_datetime(start_time)
            if parsed_start is None:
                return SkillResult(success=False, skill=self.name, action="update", message="Invalid start_time format")
            normalized_payload["start_time"] = parsed_start.isoformat()
        if end_time:
            parsed_end = self._parse_datetime(end_time)
            if parsed_end is None:
                return SkillResult(success=False, skill=self.name, action="update", message="Invalid end_time format")
            normalized_payload["end_time"] = parsed_end.isoformat()

        if normalized_payload.get("start_time") and normalized_payload.get("end_time") and self.provider.has_conflict(
            normalized_payload["start_time"],
            normalized_payload["end_time"],
            ignore_event_id=event_id,
        ):
            return SkillResult(success=False, skill=self.name, action="update", message="Calendar conflict detected")

        try:
            updated = self.provider.update_event(event_id, normalized_payload)
        except Exception as error:  # noqa: BLE001
            return SkillResult(success=False, skill=self.name, action="update", message=self._humanize_provider_error(error))
        if updated is None:
            return SkillResult(success=False, skill=self.name, action="update", message="Event not found")

        return SkillResult(
            success=True,
            skill=self.name,
            action="update",
            message="Event updated",
            data={"event": updated.model_dump(mode="json")},
        )

    def _delete(self, payload: dict) -> SkillResult:
        event_id = payload.get("id")
        if not event_id:
            return SkillResult(success=False, skill=self.name, action="delete", message="Missing event id")

        deleted = self.provider.delete_event(event_id)
        if not deleted:
            return SkillResult(success=False, skill=self.name, action="delete", message="Event not found")
        return SkillResult(success=True, skill=self.name, action="delete", message="Event deleted")

    def _list_today(self) -> SkillResult:
        local_today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        all_events = self.provider.list_events()
        today_events = []

        for event in all_events:
            event_start = event.start_time
            if event_start.tzinfo is not None and event_start.utcoffset() is not None:
                # Compare aware datetimes with aware day bounds in the event timezone.
                day_start = local_today_start.replace(tzinfo=event_start.tzinfo)
            else:
                day_start = local_today_start
            day_end = day_start + timedelta(days=1)

            if day_start <= event_start < day_end:
                today_events.append(event)

        return SkillResult(
            success=True,
            skill=self.name,
            action="list_today",
            message=f"Found {len(today_events)} event(s) for today",
            data={"events": [event.model_dump(mode="json") for event in today_events]},
        )

    def _schedule_action_items(self, payload: dict, context: Context) -> SkillResult:
        items = payload.get("items", [])
        scheduled_events = []
        cursor = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

        for item in items:
            title = item.get("title", "Follow-up")
            due_at = item.get("due_at")
            start_time = due_at or cursor.isoformat()
            end_time = (datetime.fromisoformat(start_time) + timedelta(minutes=30)).isoformat()

            while self.provider.has_conflict(start_time, end_time):
                cursor = cursor + timedelta(hours=1)
                start_time = cursor.isoformat()
                end_time = (cursor + timedelta(minutes=30)).isoformat()

            event = self.provider.create_event(
                {
                    "title": f"Action: {title}",
                    "start_time": start_time,
                    "end_time": end_time,
                    "description": "Auto-scheduled from email action item",
                    "reminder_minutes_before": 15,
                }
            )
            scheduled_events.append(event.model_dump(mode="json"))
            cursor = datetime.fromisoformat(end_time) + timedelta(minutes=15)

        context.append_memory("scheduled_action_items", scheduled_events)
        return SkillResult(
            success=True,
            skill=self.name,
            action="schedule_action_items",
            message=f"Scheduled {len(scheduled_events)} action item(s)",
            data={"events": scheduled_events},
        )

    @staticmethod
    def _parse_datetime(value: Any, default_hour: int = 9, default_minute: int = 0) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str):
            return None

        cleaned = value.strip()
        if not cleaned:
            return None

        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"

        try:
            parsed = datetime.fromisoformat(cleaned)
            if len(cleaned) == 10:  # YYYY-MM-DD only
                parsed = parsed.replace(hour=default_hour, minute=default_minute)
            return parsed
        except ValueError:
            pass

        normalized = cleaned.replace(" at ", " ").replace(",", " ")
        normalized = " ".join(normalized.split())

        formats = [
            "%d %B %Y %I%p",
            "%d %b %Y %I%p",
            "%d %B %Y %I:%M%p",
            "%d %b %Y %I:%M%p",
            "%d %B %Y %H:%M",
            "%d %b %Y %H:%M",
            "%d %B %Y",
            "%d %b %Y",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                parsed = datetime.strptime(normalized, fmt)
                if "%H" not in fmt and "%I" not in fmt:
                    parsed = parsed.replace(hour=default_hour, minute=default_minute)
                return parsed
            except ValueError:
                continue

        return None

    @staticmethod
    def _humanize_provider_error(error: Exception) -> str:
        message = str(error)
        lowered = message.lower()
        if "invalid credentials" in lowered or "unauthenticated" in lowered or "status': 401" in lowered:
            return "Google Calendar authentication failed. Reconnect Google from /admin and try again."
        return f"Calendar provider error: {message}"


def create_skill(dependencies: dict[str, Any]) -> CalendarSkill:
    provider = dependencies.get("calendar_provider")
    if not isinstance(provider, CalendarProvider):
        raise ValueError("Missing dependency: calendar_provider")
    return CalendarSkill(provider)