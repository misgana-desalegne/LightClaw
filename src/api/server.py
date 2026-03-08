from __future__ import annotations

import json
import os
import secrets
import time
from html import escape
from dataclasses import dataclass
from typing import Annotated, Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from collections import deque
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Header, HTTPException, Query, Request as FastAPIRequest
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel

from src.main import bootstrap_orchestrator
from src.integrations.telegram import TelegramProvider
from src.integrations.token_store import get_token, upsert_tokens
from src.integrations.webchat import WebChatProvider
from src.integrations.whatsapp import WhatsAppProvider

load_dotenv()

app = FastAPI(title="Lightweight AI Agent API", version="0.1.0")
orchestrator = bootstrap_orchestrator()
whatsapp_provider = WhatsAppProvider()
telegram_provider = TelegramProvider()
webchat_provider = WebChatProvider()

_MESSAGE_LOG: deque[dict[str, Any]] = deque(maxlen=100)


def _add_message(channel: str, sender: str, role: str, text: str) -> None:
    _MESSAGE_LOG.append({
        "id": len(_MESSAGE_LOG),
        "channel": channel,
        "sender": sender,
        "role": role,
        "text": text,
        "timestamp": datetime.now().isoformat(),
    })


class WebChatMessageIn(BaseModel):
    session_id: str
    message: str


@dataclass
class OAuthState:
    services: list[str]
    created_at: float


_OAUTH_STATE: dict[str, OAuthState] = {}
_STATE_TTL_SECONDS = 900


def _cleanup_expired_state() -> None:
    now = time.time()
    expired = [key for key, value in _OAUTH_STATE.items() if now - value.created_at > _STATE_TTL_SECONDS]
    for key in expired:
        _OAUTH_STATE.pop(key, None)


def _oauth_client_id() -> str:
    return (
        os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        or os.getenv("GOOGLE_CALENDAR_CLIENT_ID")
        or os.getenv("GMAIL_CLIENT_ID")
        or ""
    )


def _oauth_client_secret() -> str:
    return (
        os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
        or os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET")
        or os.getenv("GMAIL_CLIENT_SECRET")
        or ""
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "name": "Lightweight AI Agent API",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "admin": "/admin",
            "admin_skills": "/admin/skills",
            "admin_llm_config": "/admin/llm/config",
            "webchat_ui": "/chat",
            "webchat_message": "/webchat/message",
            "google_auth_start": "/auth/google/start?services=gmail,calendar&redirect=true",
            "google_auth_callback": "/auth/google/callback",
            "telegram_webhook": "/webhooks/telegram",
        },
    }


def _connected(service: str) -> bool:
    if service == "gmail":
        return bool(
            os.getenv("GMAIL_ACCESS_TOKEN")
            or os.getenv("GMAIL_REFRESH_TOKEN")
            or get_token("GMAIL_ACCESS_TOKEN")
            or get_token("GMAIL_REFRESH_TOKEN")
        )
    if service == "calendar":
        return bool(
            os.getenv("GOOGLE_CALENDAR_ACCESS_TOKEN")
            or os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN")
            or get_token("GOOGLE_CALENDAR_ACCESS_TOKEN")
            or get_token("GOOGLE_CALENDAR_REFRESH_TOKEN")
        )
    if service == "telegram":
        return bool(
            os.getenv("TELEGRAM_BOT_TOKEN")
            or get_token("TELEGRAM_BOT_TOKEN")
        )
    return False


