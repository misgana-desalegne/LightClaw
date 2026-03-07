from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any
from urllib.request import Request, urlopen

from src.integrations.token_store import get_token


class TelegramProvider:
    def __init__(self) -> None:
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or get_token("TELEGRAM_BOT_TOKEN")
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

        if self.bot_token and self._send_telegram(chat_id=to, text=message):
            outbound["status"] = "sent"
        elif self.bot_token:
            outbound["status"] = "failed"

        self._outbox.append(outbound)
        return outbound

    def list_outbox(self) -> list[dict[str, Any]]:
        return list(self._outbox)

    def _send_telegram(self, chat_id: str, text: str) -> bool:
        payload = {
            "chat_id": chat_id,
            "text": text,
        }
        request = Request(
            url=f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=20):
                return True
        except Exception:  # noqa: BLE001
            return False
