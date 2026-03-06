from __future__ import annotations

from src.agent.context import Context
from src.integrations.llm import LLMProvider
from src.integrations.web_search import WebSearchProvider
from src.models.schemas import SkillResult


class EventsSkill:
    name = "events"

    def __init__(self, provider: WebSearchProvider, llm: LLMProvider) -> None:
        self.provider = provider
        self.llm = llm

    def can_handle(self, intent: str) -> bool:
        return "find" in intent or "event" in intent or "search" in intent

    def execute(self, action: str, payload: dict, context: Context) -> SkillResult:
        if action == "search":
            query = payload.get("query", "events")
            suggestions = self.provider.search_events(query)
            serialized = [event.model_dump(mode="json") for event in suggestions]
            context.set("last_event_suggestions", serialized)
            return SkillResult(
                success=True,
                skill=self.name,
                action=action,
                message=f"Found {len(serialized)} event suggestion(s)",
                data={"events": serialized},
            )

        if action == "best_option":
            suggestions = context.get("last_event_suggestions", [])
            if not suggestions:
                return SkillResult(
                    success=False,
                    skill=self.name,
                    action=action,
                    message="No event suggestions available. Run search first.",
                )
            llm_ranking = self.llm.generate_json(
                system_prompt=(
                    "Rank events for user relevance. Return JSON: {\"best_index\": number}. "
                    "Pick the strongest match for query and timing."
                ),
                user_prompt=f"query={payload.get('query', 'events')}\nevents={suggestions}",
            )
            best_index = llm_ranking.get("best_index", 0) if isinstance(llm_ranking, dict) else 0
            if not isinstance(best_index, int) or best_index < 0 or best_index >= len(suggestions):
                best_index = 0
            best = suggestions[best_index]
            return SkillResult(
                success=True,
                skill=self.name,
                action=action,
                message="Selected best event option",
                data={"event": best, "best_index": best_index},
            )

        return SkillResult(success=False, skill=self.name, action=action, message="Unsupported action")