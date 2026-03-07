from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src.agent.context import Context
from src.models.schemas import SkillResult


class Skill(Protocol):
    name: str

    def can_handle(self, intent: str) -> bool:
        ...

    def execute(self, action: str, payload: dict, context: Context) -> SkillResult:
        ...


@dataclass(frozen=True)
class SkillManifest:
    name: str
    version: str
    description: str
    actions: list[str]
    required_env: list[str]


@dataclass
class RegisteredSkill:
    name: str
    instance: Skill
    manifest: SkillManifest
    enabled: bool = True


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, RegisteredSkill] = {}

    def register_skill(self, skill: Skill, enabled: bool = True) -> None:
        if skill.name in self._skills:
            raise ValueError(f"Skill '{skill.name}' is already registered")
        manifest = self._build_manifest(skill)
        self._skills[skill.name] = RegisteredSkill(
            name=skill.name,
            instance=skill,
            manifest=manifest,
            enabled=enabled,
        )

    def unregister_skill(self, skill_name: str) -> None:
        self._skills.pop(skill_name, None)

    def get_skill(self, skill_name: str, include_disabled: bool = False) -> Skill | None:
        registered = self._skills.get(skill_name)
        if registered is None:
            return None
        if not include_disabled and not registered.enabled:
            return None
        return registered.instance

    def list_skills(self) -> list[str]:
        return sorted(name for name, registered in self._skills.items() if registered.enabled)

    def list_registered_skills(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for name in sorted(self._skills.keys()):
            item = self._skills[name]
            rows.append(
                {
                    "name": item.name,
                    "enabled": item.enabled,
                    "version": item.manifest.version,
                    "description": item.manifest.description,
                    "actions": list(item.manifest.actions),
                    "required_env": list(item.manifest.required_env),
                }
            )
        return rows

    def enable_skill(self, skill_name: str) -> bool:
        registered = self._skills.get(skill_name)
        if registered is None:
            return False
        registered.enabled = True
        return True

    def disable_skill(self, skill_name: str) -> bool:
        registered = self._skills.get(skill_name)
        if registered is None:
            return False
        registered.enabled = False
        return True

    def is_skill_registered(self, skill_name: str) -> bool:
        return skill_name in self._skills

    def resolve_by_intent(self, intent: str) -> Skill | None:
        lowered_intent = intent.lower()
        for registered in self._skills.values():
            if not registered.enabled:
                continue
            if registered.instance.can_handle(lowered_intent):
                return registered.instance
        return None

    @staticmethod
    def _build_manifest(skill: Skill) -> SkillManifest:
        raw_actions = getattr(skill, "actions", [])
        raw_required_env = getattr(skill, "required_env", [])
        description = str(getattr(skill, "description", ""))
        version = str(getattr(skill, "version", "0.1.0"))

        actions = [str(item) for item in raw_actions] if isinstance(raw_actions, list) else []
        required_env = [str(item) for item in raw_required_env] if isinstance(raw_required_env, list) else []

        return SkillManifest(
            name=skill.name,
            version=version,
            description=description,
            actions=actions,
            required_env=required_env,
        )