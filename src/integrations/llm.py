from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


class LLMProvider(ABC):
    @abstractmethod
    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        raise NotImplementedError


class MockLLMProvider(LLMProvider):
    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        prompt = user_prompt.lower()
        now = datetime.now().replace(second=0, microsecond=0)

        if "extract action items" in system_prompt.lower():
            due = None
            if "monday" in prompt:
                due = (now + timedelta(days=(0 - now.weekday()) % 7)).replace(hour=10, minute=0).isoformat()
            elif "friday" in prompt:
                due = (now + timedelta(days=(4 - now.weekday()) % 7)).replace(hour=10, minute=0).isoformat()
            return {
                "items": [
                    {
                        "title": "Follow up on email request",
                        "due_at": due,
                    }
                ]
            }

        if "rank events" in system_prompt.lower():
            return {"best_index": 0}

        if "parse whatsapp command" in system_prompt.lower():
            if "add task" in prompt:
                title = user_prompt.split("add task", 1)[1].strip() if "add task" in prompt else "New task"
                start = (now + timedelta(hours=1)).isoformat()
                end = (now + timedelta(hours=1, minutes=30)).isoformat()
                return {
                    "intent": "calendar_create",
                    "payload": {
                        "title": f"Task: {title or 'New task'}",
                        "start_time": start,
                        "end_time": end,
                    },
                }
            if "add event" in prompt or "schedule" in prompt:
                start = (now + timedelta(hours=2)).isoformat()
                end = (now + timedelta(hours=3)).isoformat()
                return {
                    "intent": "calendar_create",
                    "payload": {
                        "title": "New event",
                        "start_time": start,
                        "end_time": end,
                    },
                }
            return {"intent": "fallback", "payload": {}}

        return {"result": "ok"}


class OpenAICompatibleLLMProvider(LLMProvider):
    def __init__(self, base_url: str, model: str, api_key: str, timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
        }
        request = Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError, json.JSONDecodeError):
            return {"error": "llm_request_failed"}

        content = (
            body.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "{}")
        )
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"error": "llm_invalid_json", "raw": content}


class OllamaLLMProvider(LLMProvider):
    def __init__(self, base_url: str, model: str, timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "format": "json",
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        request = Request(
            url=f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError, json.JSONDecodeError):
            return {"error": "llm_request_failed"}

        content = body.get("message", {}).get("content", "{}")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"error": "llm_invalid_json", "raw": content}


def build_llm_provider_from_env() -> LLMProvider:
    backend = os.getenv("LLM_BACKEND", "mock").lower()
    model = os.getenv("LLM_MODEL", "qwen2.5:7b-instruct")
    base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434")
    api_key = os.getenv("LLM_API_KEY", "")

    if backend == "openai":
        openai_url = base_url or "https://api.openai.com/v1"
        if not api_key:
            return MockLLMProvider()
        return OpenAICompatibleLLMProvider(base_url=openai_url, model=model, api_key=api_key)

    if backend == "ollama":
        return OllamaLLMProvider(base_url=base_url, model=model)

    return MockLLMProvider()