@app.get("/admin", response_class=HTMLResponse)
def admin_page(message: str | None = Query(default=None)) -> HTMLResponse:
    google_connected = _connected("gmail") and _connected("calendar")
    telegram_connected = _connected("telegram")
    llm_backend = (os.getenv("LLM_BACKEND") or get_token("LLM_BACKEND") or "gemini").strip().lower()
    llm_model = (os.getenv("LLM_MODEL") or get_token("LLM_MODEL") or "gemini-2.5-flash").strip()
    llm_base_url = (os.getenv("LLM_BASE_URL") or get_token("LLM_BASE_URL") or "").strip()

    not_configured = "Not configured"
    status_google = "Connected" if google_connected else "Not connected"
    status_telegram = "Configured" if telegram_connected else not_configured
    google_action_html = (
        """
        <div class='action-row'>
            <button class='button connected' type='button' disabled>Google Connected</button>
            <a class='button secondary' href='/auth/google/start?services=gmail,calendar&redirect=true'>Reconnect Google</a>
        </div>
        """
        if google_connected
        else "<a class='button' href='/auth/google/start?services=gmail,calendar&redirect=true'>Connect Google</a>"
    )
    telegram_action_html = (
        """
                <div class='action-row'>
                    <button class='button connected' type='button' disabled>Telegram Connected</button>
                    <span class='muted'>Use the form below to reconnect or rotate token.</span>
                </div>
                <form method='post' action='/auth/telegram/config'>
                    <div class='row'><label>Bot Token</label><input name='bot_token' /></div>
                    <div class='row'><label>Webhook Secret (optional)</label><input name='webhook_secret' /></div>
                    <button type='submit'>Reconnect Telegram</button>
                </form>
        """
        if telegram_connected
        else """
                <form method='post' action='/auth/telegram/config'>
                    <div class='row'><label>Bot Token</label><input name='bot_token' /></div>
                    <div class='row'><label>Webhook Secret (optional)</label><input name='webhook_secret' /></div>
                    <button type='submit'>Save Telegram Credentials</button>
                </form>
        """
    )
    message_html = (
        f"<div class='notice success'>{escape(message)}</div>" if message else ""
    )

    html = f"""
<!DOCTYPE html>
<html lang='en'>
<head>
    <meta charset='UTF-8' />
    <meta name='viewport' content='width=device-width, initial-scale=1.0' />
    <title>Agent Admin</title>
    <style>
        :root {{
            --bg: #f6f8fb;
            --card: #ffffff;
            --text: #1f2937;
            --muted: #6b7280;
            --primary: #2563eb;
            --border: #e5e7eb;
            --ok: #16a34a;
        }}
        * {{ box-sizing: border-box; font-family: Segoe UI, Inter, Arial, sans-serif; }}
        body {{ margin: 0; background: var(--bg); color: var(--text); }}
        .container {{ max-width: 920px; margin: 40px auto; padding: 0 16px; }}
        .title {{ font-size: 28px; margin: 0 0 8px; }}
        .subtitle {{ color: var(--muted); margin: 0 0 24px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }}
        .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 18px; }}
        .card h3 {{ margin: 0 0 8px; font-size: 18px; }}
        .status {{ font-size: 13px; margin-bottom: 14px; color: var(--muted); }}
        .status .ok {{ color: var(--ok); font-weight: 600; }}
        .row {{ display: grid; gap: 8px; margin-bottom: 10px; }}
        label {{ font-size: 12px; color: var(--muted); }}
        input, select {{ width: 100%; border: 1px solid var(--border); border-radius: 10px; padding: 10px; font-size: 14px; }}
        button, a.button {{
            display: inline-block;
            border: none;
            background: var(--primary);
            color: #fff;
            text-decoration: none;
            border-radius: 10px;
            padding: 10px 14px;
            font-size: 14px;
            cursor: pointer;
        }}
        .button.connected {{
            background: var(--ok);
            cursor: not-allowed;
            opacity: 0.95;
        }}
        .button.secondary {{
            background: #374151;
        }}
        .action-row {{
            display: flex;
            gap: 8px;
            align-items: center;
            flex-wrap: wrap;
            margin-bottom: 10px;
        }}
        .muted {{ color: var(--muted); font-size: 12px; margin-top: 6px; }}
        .notice {{ margin: 0 0 18px; padding: 10px 12px; border-radius: 10px; font-size: 14px; }}
        .notice.success {{ background: #ecfdf3; color: #166534; border: 1px solid #86efac; }}
        .required {{
            display: inline-block;
            margin-left: 8px;
            padding: 2px 8px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 600;
            color: #1d4ed8;
            background: #dbeafe;
            border: 1px solid #93c5fd;
        }}
        .chat-wrap {{
            border: 1px solid var(--border);
            border-radius: 10px;
            background: #f9fafb;
            padding: 10px;
        }}
        .chat-log {{
            height: 230px;
            overflow-y: auto;
            background: #fff;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 8px;
            margin-bottom: 10px;
            font-size: 13px;
        }}
        .chat-item {{ margin-bottom: 8px; }}
        .chat-user {{ color: #111827; }}
        .chat-agent {{ color: #1d4ed8; }}
        .skill-list {{ display: grid; gap: 10px; }}
        .skill-item {{
            display: flex;
            justify-content: space-between;
            gap: 10px;
            align-items: center;
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 10px;
            background: #fafafa;
        }}
        .skill-name {{ font-weight: 600; }}
        .skill-meta {{ font-size: 12px; color: var(--muted); }}
        .skill-toggle {{ background: #111827; }}
        .skill-toggle.enable {{ background: #166534; }}
        .skill-toggle.disable {{ background: #b91c1c; }}
    </style>
</head>
<body>
    <div class='container'>
        <h1 class='title'>Admin Authentication</h1>
        <p class='subtitle'>Google and Webchat are required. WhatsApp and Telegram are optional channels.</p>
        {message_html}
        <div class='grid'>
            <div class='card'>
                <h3>Google (Gmail + Calendar)<span class='required'>Mandatory</span></h3>
                <div class='status'>Status: <span class='{"ok" if google_connected else ""}'>{status_google}</span></div>
                {google_action_html}
                <div class='muted'>Uses OAuth consent and stores tokens automatically.</div>
            </div>

            <div class='card'>
                <h3>Webchat<span class='required'>Mandatory</span></h3>
                <div class='status'>Status: <span class='ok'>Ready</span></div>
                <div class='chat-wrap'>
                    <div id='admin-chat-log' class='chat-log'></div>
                    <div class='row'>
                        <label>Type and press Enter</label>
                        <input id='admin-chat-input' placeholder='add task prepare sprint demo' autocomplete='off' />
                    </div>
                </div>
                <div class='muted'>No external auth required. Messages are sent directly from this page.</div>
            </div>


            <div class='card'>
                <h3>Telegram Bot</h3>
                <div class='status'>Status: <span class='{"ok" if telegram_connected else ""}'>{status_telegram}</span></div>
                {telegram_action_html}
                <div class='muted'>Webhook URL: /webhooks/telegram</div>
            </div>

            <div class='card'>
                <h3>LLM Model</h3>
                <div class='status'>Choose cloud or local model backend for intent parsing and summaries.</div>
                <form method='post' action='/admin/llm/config'>
                    <div class='row'>
                        <label>Backend</label>
                        <select name='backend'>
                            <option value='gemini' {"selected" if llm_backend == "gemini" else ""}>Gemini (cloud)</option>
                            <option value='ollama' {"selected" if llm_backend == "ollama" else ""}>Ollama (local)</option>
                            <option value='openai' {"selected" if llm_backend == "openai" else ""}>OpenAI-compatible</option>
                            <option value='mock' {"selected" if llm_backend == "mock" else ""}>Mock (offline test)</option>
                        </select>
                    </div>
                    <div class='row'><label>Model</label><input name='model' value='{escape(llm_model)}' placeholder='e.g. mistral:7b-instruct or gemini-2.5-flash' /></div>
                    <div class='row'><label>Base URL (for Ollama/OpenAI-compatible)</label><input name='base_url' value='{escape(llm_base_url)}' placeholder='http://localhost:11434 or https://api.openai.com/v1' /></div>
                    <div class='row'><label>API Key (required for Gemini/OpenAI-compatible)</label><input name='api_key' type='password' autocomplete='off' /></div>
                    <button type='submit'>Save LLM Settings</button>
                </form>
                <div class='muted'>Tip: for local Mistral via Ollama use backend=ollama, model=mistral:7b-instruct.</div>
            </div>

            <div class='card'>
                <h3>Skills</h3>
                <div class='status'>Enable or disable registered skills without restarting.</div>
                <div id='skills-list' class='skill-list'></div>
            </div>
        </div>
    </div>
    <script>
        const sessionId = 'admin-webchat-user';
        const log = document.getElementById('admin-chat-log');
        const input = document.getElementById('admin-chat-input');

        function addLine(text, cls) {{
            const item = document.createElement('div');
            item.className = 'chat-item ' + cls;
            item.textContent = text;
            log.appendChild(item);
            log.scrollTop = log.scrollHeight;
        }}

        async function sendMessage(message) {{
            addLine('You: ' + message, 'chat-user');
            try {{
                const response = await fetch('/webchat/message', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ session_id: sessionId, message }})
                }});
                const data = await response.json();
                addLine('Agent: ' + (data.reply || data.message || 'OK'), 'chat-agent');
            }} catch (error) {{
                addLine('Agent: Failed to send message.', 'chat-agent');
            }}
        }}

        input.addEventListener('keydown', function(event) {{
            if (event.key !== 'Enter') return;
            event.preventDefault();
            const message = input.value.trim();
            if (!message) return;
            input.value = '';
            sendMessage(message);
        }});

        let lastMsgId = -1;
        async function pollMessages() {{
            try {{
                // Poll Telegram for new messages first
                await fetch('/telegram/poll', {{ method: 'POST' }});
                
                // Then fetch all new messages from the log
                const response = await fetch('/messages?since=' + (lastMsgId + 1));
                const messages = await response.json();
                messages.forEach(msg => {{
                    if (msg.id > lastMsgId) {{
                        const label = msg.role === 'user' ? '[' + msg.channel + '] ' + msg.sender + ': ' : 'Agent: ';
                        const cls = msg.role === 'user' ? 'chat-user' : 'chat-agent';
                        addLine(label + msg.text, cls);
                        lastMsgId = msg.id;
                    }}
                }});
            }} catch (e) {{}}
        }}

        function renderSkills(skills) {{
            const box = document.getElementById('skills-list');
            box.innerHTML = '';
            if (!skills.length) {{
                box.innerHTML = '<div class="skill-meta">No skills registered.</div>';
                return;
            }}
            for (const skill of skills) {{
                const item = document.createElement('div');
                item.className = 'skill-item';

                const info = document.createElement('div');
                const envHint = skill.required_env.length ? ('Requires: ' + skill.required_env.join(', ')) : 'No required env vars';
                info.innerHTML = '<div class="skill-name">' + skill.name + (skill.enabled ? ' (enabled)' : ' (disabled)') + '</div>' +
                                 '<div class="skill-meta">v' + skill.version + ' • ' + (skill.description || 'No description') + '</div>' +
                                 '<div class="skill-meta">Actions: ' + (skill.actions.join(', ') || 'n/a') + '</div>' +
                                 '<div class="skill-meta">' + envHint + '</div>';

                const action = document.createElement('button');
                action.className = 'button skill-toggle ' + (skill.enabled ? 'disable' : 'enable');
                action.textContent = skill.enabled ? 'Disable' : 'Enable';
                action.onclick = () => setSkillEnabled(skill.name, !skill.enabled);

                item.appendChild(info);
                item.appendChild(action);
                box.appendChild(item);
            }}
        }}

        async function loadSkills() {{
            try {{
                const response = await fetch('/admin/skills');
                const data = await response.json();
                renderSkills(data.skills || []);
            }} catch (e) {{
                const box = document.getElementById('skills-list');
                box.innerHTML = '<div class="skill-meta">Failed to load skills.</div>';
            }}
        }}

        async function setSkillEnabled(skillName, enabled) {{
            const route = enabled ? 'enable' : 'disable';
            await fetch('/admin/skills/' + encodeURIComponent(skillName) + '/' + route, {{ method: 'POST' }});
            loadSkills();
        }}

        loadSkills();
        pollMessages();
        setInterval(pollMessages, 2000);
    </script>
</body>
</html>
"""
    return HTMLResponse(html)


