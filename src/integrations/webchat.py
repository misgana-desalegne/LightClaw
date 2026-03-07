from __future__ import annotations

from datetime import datetime
from typing import Any


class WebChatProvider:
    def __init__(self) -> None:
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
            "status": "delivered",
        }
        self._outbox.append(outbound)
        return outbound

    def list_outbox(self) -> list[dict[str, Any]]:
        return list(self._outbox)
