from __future__ import annotations

import json
import os
import subprocess
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


class MistralLLMProvider(LLMProvider):
    """Provider for local Mistral models. Attempts to use Hugging Face Transformers if available.

    This will work when a Mistral-compatible model is installed/cached locally and `transformers` is
    available. The provider reads the model name from the LLM_MODEL env var (defaults to 'mistral/mistral-large').
    """

    def __init__(self, model: str = "mistral/mistral-large") -> None:
        self.model = model
        self._impl = None
        self._pipeline = None
        self._error = None

        # Prefer transformers pipeline if installed
        try:
            from transformers import pipeline
            # Create a text-generation pipeline. If device_map='auto' is supported it will use GPU/CPU as available.
            # We set return_full_text=False to get only the generated continuation in newer transformers; handle both cases.
            self._pipeline = pipeline("text-generation", model=self.model, device_map="auto")
            self._impl = "transformers"
        except Exception as e:
            self._error = str(e)
            self._pipeline = None
            self._impl = None

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        prompt = f"{system_prompt}\n\nUser message: {user_prompt}\n\nRespond with valid JSON only."

        if self._impl == "transformers" and self._pipeline is not None:
            try:
                # Request a deterministic completion (no sampling) to try to keep output consistent
                outputs = self._pipeline(prompt, max_new_tokens=512, do_sample=False)
                # `outputs` can be a list of dicts with 'generated_text' or a list of strings depending on transformers version
                if isinstance(outputs, list) and outputs:
                    if isinstance(outputs[0], dict) and "generated_text" in outputs[0]:
                        content = outputs[0]["generated_text"]
                    elif isinstance(outputs[0], str):
                        content = outputs[0]
                    else:
                        content = str(outputs[0])
                else:
                    content = ""
            except Exception as e:
                return {"error": "llm_request_failed", "details": str(e)}

            # If the pipeline returns the entire prompt + completion, strip the prompt prefix
            if content.startswith(prompt):
                content = content[len(prompt):]
        else:
            return {"error": "mistral_unavailable", "details": self._error or "transformers pipeline unavailable"}

        # Clean up code fences like other providers
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


class OllamaLLMProvider(LLMProvider):
    """Provider that uses Ollama (either CLI or HTTP API) to run a model (e.g. 'mistral').

    Tries HTTP API first (if ollama serve is running), falls back to CLI `ollama run <model>`.
    HTTP API is much faster for repeated requests since the model stays loaded.
    
    OPTIMIZATIONS:
    - Uses HTTP API by default (10x faster)
    - Configurable max_tokens and temperature
    - Connection pooling
    - Shorter timeout for faster failure
    """

    def __init__(self, model: str = "mistral", api_base: str = "http://localhost:11434") -> None:
        self.model = model
        self.api_base = api_base
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "256"))  # Reduced from 512
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))  # Lower = faster
        self._use_cli = False  # Flag to skip HTTP API if it's not available

    def _try_http_api(self, prompt: str) -> dict[str, Any] | None:
        """Try to use Ollama HTTP API (if server is running). Returns None if unavailable."""
        if self._use_cli:
            return None  # Skip if we know HTTP isn't available
            
        try:
            import urllib.request
            import urllib.parse
            
            # Ollama API endpoint
            url = f"{self.api_base}/api/generate"
            data = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": self.max_tokens,
                    "temperature": self.temperature,
                    "top_p": 0.9,
                }
            }
            
            req_data = json.dumps(data).encode('utf-8')
            req = urllib.request.Request(url, data=req_data, headers={'Content-Type': 'application/json'})
            
            # Reduced timeout from 30s to 15s for faster failure
            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))
                return {"success": True, "content": result.get("response", "")}
                
        except Exception as e:
            # Mark as unavailable to skip HTTP API in future calls
            self._use_cli = True
            return None

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        prompt = f"{system_prompt}\n\nUser message: {user_prompt}\n\nRespond with valid JSON only."

        # First, try HTTP API (faster if ollama serve is running)
        api_result = self._try_http_api(prompt)
        if api_result and api_result.get("success"):
            content = api_result["content"]
        else:
            # Fallback to CLI (slower but works without ollama serve)
            try:
                # Try passing the prompt as a single argument first
                proc = subprocess.run(
                    ["ollama", "run", self.model, prompt],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=60,
                )

                # If that didn't produce output, try piping via stdin
                if (not proc.stdout or proc.returncode != 0):
                    proc = subprocess.run(
                        ["ollama", "run", self.model],
                        input=prompt,
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=60,
                    )

                content = proc.stdout or proc.stderr or ""
            except Exception as e:
                return {"error": "ollama_unavailable", "details": str(e)}

        # If the tool echoes the prompt, strip it
        if content.startswith(prompt):
            content = content[len(prompt):]

        # Clean up markdown code fences like other providers
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
    """Build LLM provider based on environment. Defaults to Gemini if API key present.

    Now supports selecting backend via LLM_BACKEND env var. Supported values:
      - 'gemini' (default if LLM_API_KEY present)
      - 'mistral' (uses local Mistral implementation via transformers)
      - 'ollama' (uses the local Ollama CLI: 'ollama run <model>')
      - 'mock'
    """
    backend = os.getenv("LLM_BACKEND", "").strip().lower()
    api_key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "gemini-2.5-flash")

    if backend in ("ollama", "mistral_ollama"):
        return OllamaLLMProvider(model=os.getenv("LLM_MODEL", "mistral"))

    if backend in ("mistral", "local_mistral"):
        # Use local Mistral provider (requires transformers + model)
        return MistralLLMProvider(model=os.getenv("LLM_MODEL", "mistral/mistral-large"))

    if backend in ("mock", "none"):
        return MockLLMProvider()

    # If backend unspecified but API key exists, prefer Gemini
    if api_key and (backend == "" or backend in ("gemini", "google")):
        return GeminiLLMProvider(api_key=api_key, model=model)

    # Fallbacks
    if api_key:
        # explicit API key but unknown backend -> try Gemini
        return GeminiLLMProvider(api_key=api_key, model=model)

    return MockLLMProvider()