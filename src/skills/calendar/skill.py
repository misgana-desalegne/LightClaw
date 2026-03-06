from __future__ import annotations

from datetime import datetime, timedelta

from src.agent.context import Context
from src.integrations.google_calendar import CalendarProvider
from src.models.schemas import SkillResult


class CalendarSkill:
    name = "calendar"

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

        if self.provider.has_conflict(payload["start_time"], payload["end_time"]):
            return SkillResult(success=False, skill=self.name, action="create", message="Calendar conflict detected")

        event = self.provider.create_event(payload)
        context.append_memory("calendar_events", event.model_dump(mode="json"))
        return SkillResult(
            success=True,
            skill=self.name,
            action="create",
            message="Event created",
            data={"event": event.model_dump(mode="json")},
        )

    def _update(self, payload: dict) -> SkillResult:
        event_id = payload.get("id")
        if not event_id:
            return SkillResult(success=False, skill=self.name, action="update", message="Missing event id")

        start_time = payload.get("start_time")
        end_time = payload.get("end_time")
        if start_time and end_time and self.provider.has_conflict(start_time, end_time, ignore_event_id=event_id):
            return SkillResult(success=False, skill=self.name, action="update", message="Calendar conflict detected")

        updated = self.provider.update_event(event_id, payload)
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