@app.get("/admin/skills")
def admin_skills() -> dict[str, Any]:
    return {"skills": orchestrator.skill_registry.list_registered_skills()}


@app.post("/admin/skills/{skill_name}/enable")
def admin_enable_skill(skill_name: str) -> dict[str, Any]:
    changed = orchestrator.skill_registry.enable_skill(skill_name)
    if not changed:
        raise HTTPException(status_code=404, detail=f"Unknown skill: {skill_name}")
    return {"ok": True, "skill": skill_name, "enabled": True}


@app.post("/admin/skills/{skill_name}/disable")
def admin_disable_skill(skill_name: str) -> dict[str, Any]:
    changed = orchestrator.skill_registry.disable_skill(skill_name)
    if not changed:
        raise HTTPException(status_code=404, detail=f"Unknown skill: {skill_name}")
    return {"ok": True, "skill": skill_name, "enabled": False}


@app.post("/auth/whatsapp/config")
def whatsapp_configure(
        provider: Annotated[str, Form()],
        phone_number_id: Annotated[str, Form()] = "",
        access_token: Annotated[str, Form()] = "",
        verify_token: Annotated[str, Form()] = "",
        twilio_sid: Annotated[str, Form()] = "",
        twilio_auth_token: Annotated[str, Form()] = "",
        twilio_whatsapp_number: Annotated[str, Form()] = "",
) -> RedirectResponse:
        provider_lower = provider.lower().strip()

        if provider_lower == "meta":
                updates = {
                        "WHATSAPP_PROVIDER": "meta",
                        "WHATSAPP_PHONE_NUMBER_ID": phone_number_id,
                        "WHATSAPP_ACCESS_TOKEN": access_token,
                        "WHATSAPP_VERIFY_TOKEN": verify_token,
                }
                upsert_tokens(updates)
                os.environ.update({key: str(value) for key, value in updates.items() if value})
                return RedirectResponse(url="/admin?message=Meta+WhatsApp+configured", status_code=303)

        if provider_lower == "twilio":
                updates = {
                        "WHATSAPP_PROVIDER": "twilio",
                        "TWILIO_ACCOUNT_SID": twilio_sid,
                        "TWILIO_AUTH_TOKEN": twilio_auth_token,
                        "TWILIO_WHATSAPP_NUMBER": twilio_whatsapp_number,
                }
                upsert_tokens(updates)
                os.environ.update({key: str(value) for key, value in updates.items() if value})
                return RedirectResponse(url="/admin?message=Twilio+WhatsApp+configured", status_code=303)

        return RedirectResponse(url="/admin?message=Unsupported+provider", status_code=303)


