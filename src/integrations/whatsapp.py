from __future__ import annotations

import base64
import json
import os
from datetime import datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.integrations.token_store import get_token


class WhatsAppProvider:
    def __init__(self) -> None:
        self.mode = (os.getenv("WHATSAPP_PROVIDER") or get_token("WHATSAPP_PROVIDER") or "twilio").lower()
        self._outbox: list[dict[str, Any]] = []

    def normalize_incoming(self, text: str, sender: str) -> dict[str, Any]:
        return {
            "sender": sender,
            "text": text.strip(),
            "received_at": datetime.now().isoformat(),
        }

    def send_message(self, to: str, message: str) -> dict[str, Any]:
        outbound = {
            "to": to,
            "message": message,
            "sent_at": datetime.now().isoformat(),
            "status": "queued",
        }

        if self.mode == "twilio":
            sent = self._send_twilio(to=to, message=message)
            outbound["status"] = "sent" if sent else "failed"
        elif self.mode == "meta":
            sent = self._send_meta(to=to, message=message)
            outbound["status"] = "sent" if sent else "failed"

        self._outbox.append(outbound)
        return outbound

    def list_outbox(self) -> list[dict[str, Any]]:
        return list(self._outbox)

    def _send_twilio(self, to: str, message: str) -> bool:
        sid = os.getenv("TWILIO_ACCOUNT_SID") or get_token("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN") or get_token("TWILIO_AUTH_TOKEN")
        from_number = os.getenv("TWILIO_WHATSAPP_NUMBER") or get_token("TWILIO_WHATSAPP_NUMBER")
        if not (sid and auth_token and from_number):
            return False

        payload = urlencode(
            {
                "From": from_number,
                "To": to,
                "Body": message,
            }
        ).encode("utf-8")
        auth = base64.b64encode(f"{sid}:{auth_token}".encode("utf-8")).decode("utf-8")
        request = Request(
            url=f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data=payload,
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=20):
                return True
        except Exception:  # noqa: BLE001
            return False

    def _send_meta(self, to: str, message: str) -> bool:
        phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID") or get_token("WHATSAPP_PHONE_NUMBER_ID")
        access_token = os.getenv("WHATSAPP_ACCESS_TOKEN") or get_token("WHATSAPP_ACCESS_TOKEN")
        if not (phone_id and access_token):
            return False

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": message},
        }
        request = Request(
            url=f"https://graph.facebook.com/v20.0/{phone_id}/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=20):
                return True
        except Exception:  # noqa: BLE001
            return False