from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any


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


def build_llm_provider_from_env() -> LLMProvider:
    """Build LLM provider based on environment. Defaults to Gemini if API key present."""
    api_key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "gemini-2.5-flash")
    
    if api_key:
        return GeminiLLMProvider(api_key=api_key, model=model)
    return MockLLMProvider()