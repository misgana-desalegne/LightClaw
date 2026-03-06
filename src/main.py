from __future__ import annotations

import argparse
import json
import os
import webbrowser
from urllib.parse import urlencode

from dotenv import load_dotenv

from src.agent.context import Context
from src.agent.orchestrator import Orchestrator
from src.agent.registry import SkillRegistry
from src.integrations.gmail import GmailProvider
from src.integrations.google_calendar import CalendarProvider
from src.integrations.llm import build_llm_provider_from_env
from src.integrations.token_store import get_token
from src.integrations.whatsapp import WhatsAppProvider
from src.integrations.web_search import WebSearchProvider
from src.models.schemas import IntentRequest
from src.skills.calendar.skill import CalendarSkill
from src.skills.email.skill import EmailSkill
from src.skills.events.skill import EventsSkill
from src.utils.logger import get_logger


def _has_google_tokens() -> bool:
    return any(
        [
            os.getenv("GMAIL_ACCESS_TOKEN"),
            os.getenv("GMAIL_REFRESH_TOKEN"),
            os.getenv("GOOGLE_CALENDAR_ACCESS_TOKEN"),
            os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN"),
            get_token("GMAIL_ACCESS_TOKEN"),
            get_token("GMAIL_REFRESH_TOKEN"),
            get_token("GOOGLE_CALENDAR_ACCESS_TOKEN"),
            get_token("GOOGLE_CALENDAR_REFRESH_TOKEN"),
        ]
    )


def _google_auth_url() -> str:
    base_url = os.getenv("APP_BASE_URL", "http://localhost:8000")
    services = os.getenv("GOOGLE_OAUTH_SERVICES", "gmail,calendar")
    return f"{base_url.rstrip('/')}/auth/google/start?{urlencode({'services': services, 'redirect': 'true'})}"


def bootstrap_orchestrator() -> Orchestrator:
    logger = get_logger(__name__)
    context = Context()
    registry = SkillRegistry()
    llm_provider = build_llm_provider_from_env()

    calendar_provider = CalendarProvider()
    gmail_provider = GmailProvider()
    web_provider = WebSearchProvider()

    registry.register_skill(CalendarSkill(calendar_provider))
    registry.register_skill(EmailSkill(gmail_provider, llm_provider))
    registry.register_skill(EventsSkill(web_provider, llm_provider))

    return Orchestrator(skill_registry=registry, context=context, llm=llm_provider, retries=2, logger=logger)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Lightweight AI productivity agent")
    parser.add_argument("intent", help="Natural-language intent to execute")
    parser.add_argument("--skill", dest="preferred_skill", default=None, help="Optional explicit skill")
    parser.add_argument("--action", dest="action", default=None, help="Optional explicit action")
    parser.add_argument("--payload", dest="payload", default="{}", help="JSON payload for action")
    parser.add_argument("--channel", dest="channel", default="cli", choices=["cli", "whatsapp"], help="Input channel")
    parser.add_argument("--from", dest="sender", default="+10000000000", help="Sender id/phone for WhatsApp mode")
    parser.add_argument(
        "--open-auth-link",
        dest="open_auth_link",
        action="store_true",
        help="Open Google OAuth link in browser if tokens are missing",
    )
    args = parser.parse_args()

    if not _has_google_tokens():
        auth_url = _google_auth_url()
        print("[auth] Google is not connected yet.")
        print(f"[auth] Start API server: python -m uvicorn src.api.server:app --port 8000")
        print(f"[auth] Connect here: {auth_url}")
        if args.open_auth_link:
            try:
                webbrowser.open(auth_url)
            except Exception:
                pass

    payload = json.loads(args.payload)
    orchestrator = bootstrap_orchestrator()
    if args.channel == "whatsapp":
        whatsapp_provider = WhatsAppProvider()
        result = orchestrator.handle_whatsapp_command(text=args.intent, sender=args.sender, provider=whatsapp_provider)
    else:
        request = IntentRequest(
            text=args.intent,
            preferred_skill=args.preferred_skill,
            action=args.action,
            payload=payload,
        )
        result = orchestrator.handle_request(request)

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()