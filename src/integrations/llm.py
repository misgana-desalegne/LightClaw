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
    """Minimal mock for testing. Returns basic fixtures based on prompt keywords."""
    
    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        prompt = user_prompt.lower()
        now = datetime.now().replace(second=0, microsecond=0)

        # Email action items extraction
        if "extract action items" in system_prompt.lower():
            return {"items": [{"title": "Follow up on email request", "due_at": None}]}

        # Intent classification (for tests) - detect via user_prompt containing "classify"
        if "classify" in prompt or "intent" in prompt:
            # Extract user message from formatted prompt
            user_msg = prompt.split("user message:")[-1].strip().lower() if "user message:" in prompt else prompt
            
            # Check day - see both calendar and emails
            if any(kw in user_msg for kw in ["check my day", "check day", "my day", "today's schedule", "what's on"]):
                return {"intent": "check_day", "skill": None, "action": None, "payload": {}, "confidence": 0.95, "reasoning": "Check day overview"}
            
            # Today's calendar
            if "today" in user_msg and ("calendar" in user_msg or "schedule" in user_msg or "events" in user_msg):
                return {"intent": "calendar_today", "skill": "calendar", "action": "list_today", "payload": {}, "confidence": 0.9, "reasoning": "Today's calendar"}
            
            # Today's emails
            if "today" in user_msg and "email" in user_msg:
                return {"intent": "review_email_today", "skill": "email", "action": "summarize_today", "payload": {}, "confidence": 0.9, "reasoning": "Today's emails"}
            
            if any(kw in user_msg for kw in ["add task", "schedule task", "meeting", "lunch", "dinner"]):
                start = (now + timedelta(hours=1)).isoformat()
                end = (now + timedelta(hours=2)).isoformat()
                return {
                    "intent": "calendar_create",
                    "skill": "calendar",
                    "action": "create",
                    "payload": {"title": "Event", "start_time": start, "end_time": end},
                    "confidence": 0.9,
                    "reasoning": "User wants to create calendar event",
                }
            if "email" in user_msg or "inbox" in user_msg:
                return {"intent": "review_email", "skill": "email", "action": "summarize", "payload": {}, "confidence": 0.9, "reasoning": "Email review"}
            return {"intent": "fallback", "skill": None, "action": None, "payload": {}, "confidence": 0.3, "reasoning": "Unknown"}

        return {"result": "ok"}


class GeminiLLMProvider(LLMProvider):
    """Google Gemini API provider using official SDK."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        from google import genai
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        prompt = f"{system_prompt}\n\nUser message: {user_prompt}\n\nRespond with valid JSON only."
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            content = response.text
        except Exception as e:
            return {"error": "llm_request_failed", "details": str(e)}

        # Clean up markdown code blocks if present
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"error": "llm_invalid_json", "raw": content}


class OpenAICompatibleLLMProvider(LLMProvider):
    """OpenAI-compatible chat completions endpoint provider."""

    def __init__(self, base_url: str, model: str, api_key: str, timeout: float = 20.0) -> None:
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

        content = body.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"error": "llm_invalid_json", "raw": content}


class OllamaLLMProvider(LLMProvider):
    """Local Ollama chat endpoint provider."""

    def __init__(self, base_url: str, model: str, timeout: float = 20.0) -> None:
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
    """Build LLM provider from env selection with safe fallback to mock."""
    backend = os.getenv("LLM_BACKEND", "gemini").strip().lower()
    api_key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "gemini-2.5-flash")
    base_url = os.getenv("LLM_BASE_URL", "").strip()

    if backend == "mock":
        return MockLLMProvider()

    if backend == "gemini":
        if not api_key:
            return MockLLMProvider()
        return GeminiLLMProvider(api_key=api_key, model=model)

    if backend == "ollama":
        ollama_model = model or "qwen2.5:7b-instruct"
        ollama_base_url = base_url or "http://localhost:11434"
        return OllamaLLMProvider(base_url=ollama_base_url, model=ollama_model)

    if backend == "openai":
        if not api_key:
            return MockLLMProvider()
        openai_model = model or "gpt-4.1-mini"
        openai_base_url = base_url or "https://api.openai.com/v1"
        return OpenAICompatibleLLMProvider(base_url=openai_base_url, model=openai_model, api_key=api_key)

    return MockLLMProvider()