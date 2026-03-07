from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IntentRequest(BaseModel):
    text: str
    preferred_skill: str | None = None
    action: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class SkillResult(BaseModel):
    success: bool
    skill: str
    action: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class CalendarEvent(BaseModel):
    id: str
    title: str
    start_time: datetime
    end_time: datetime
    location: str | None = None
    description: str | None = None
    reminder_minutes_before: int = 30


class EmailMessage(BaseModel):
    id: str
    subject: str
    sender: str
    body: str
    received_at: datetime
    unread: bool = True


class ActionItem(BaseModel):
    title: str
    due_at: datetime | None = None
    source_email_id: str | None = None