@app.post("/auth/telegram/config")
def telegram_configure(
    bot_token: Annotated[str, Form()],
    webhook_secret: Annotated[str, Form()] = "",
) -> RedirectResponse:
    updates = {
        "TELEGRAM_BOT_TOKEN": bot_token,
        "TELEGRAM_WEBHOOK_SECRET": webhook_secret,
    }
    upsert_tokens(updates)
    os.environ.update({key: str(value) for key, value in updates.items() if value})
    return RedirectResponse(url="/admin?message=Telegram+configured", status_code=303)


@app.post("/admin/llm/config")
def llm_configure(
    backend: Annotated[str, Form()],
    model: Annotated[str, Form()] = "",
    base_url: Annotated[str, Form()] = "",
    api_key: Annotated[str, Form()] = "",
) -> RedirectResponse:
    global orchestrator

    backend_value = backend.strip().lower() or "gemini"
    if backend_value not in {"gemini", "ollama", "openai", "mock"}:
        return RedirectResponse(url="/admin?message=Unsupported+LLM+backend", status_code=303)

    updates: dict[str, str] = {
        "LLM_BACKEND": backend_value,
        "LLM_MODEL": model.strip(),
        "LLM_BASE_URL": base_url.strip(),
    }
    if api_key.strip():
        updates["LLM_API_KEY"] = api_key.strip()

    upsert_tokens(updates)

    # Keep environment in sync so subsequent provider construction sees new values.
    for key, value in updates.items():
        if value:
            os.environ[key] = value
        elif key in os.environ:
            os.environ.pop(key, None)

    orchestrator = bootstrap_orchestrator()
    return RedirectResponse(url="/admin?message=LLM+settings+updated", status_code=303)


