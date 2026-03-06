from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from src.models.schemas import EventSuggestion


class WebSearchProvider:
    def search_events(self, query: str) -> list[EventSuggestion]:
        google_results = self._search_google_cse(query)
        if google_results:
            return google_results

        now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        query_lower = query.lower()

        events: list[EventSuggestion] = [
            EventSuggestion(
                title="AI Builders Meetup",
                start_time=now + timedelta(days=1, hours=5),
                end_time=now + timedelta(days=1, hours=8),
                location="Downtown Hub",
                source_url="https://example.org/ai-builders",
            ),
            EventSuggestion(
                title="Weekend GenAI Workshop",
                start_time=now + timedelta(days=2, hours=3),
                end_time=now + timedelta(days=2, hours=6),
                location="Tech Campus",
                source_url="https://example.org/genai-weekend",
            ),
            EventSuggestion(
                title="Cloud & AI Networking",
                start_time=now + timedelta(days=5, hours=2),
                end_time=now + timedelta(days=5, hours=4),
                location="Innovation Center",
                source_url="https://example.org/cloud-ai-networking",
            ),
        ]

        if "weekend" in query_lower:
            return events[:2]
        if "ai" in query_lower:
            return events
        return events[:1]

    def _search_google_cse(self, query: str) -> list[EventSuggestion]:
        api_key = os.getenv("WEB_SEARCH_API_KEY")
        engine_id = os.getenv("WEB_SEARCH_ENGINE_ID")
        if not (api_key and engine_id):
            return []

        params = urlencode(
            {
                "key": api_key,
                "cx": engine_id,
                "q": f"{query} events",
                "num": "5",
            }
        )
        endpoint = f"https://www.googleapis.com/customsearch/v1?{params}"

        try:
            with urlopen(endpoint, timeout=20) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError, json.JSONDecodeError):
            return []

        items = body.get("items", []) if isinstance(body, dict) else []
        if not items:
            return []

        base_start = datetime.now().replace(hour=18, minute=0, second=0, microsecond=0)
        suggestions: list[EventSuggestion] = []
        for index, item in enumerate(items[:3]):
            title = item.get("title", f"Event option {index + 1}")
            link = item.get("link")
            start = base_start + timedelta(days=index + 1)
            end = start + timedelta(hours=2)
            suggestions.append(
                EventSuggestion(
                    title=title,
                    start_time=start,
                    end_time=end,
                    location="TBD",
                    source_url=link,
                )
            )

        return suggestions