from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.agent.context import Context
from src.models.schemas import SkillResult


class Skill(Protocol):
    name: str

    def can_handle(self, intent: str) -> bool:
        ...

    def execute(self, action: str, payload: dict, context: Context) -> SkillResult:
        ...


@dataclass
class RegisteredSkill:
    name: str
    instance: Skill


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, RegisteredSkill] = {}

    def register_skill(self, skill: Skill) -> None:
        if skill.name in self._skills:
            raise ValueError(f"Skill '{skill.name}' is already registered")
        self._skills[skill.name] = RegisteredSkill(name=skill.name, instance=skill)

    def unregister_skill(self, skill_name: str) -> None:
        self._skills.pop(skill_name, None)

    def get_skill(self, skill_name: str) -> Skill | None:
        registered = self._skills.get(skill_name)
        return registered.instance if registered else None

    def list_skills(self) -> list[str]:
        return sorted(self._skills.keys())

    def resolve_by_intent(self, intent: str) -> Skill | None:
        lowered_intent = intent.lower()
        for registered in self._skills.values():
            if registered.instance.can_handle(lowered_intent):
                return registered.instance
        return None