@app.get("/auth/google/start", response_model=None, responses={400: {"description": "Missing OAuth client id"}})
def google_auth_start(
    services: Annotated[str, Query()] = "gmail,calendar",
    redirect: Annotated[bool, Query()] = False,
) -> JSONResponse | RedirectResponse:
    _cleanup_expired_state()

    requested_services = [item.strip().lower() for item in services.split(",") if item.strip()]
    if not requested_services:
        requested_services = ["gmail", "calendar"]

    client_id = _oauth_client_id()
    if not client_id:
        raise HTTPException(status_code=400, detail="Missing GOOGLE_OAUTH_CLIENT_ID / GOOGLE_CALENDAR_CLIENT_ID / GMAIL_CLIENT_ID")

    scope_map = {
        "gmail": "https://www.googleapis.com/auth/gmail.modify",
        "calendar": "https://www.googleapis.com/auth/calendar",
    }
    selected_scopes = [scope_map[service] for service in requested_services if service in scope_map]
    if not selected_scopes:
        selected_scopes = [scope_map["gmail"], scope_map["calendar"]]

    state = secrets.token_urlsafe(24)
    _OAUTH_STATE[state] = OAuthState(services=requested_services, created_at=time.time())

    redirect_uri = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
    params = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(selected_scopes),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
    )
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"

    if redirect:
        return RedirectResponse(auth_url)

    return JSONResponse({"auth_url": auth_url, "state": state, "services": requested_services})


