from __future__ import annotations

from src.agent.loader import load_skills
from src.agent.registry import SkillRegistry
from src.integrations.gmail import GmailProvider
from src.integrations.google_calendar import CalendarProvider
from src.integrations.llm import MockLLMProvider


def test_registry_enable_disable_roundtrip() -> None:
    registry = SkillRegistry()
    llm = MockLLMProvider()

    load_skills(
        registry=registry,
        dependencies={
            "llm_provider": llm,
            "calendar_provider": CalendarProvider(),
            "gmail_provider": GmailProvider(test_emails=[]),
        },
    )

    assert "calendar" in registry.list_skills()
    assert "email" in registry.list_skills()

    changed = registry.disable_skill("email")
    assert changed is True
    assert "email" not in registry.list_skills()

    changed = registry.enable_skill("email")
    assert changed is True
    assert "email" in registry.list_skills()


def test_registry_exposes_manifest_metadata() -> None:
    registry = SkillRegistry()

    load_skills(
        registry=registry,
        dependencies={
            "llm_provider": MockLLMProvider(),
            "calendar_provider": CalendarProvider(),
            "gmail_provider": GmailProvider(test_emails=[]),
        },
    )

    rows = registry.list_registered_skills()
    names = {row["name"] for row in rows}
    assert "calendar" in names
    assert "email" in names

    for row in rows:
        assert isinstance(row["actions"], list)
        assert isinstance(row["required_env"], list)
        assert row["version"]
