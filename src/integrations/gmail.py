from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.models.schemas import EmailMessage
from src.integrations.token_store import get_token


class GmailProvider:
    def __init__(self) -> None:
        self._access_token = self._resolve_access_token()
        running_pytest = bool(os.getenv("PYTEST_CURRENT_TEST"))
        self._use_google_api = bool(self._access_token) and not running_pytest

        now = datetime.now()
        self._emails: dict[str, EmailMessage] = {
            "m1": EmailMessage(
                id="m1",
                subject="Project sync next Monday",
                sender="teamlead@acme.dev",
                body="Please prepare demo notes before Monday 10:00 and share updates.",
                received_at=now - timedelta(hours=3),
                unread=True,
            ),
            "m2": EmailMessage(
                id="m2",
                subject="AI meetup this weekend",
                sender="events@community.org",
                body="There is an AI meetup on Saturday at 14:00 downtown.",
                received_at=now - timedelta(hours=6),
                unread=True,
            ),
            "m3": EmailMessage(
                id="m3",
                subject="Invoice reminder",
                sender="billing@tools.io",
                body="Please review and pay the invoice by Friday.",
                received_at=now - timedelta(days=1),
                unread=False,
            ),
        }

    def list_unread_messages(self, limit: int = 10) -> list[EmailMessage]:
        if self._use_google_api:
            remote = self._list_unread_messages_google(limit)
            if remote:
                return remote

        unread = [email for email in self._emails.values() if email.unread]
        return sorted(unread, key=lambda item: item.received_at, reverse=True)[:limit]

    def mark_as_read(self, message_id: str) -> bool:
        if self._use_google_api and self._mark_as_read_google(message_id):
            return True

        message = self._emails.get(message_id)
        if message is None:
            return False
        self._emails[message_id] = message.model_copy(update={"unread": False})
        return True

    def all_messages(self) -> list[EmailMessage]:
        if self._use_google_api:
            unread = self._list_unread_messages_google(limit=50)
            if unread:
                return unread
        return sorted(self._emails.values(), key=lambda item: item.received_at, reverse=True)

    def _list_unread_messages_google(self, limit: int) -> list[EmailMessage]:
        access_token = self._resolve_access_token()
        if not access_token:
            return []

        query_params = urlencode({"q": "is:unread", "maxResults": str(limit)})
        list_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages?{query_params}"
        data = self._http_json("GET", list_url, access_token)
        message_refs = data.get("messages", []) if isinstance(data, dict) else []
        messages: list[EmailMessage] = []

        for ref in message_refs:
            msg_id = ref.get("id")
            if not msg_id:
                continue
            detail = self._http_json("GET", f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}", access_token)
            if not isinstance(detail, dict):
                continue

            payload = detail.get("payload", {})
            headers = payload.get("headers", [])
            header_map = {header.get("name", "").lower(): header.get("value", "") for header in headers}
            internal_ms = int(detail.get("internalDate", "0") or "0")
            received_at = datetime.fromtimestamp(internal_ms / 1000) if internal_ms else datetime.now()
            label_ids = detail.get("labelIds", [])

            messages.append(
                EmailMessage(
                    id=msg_id,
                    subject=header_map.get("subject", "(no subject)"),
                    sender=header_map.get("from", "unknown@sender"),
                    body=detail.get("snippet", ""),
                    received_at=received_at,
                    unread="UNREAD" in label_ids,
                )
            )

        return sorted(messages, key=lambda item: item.received_at, reverse=True)

    def _mark_as_read_google(self, message_id: str) -> bool:
        access_token = self._resolve_access_token()
        if not access_token:
            return False

        payload = {"removeLabelIds": ["UNREAD"]}
        result = self._http_json(
            "POST",
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}/modify",
            access_token,
            payload,
        )
        return isinstance(result, dict)

    def _resolve_access_token(self) -> str | None:
        direct_access_token = os.getenv("GMAIL_ACCESS_TOKEN") or get_token("GMAIL_ACCESS_TOKEN")
        if direct_access_token:
            return direct_access_token

        refresh_token = os.getenv("GMAIL_REFRESH_TOKEN") or get_token("GMAIL_REFRESH_TOKEN")
        client_id = os.getenv("GMAIL_CLIENT_ID") or os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        client_secret = os.getenv("GMAIL_CLIENT_SECRET") or os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
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
                return json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError, json.JSONDecodeError):
            return {}