@app.get("/auth/google/callback", responses={400: {"description": "Invalid OAuth request"}, 502: {"description": "OAuth exchange failed"}})
def google_auth_callback(
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
) -> dict[str, Any]:
    _cleanup_expired_state()
    state_data = _OAUTH_STATE.pop(state, None)
    if state_data is None:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    client_id = _oauth_client_id()
    client_secret = _oauth_client_secret()
    redirect_uri = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Missing Google OAuth client credentials")

    token_request_data = urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
    ).encode("utf-8")
    request = Request(
        url="https://oauth2.googleapis.com/token",
        data=token_request_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=20) as response:
            token_payload = json.loads(response.read().decode("utf-8"))
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"OAuth token exchange failed: {error}") from error

    refresh_token = token_payload.get("refresh_token")
    access_token = token_payload.get("access_token")
    expires_in = token_payload.get("expires_in")

    updates: dict[str, Any] = {
        "GOOGLE_OAUTH_ACCESS_TOKEN": access_token,
        "GOOGLE_OAUTH_REFRESH_TOKEN": refresh_token,
        "GOOGLE_OAUTH_TOKEN_TYPE": token_payload.get("token_type"),
        "GOOGLE_OAUTH_EXPIRES_IN": expires_in,
    }

    if "gmail" in state_data.services:
        updates["GMAIL_ACCESS_TOKEN"] = access_token
        if refresh_token:
            updates["GMAIL_REFRESH_TOKEN"] = refresh_token

    if "calendar" in state_data.services:
        updates["GOOGLE_CALENDAR_ACCESS_TOKEN"] = access_token
        if refresh_token:
            updates["GOOGLE_CALENDAR_REFRESH_TOKEN"] = refresh_token

    upsert_tokens(updates)

    return {
        "connected": state_data.services,
        "token_saved": True,
        "has_access_token": bool(access_token),
        "has_refresh_token": bool(refresh_token),
        "expires_in": expires_in,
    }







@app.get("/chat", response_class=HTMLResponse)
def webchat_page() -> HTMLResponse:
        html = """
<!DOCTYPE html>
<html lang='en'>
<head>
    <meta charset='UTF-8' />
    <meta name='viewport' content='width=device-width, initial-scale=1.0' />
    <title>Webchat</title>
    <style>
        body { font-family: Segoe UI, Inter, Arial, sans-serif; background: #f6f8fb; margin: 0; }
        .wrap { max-width: 760px; margin: 30px auto; padding: 0 16px; }
        .card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; }
        .log { height: 340px; overflow-y: auto; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 10px; padding: 10px; margin-bottom: 12px; }
        .row { display: grid; grid-template-columns: 1fr auto; gap: 8px; }
        input { padding: 10px; border: 1px solid #d1d5db; border-radius: 10px; }
        button { background: #2563eb; color: #fff; border: none; border-radius: 10px; padding: 10px 14px; }
        .item { margin-bottom: 8px; }
        .user { color: #111827; }
        .bot { color: #1d4ed8; }
    </style>
</head>
<body>
    <div class='wrap'>
        <div class='card'>
            <h2>Webchat</h2>
            <div id='log' class='log'></div>
            <div class='row'>
                <input id='msg' placeholder='Type: add task prepare sprint demo' />
                <button onclick='send()'>Send</button>
            </div>
        </div>
    </div>
    <script>
        const sessionId = 'webchat-demo-user';
        const log = document.getElementById('log');
        const input = document.getElementById('msg');
        function addLine(text, cls){
            const d = document.createElement('div');
            d.className = 'item ' + cls;
            d.textContent = text;
            log.appendChild(d);
            log.scrollTop = log.scrollHeight;
        }
        async function send(){
            const message = input.value.trim();
            if(!message) return;
            addLine('You: ' + message, 'user');
            input.value = '';
            const response = await fetch('/webchat/message', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({session_id: sessionId, message})
            });
            const data = await response.json();
            addLine('Agent: ' + (data.reply || data.message || 'OK'), 'bot');
        }
    </script>
</body>
</html>
"""
        return HTMLResponse(html)


