from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

from src.agent.registry import SkillRegistry


class SkillLoaderError(RuntimeError):
    """Raised when a skill module cannot be loaded or initialized."""


def load_skills(registry: SkillRegistry, dependencies: dict[str, Any]) -> list[str]:
    """Discover and register skills from src/skills/*/skill.py.

    Skill module contract:
    - Must expose create_skill(dependencies: dict[str, Any]) -> Skill
    """
    skills_dir = Path(__file__).resolve().parents[1] / "skills"
    disabled = {
        item.strip().lower()
        for item in os.getenv("SKILLS_DISABLED", "").split(",")
        if item.strip()
    }

    loaded: list[str] = []
    for child in sorted(skills_dir.iterdir()):
        if not child.is_dir() or child.name.startswith("__"):
            continue
        if not (child / "skill.py").exists():
            continue

        module_name = f"src.skills.{child.name}.skill"
        module = importlib.import_module(module_name)
        factory = getattr(module, "create_skill", None)
        if factory is None:
            raise SkillLoaderError(
                f"Skill module '{module_name}' is missing create_skill(dependencies)"
            )

        skill = factory(dependencies)
        enabled = child.name.lower() not in disabled
        registry.register_skill(skill, enabled=enabled)
        loaded.append(skill.name)

    return loaded
