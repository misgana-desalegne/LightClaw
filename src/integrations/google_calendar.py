from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from src.models.schemas import CalendarEvent
from src.integrations.token_store import get_token


class CalendarProvider:
    def __init__(self) -> None:
        self._access_token = self._resolve_access_token()
        running_pytest = bool(os.getenv("PYTEST_CURRENT_TEST"))
        self._use_google_api = bool(self._access_token) and not running_pytest
        self.last_error: str | None = None
        self._events: dict[str, CalendarEvent] = {}

    def list_events(self) -> list[CalendarEvent]:
        if self._use_google_api:
            remote_events = self._list_events_google()
            if remote_events:
                return remote_events
        return sorted(self._events.values(), key=lambda event: event.start_time)

    def create_event(self, event_data: dict) -> CalendarEvent:
        if self._use_google_api:
            created = self._create_event_google(event_data)
            if created is not None:
                return created
            raise RuntimeError(self.last_error or "Google Calendar event creation failed")

        event = CalendarEvent(
            id=event_data.get("id") or str(uuid4()),
            title=event_data["title"],
            start_time=self._to_datetime(event_data["start_time"]),
            end_time=self._to_datetime(event_data["end_time"]),
            location=event_data.get("location"),
            description=event_data.get("description"),
            reminder_minutes_before=event_data.get("reminder_minutes_before", 30),
        )
        self._events[event.id] = event
        return event

    def update_event(self, event_id: str, updates: dict) -> CalendarEvent | None:
        if self._use_google_api:
            updated = self._update_event_google(event_id, updates)
            if updated is not None:
                return updated

        existing = self._events.get(event_id)
        if existing is None:
            return None

        merged = existing.model_dump()
        merged.update(updates)
        merged["start_time"] = self._to_datetime(merged["start_time"])
        merged["end_time"] = self._to_datetime(merged["end_time"])
        updated = CalendarEvent(**merged)
        self._events[event_id] = updated
        return updated

    def delete_event(self, event_id: str) -> bool:
        if self._use_google_api and self._delete_event_google(event_id):
            return True
        return self._events.pop(event_id, None) is not None

    def has_conflict(self, start_time: datetime | str, end_time: datetime | str, ignore_event_id: str | None = None) -> bool:
        start = self._to_datetime(start_time)
        end = self._to_datetime(end_time)
        for event in self._events.values():
            if ignore_event_id and event.id == ignore_event_id:
                continue
            if start < event.end_time and end > event.start_time:
                return True
        return False

    @staticmethod
    def _to_datetime(value: datetime | str) -> datetime:
        if isinstance(value, datetime):
            return value
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        return datetime.fromisoformat(value)

    def _list_events_google(self) -> list[CalendarEvent]:
        access_token = self._resolve_access_token()
        if not access_token:
            return []

        time_min = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        query = urlencode({"singleEvents": "true", "orderBy": "startTime", "timeMin": time_min, "maxResults": "20"})
        url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events?{query}"
        payload = self._http_json("GET", url, access_token)
        items = payload.get("items", []) if isinstance(payload, dict) else []
        parsed: list[CalendarEvent] = []

        for item in items:
            start_raw = item.get("start", {}).get("dateTime")
            end_raw = item.get("end", {}).get("dateTime")
            if not (start_raw and end_raw):
                continue
            parsed.append(
                CalendarEvent(
                    id=item.get("id", str(uuid4())),
                    title=item.get("summary", "Untitled"),
                    start_time=self._to_datetime(start_raw),
                    end_time=self._to_datetime(end_raw),
                    location=item.get("location"),
                    description=item.get("description"),
                    reminder_minutes_before=30,
                )
            )
        return parsed

    def _create_event_google(self, event_data: dict) -> CalendarEvent | None:
        access_token = self._resolve_access_token()
        if not access_token:
            return None

        timezone_name = os.getenv("DEFAULT_TIMEZONE", "UTC")
        payload = {
            "summary": event_data["title"],
            "description": event_data.get("description"),
            "location": event_data.get("location"),
            "start": {
                "dateTime": self._to_datetime(event_data["start_time"]).isoformat(),
                "timeZone": timezone_name,
            },
            "end": {
                "dateTime": self._to_datetime(event_data["end_time"]).isoformat(),
                "timeZone": timezone_name,
            },
        }
        result = self._http_json(
            "POST",
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            access_token,
            payload,
        )
        if not isinstance(result, dict) or not result.get("id"):
            self.last_error = f"Calendar create failed: {result}"
            return None

        return CalendarEvent(
            id=result["id"],
            title=result.get("summary", event_data["title"]),
            start_time=self._to_datetime(result.get("start", {}).get("dateTime", payload["start"]["dateTime"])),
            end_time=self._to_datetime(result.get("end", {}).get("dateTime", payload["end"]["dateTime"])),
            location=result.get("location"),
            description=result.get("description"),
            reminder_minutes_before=event_data.get("reminder_minutes_before", 30),
        )

    def _update_event_google(self, event_id: str, updates: dict) -> CalendarEvent | None:
        access_token = self._resolve_access_token()
        if not access_token:
            return None

        existing = self._http_json(
            "GET",
            f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{event_id}",
            access_token,
        )
        if not isinstance(existing, dict) or not existing:
            return None

        timezone_name = os.getenv("DEFAULT_TIMEZONE", "UTC")
        if "title" in updates:
            existing["summary"] = updates["title"]
        if "description" in updates:
            existing["description"] = updates["description"]
        if "location" in updates:
            existing["location"] = updates["location"]
        if "start_time" in updates:
            existing.setdefault("start", {})["dateTime"] = self._to_datetime(updates["start_time"]).isoformat()
            existing.setdefault("start", {})["timeZone"] = timezone_name
        if "end_time" in updates:
            existing.setdefault("end", {})["dateTime"] = self._to_datetime(updates["end_time"]).isoformat()
            existing.setdefault("end", {})["timeZone"] = timezone_name

        updated = self._http_json(
            "PUT",
            f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{event_id}",
            access_token,
            existing,
        )
        if not isinstance(updated, dict) or not updated.get("id"):
            return None

        start = updated.get("start", {}).get("dateTime")
        end = updated.get("end", {}).get("dateTime")
        if not (start and end):
            return None

        return CalendarEvent(
            id=updated["id"],
            title=updated.get("summary", "Untitled"),
            start_time=self._to_datetime(start),
            end_time=self._to_datetime(end),
            location=updated.get("location"),
            description=updated.get("description"),
            reminder_minutes_before=updates.get("reminder_minutes_before", 30),
        )

    def _delete_event_google(self, event_id: str) -> bool:
        access_token = self._resolve_access_token()
        if not access_token:
            return False
        result = self._http_json(
            "DELETE",
            f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{event_id}",
            access_token,
        )
        return result == {} or isinstance(result, dict)

    def _resolve_access_token(self) -> str | None:
        direct_access_token = os.getenv("GOOGLE_CALENDAR_ACCESS_TOKEN") or get_token("GOOGLE_CALENDAR_ACCESS_TOKEN")
        if direct_access_token:
            return direct_access_token

        refresh_token = os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN") or get_token("GOOGLE_CALENDAR_REFRESH_TOKEN")
        client_id = os.getenv("GOOGLE_CALENDAR_CLIENT_ID") or os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET") or os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
        if not (refresh_token and client_id and client_secret):
            return None

        refresh_payload = urlencode(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")
        request = Request(
            "https://oauth2.googleapis.com/token",
            data=refresh_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=15) as response:
                token_response = json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError, json.JSONDecodeError):
            return None

        return token_response.get("access_token")

    @staticmethod
    def _http_json(method: str, url: str, access_token: str, payload: dict | None = None) -> dict:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            url=url,
            data=body,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with urlopen(request, timeout=20) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except HTTPError as error:
            try:
                body = error.read().decode("utf-8")
                parsed = json.loads(body)
                return {"_error": {"status": error.code, "body": parsed}}
            except Exception:  # noqa: BLE001
                return {"_error": {"status": error.code, "reason": str(error)}}
        except (URLError, TimeoutError, json.JSONDecodeError):
            return {}