@app.post("/webchat/message")
def webchat_message(payload: WebChatMessageIn) -> dict[str, Any]:
        result = orchestrator.handle_channel_command(
                text=payload.message,
                sender=payload.session_id,
                provider=webchat_provider,
        )
        return {
                "success": result.success,
                "reply": result.message,
                "action": result.action,
                "data": result.data,
        }


# Track last processed Telegram update ID for polling
_LAST_TELEGRAM_UPDATE_ID: int = 0


@app.get("/messages")
def get_messages(since: int = Query(default=0)) -> list[dict[str, Any]]:
    return [msg for msg in _MESSAGE_LOG if msg["id"] >= since]


@app.post("/telegram/poll")
def telegram_poll() -> dict[str, Any]:
    """
    Poll Telegram for new messages and process them.
    This is an alternative to webhooks for development/testing.
    """
    global _LAST_TELEGRAM_UPDATE_ID
    
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or get_token("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return {"status": "error", "message": "No Telegram bot token configured"}
    
    import json as json_module
    from urllib.request import Request as UrlRequest
    
    # Fetch updates since last processed update
    offset = _LAST_TELEGRAM_UPDATE_ID + 1 if _LAST_TELEGRAM_UPDATE_ID else None
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates?limit=10&timeout=1"
    if offset:
        url += f"&offset={offset}"
    
    try:
        req = UrlRequest(url, method="GET")
        with urlopen(req, timeout=5) as response:
            data = json_module.loads(response.read().decode("utf-8"))
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
    updates = data.get("result", []) if data.get("ok") else []
    processed = 0
    
    for update in updates:
        update_id = update.get("update_id", 0)
        _LAST_TELEGRAM_UPDATE_ID = max(_LAST_TELEGRAM_UPDATE_ID, update_id)
        
        message = update.get("message") or update.get("edited_message") or {}
        text = message.get("text", "")
        sender = str((message.get("chat") or {}).get("id", ""))
        
        if sender and text:
            # Check if this message is already in the log (avoid duplicates)
            already_logged = any(
                msg.get("channel") == "telegram" 
                and msg.get("sender") == sender 
                and msg.get("text") == text
                for msg in list(_MESSAGE_LOG)[-20:]
            )
            
            if not already_logged:
                _add_message(channel="telegram", sender=sender, role="user", text=text)
                result = orchestrator.handle_channel_command(text=text, sender=sender, provider=telegram_provider)
                _add_message(channel="telegram", sender="agent", role="agent", text=result.message)
                processed += 1
    
    return {"status": "ok", "processed": processed, "last_update_id": _LAST_TELEGRAM_UPDATE_ID}


@app.post("/webhooks/telegram")
async def telegram_webhook(
        request: FastAPIRequest,
        x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
        expected_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET") or get_token("TELEGRAM_WEBHOOK_SECRET")
        if expected_secret and x_telegram_bot_api_secret_token != expected_secret:
                raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")

        payload = await request.json()
        message = payload.get("message") or payload.get("edited_message") or {}
        text = message.get("text", "")
        sender = str((message.get("chat") or {}).get("id", ""))
        if sender and text:
                _add_message(channel="telegram", sender=sender, role="user", text=text)
                result = orchestrator.handle_channel_command(text=text, sender=sender, provider=telegram_provider)
                _add_message(channel="telegram", sender="agent", role="agent", text=result.message)

        return {"status": "ok"}
