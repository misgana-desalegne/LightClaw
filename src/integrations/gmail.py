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
    def __init__(self, test_emails: list[EmailMessage] | None = None) -> None:
        self._access_token = self._resolve_access_token()
        running_pytest = bool(os.getenv("PYTEST_CURRENT_TEST"))
        self._use_google_api = bool(self._access_token) and not running_pytest
        self._emails: dict[str, EmailMessage] = {e.id: e for e in test_emails} if test_emails else {}

    def list_unread_messages(self, limit: int = 10) -> list[EmailMessage]:
        if self._use_google_api:
            remote = self._list_messages_google(query="is:unread", limit=limit)
            if remote:
                return remote

        unread = [email for email in self._emails.values() if email.unread]
        return sorted(unread, key=lambda item: item.received_at, reverse=True)[:limit]

    def list_recent_messages(self, limit: int = 10) -> list[EmailMessage]:
        """Get the most recent emails regardless of read status."""
        if self._use_google_api:
            remote = self._list_messages_google(query="", limit=limit)
            if remote:
                return remote
        return sorted(self._emails.values(), key=lambda item: item.received_at, reverse=True)[:limit]

    def list_today_messages(self) -> list[EmailMessage]:
        """Get emails received today."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if self._use_google_api:
            date_str = today.strftime("%Y/%m/%d")
            remote = self._list_messages_google(query=f"after:{date_str}", limit=50)
            if remote:
                return remote
        return sorted(
            [e for e in self._emails.values() if e.received_at >= today],
            key=lambda item: item.received_at,
            reverse=True,
        )

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
            remote = self._list_messages_google(query="", limit=50)
            if remote:
                return remote
        return sorted(self._emails.values(), key=lambda item: item.received_at, reverse=True)

    def _list_messages_google(self, query: str, limit: int) -> list[EmailMessage]:
        access_token = self._resolve_access_token()
        if not access_token:
            return []

        params = {"maxResults": str(limit)}
        if query:
            params["q"] = query
        query_params = urlencode(params)
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
        refresh_token = os.getenv("GMAIL_REFRESH_TOKEN") or get_token("GMAIL_REFRESH_TOKEN")
        if refresh_token:
            client_pairs = [
                (os.getenv("GOOGLE_OAUTH_CLIENT_ID"), os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")),
                (os.getenv("GMAIL_CLIENT_ID"), os.getenv("GMAIL_CLIENT_SECRET")),
                (os.getenv("GOOGLE_CALENDAR_CLIENT_ID"), os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET")),
            ]
            for client_id, client_secret in client_pairs:
                if not (client_id and client_secret):
                    continue
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
                    refreshed_access_token = token_response.get("access_token")
                    if refreshed_access_token:
                        return refreshed_access_token
                except (URLError, TimeoutError, json.JSONDecodeError):
                    continue

        # Fallback to direct token if refresh is unavailable or fails.
        return os.getenv("GMAIL_ACCESS_TOKEN") or get_token("GMAIL_ACCESS_TOKEN")

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