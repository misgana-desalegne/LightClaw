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

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Query, Request as FastAPIRequest
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse

from src.main import bootstrap_orchestrator
from src.integrations.token_store import get_token, upsert_tokens
from src.integrations.whatsapp import WhatsAppProvider

load_dotenv()

app = FastAPI(title="Lightweight AI Agent API", version="0.1.0")
orchestrator = bootstrap_orchestrator()
whatsapp_provider = WhatsAppProvider()


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
            "google_auth_start": "/auth/google/start?services=gmail,calendar&redirect=true",
            "google_auth_callback": "/auth/google/callback",
            "whatsapp_meta_verify": "/webhooks/whatsapp/meta",
            "whatsapp_twilio_webhook": "/webhooks/whatsapp/twilio",
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
        if service == "whatsapp_meta":
                return bool(
                        os.getenv("WHATSAPP_PHONE_NUMBER_ID")
                        or get_token("WHATSAPP_PHONE_NUMBER_ID")
                ) and bool(
                        os.getenv("WHATSAPP_ACCESS_TOKEN")
                        or get_token("WHATSAPP_ACCESS_TOKEN")
                )
        if service == "whatsapp_twilio":
                return bool(
                        os.getenv("TWILIO_ACCOUNT_SID")
                        or get_token("TWILIO_ACCOUNT_SID")
                ) and bool(
                        os.getenv("TWILIO_AUTH_TOKEN")
                        or get_token("TWILIO_AUTH_TOKEN")
                ) and bool(
                        os.getenv("TWILIO_WHATSAPP_NUMBER")
                        or get_token("TWILIO_WHATSAPP_NUMBER")
                )
        return False


@app.get("/admin", response_class=HTMLResponse)
def admin_page(message: str | None = Query(default=None)) -> HTMLResponse:
        google_connected = _connected("gmail") and _connected("calendar")
        meta_connected = _connected("whatsapp_meta")
        twilio_connected = _connected("whatsapp_twilio")

        status_google = "Connected" if google_connected else "Not connected"
        status_meta = "Configured" if meta_connected else "Not configured"
        status_twilio = "Configured" if twilio_connected else "Not configured"
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
        .muted {{ color: var(--muted); font-size: 12px; margin-top: 6px; }}
        .notice {{ margin: 0 0 18px; padding: 10px 12px; border-radius: 10px; font-size: 14px; }}
        .notice.success {{ background: #ecfdf3; color: #166534; border: 1px solid #86efac; }}
    </style>
</head>
<body>
    <div class='container'>
        <h1 class='title'>Admin Authentication</h1>
        <p class='subtitle'>Connect Google and WhatsApp with simple buttons.</p>
        {message_html}
        <div class='grid'>
            <div class='card'>
                <h3>Google (Gmail + Calendar)</h3>
                <div class='status'>Status: <span class='{"ok" if google_connected else ""}'>{status_google}</span></div>
                <a class='button' href='/auth/google/start?services=gmail,calendar&redirect=true'>Connect Google</a>
                <div class='muted'>Uses OAuth consent and stores tokens automatically.</div>
            </div>

            <div class='card'>
                <h3>WhatsApp (Meta Cloud API)</h3>
                <div class='status'>Status: <span class='{"ok" if meta_connected else ""}'>{status_meta}</span></div>
                <form method='post' action='/auth/whatsapp/config'>
                    <input type='hidden' name='provider' value='meta' />
                    <div class='row'><label>Phone Number ID</label><input name='phone_number_id' /></div>
                    <div class='row'><label>Access Token</label><input name='access_token' /></div>
                    <div class='row'><label>Verify Token</label><input name='verify_token' /></div>
                    <button type='submit'>Save Meta Credentials</button>
                </form>
                <div class='muted'>Webhook verify URL: /webhooks/whatsapp/meta</div>
            </div>

            <div class='card'>
                <h3>WhatsApp (Twilio)</h3>
                <div class='status'>Status: <span class='{"ok" if twilio_connected else ""}'>{status_twilio}</span></div>
                <form method='post' action='/auth/whatsapp/config'>
                    <input type='hidden' name='provider' value='twilio' />
                    <div class='row'><label>Account SID</label><input name='twilio_sid' /></div>
                    <div class='row'><label>Auth Token</label><input name='twilio_auth_token' /></div>
                    <div class='row'><label>WhatsApp Number (e.g. whatsapp:+14155238886)</label><input name='twilio_whatsapp_number' /></div>
                    <button type='submit'>Save Twilio Credentials</button>
                </form>
                <div class='muted'>Webhook URL: /webhooks/whatsapp/twilio</div>
            </div>
        </div>
    </div>
</body>
</html>
"""
        return HTMLResponse(html)


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


@app.get("/webhooks/whatsapp/meta", responses={403: {"description": "Invalid verify token"}})
def whatsapp_meta_verify(
    mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
    verify_token: Annotated[str | None, Query(alias="hub.verify_token")] = None,
) -> PlainTextResponse:
    expected_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    if mode == "subscribe" and verify_token and verify_token == expected_token:
        return PlainTextResponse(challenge or "")
    raise HTTPException(status_code=403, detail="Invalid verify token")


@app.post("/webhooks/whatsapp/meta")
async def whatsapp_meta_webhook(request: FastAPIRequest) -> dict[str, str]:
    payload = await request.json()
    entries = payload.get("entry", []) if isinstance(payload, dict) else []
    for entry in entries:
        for change in entry.get("changes", []):
            messages = change.get("value", {}).get("messages", [])
            for message in messages:
                sender = message.get("from")
                text = message.get("text", {}).get("body", "")
                if sender and text:
                    orchestrator.handle_whatsapp_command(text=text, sender=sender, provider=whatsapp_provider)

    return {"status": "ok"}


@app.post("/webhooks/whatsapp/twilio", responses={400: {"description": "Missing sender number"}})
def whatsapp_twilio_webhook(
    body: Annotated[str, Form()] = "",
    from_number: Annotated[str, Form(alias="From")] = "",
) -> JSONResponse:
    if not from_number:
        raise HTTPException(status_code=400, detail="Missing From")
    result = orchestrator.handle_whatsapp_command(text=body, sender=from_number, provider=whatsapp_provider)
    return JSONResponse({"status": "ok", "message": result.message})
