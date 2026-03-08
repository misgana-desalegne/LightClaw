from __future__ import annotations

from src.integrations.llm import (
    MockLLMProvider,
    OllamaLLMProvider,
    OpenAICompatibleLLMProvider,
    build_llm_provider_from_env,
)


def test_build_llm_provider_ollama_selected(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "ollama")
    monkeypatch.setenv("LLM_MODEL", "mistral:7b-instruct")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434")

    provider = build_llm_provider_from_env()

    assert isinstance(provider, OllamaLLMProvider)


def test_build_llm_provider_openai_without_key_falls_back_to_mock(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4.1-mini")
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    provider = build_llm_provider_from_env()

    assert isinstance(provider, MockLLMProvider)


def test_build_llm_provider_openai_with_key_selected(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")

    provider = build_llm_provider_from_env()

    assert isinstance(provider, OpenAICompatibleLLMProvider)
