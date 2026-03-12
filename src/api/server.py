from __future__ import annotations

import json
import os
import secrets
import sys
import time
from html import escape
from dataclasses import dataclass
from pathlib import Path
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
    if service == "youtube":
        return bool(
            os.getenv("YOUTUBE_API_KEY")
            or get_token("YOUTUBE_API_KEY")
        )
    return False


@app.get("/admin", response_class=HTMLResponse)
def admin_page(message: str | None = Query(default=None)) -> HTMLResponse:
    google_connected = _connected("gmail") and _connected("calendar")
    telegram_connected = _connected("telegram")
    youtube_connected = _connected("youtube")
    facebook_configured = bool(os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN") and os.getenv("FACEBOOK_PAGE_ID"))
    instagram_configured = bool(os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID") and os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN"))
    cdn_backend = os.getenv("CDN_BACKEND", "local")

    not_configured = "Not configured"
    status_google = "Connected" if google_connected else "Not connected"
    status_telegram = "Configured" if telegram_connected else not_configured
    status_youtube = "Connected" if youtube_connected else "Not connected"
    status_facebook = "Configured" if facebook_configured else not_configured
    status_instagram = "Configured" if instagram_configured else not_configured
    status_cdn = f"Active ({cdn_backend})"
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
    
    youtube_action_html = (
        """
        <div class='action-row'>
            <button class='button connected' type='button' disabled>YouTube Connected</button>
            <a class='button secondary' href='/auth/google/start?services=youtube&redirect=true'>Reconnect YouTube</a>
        </div>
        """
        if youtube_connected
        else "<a class='button' href='/auth/google/start?services=youtube&redirect=true'>Connect YouTube</a>"
    )
    
    facebook_action_html = """
        <form method='post' action='/auth/facebook/config'>
            <div class='row'><label>Page Access Token</label><input name='page_access_token' type='password' required /></div>
            <div class='row'><label>Page ID</label><input name='page_id' required /></div>
            <div class='row'><label>App ID (optional)</label><input name='app_id' /></div>
            <div class='row'><label>App Secret (optional)</label><input name='app_secret' type='password' /></div>
            <button type='submit'>Save Facebook Credentials</button>
        </form>
    """
    
    instagram_action_html = """
        <form method='post' action='/auth/instagram/config'>
            <div class='row'><label>Business Account ID</label><input name='account_id' required /></div>
            <div class='muted' style='margin-top:-5px;'>Use same Page Access Token as Facebook</div>
            <button type='submit'>Save Instagram Credentials</button>
        </form>
    """
    
    cdn_action_html = f"""
        <form method='post' action='/auth/cdn/config'>
            <div class='row'>
                <label>CDN Backend</label>
                <select name='cdn_backend'>
                    <option value='local' {'selected' if cdn_backend == 'local' else ''}>Local Server (Testing)</option>
                    <option value='s3' {'selected' if cdn_backend == 's3' else ''}>AWS S3 (Production)</option>
                    <option value='cloudflare' {'selected' if cdn_backend == 'cloudflare' else ''}>Cloudflare R2 (Production)</option>
                </select>
            </div>
            <div class='row'><label>Server Port (local only)</label><input name='server_port' value='8080' placeholder='8080' /></div>
            <div class='row'><label>S3 Bucket (S3/R2 only)</label><input name='s3_bucket' placeholder='my-videos-bucket' /></div>
            <div class='row'><label>AWS Region (S3 only)</label><input name='aws_region' placeholder='us-east-1' /></div>
            <button type='submit'>Save CDN Config</button>
        </form>
    """
    
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
        
        /* Tabs */
        .tabs {{
            display: flex;
            gap: 8px;
            margin-bottom: 24px;
            border-bottom: 2px solid var(--border);
        }}
        .tab {{
            padding: 12px 20px;
            background: transparent;
            border: none;
            border-bottom: 3px solid transparent;
            color: var(--muted);
            cursor: pointer;
            font-size: 15px;
            font-weight: 600;
            transition: all 0.2s;
        }}
        .tab:hover {{
            color: var(--text);
            background: #f3f4f6;
        }}
        .tab.active {{
            color: var(--primary);
            border-bottom-color: var(--primary);
        }}
        .tab-content {{
            display: none;
        }}
        .tab-content.active {{
            display: block;
        }}
        .section-title {{
            font-size: 22px;
            margin: 0 0 8px;
        }}
        .tab-subtitle {{
            color: var(--muted);
            margin: 0 0 20px;
            font-size: 14px;
        }}
        .pipeline-status {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        .pipeline-status h3 {{
            color: white;
        }}
        .pipeline-status .status {{
            color: rgba(255, 255, 255, 0.9);
        }}
        .pipeline-status .muted {{
            color: rgba(255, 255, 255, 0.8);
        }}
        .pipeline-actions {{
            display: flex;
            gap: 8px;
            margin: 12px 0;
        }}
        .pipeline-actions .button {{
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
        }}
        .pipeline-actions .button:hover {{
            background: rgba(255, 255, 255, 0.3);
        }}
        .pipeline-actions .button.secondary {{
            background: rgba(0, 0, 0, 0.2);
        }}
        .pipeline-actions .button.secondary:hover {{
            background: rgba(0, 0, 0, 0.3);
        }}
        a {{
            color: var(--primary);
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class='container'>
        <h1 class='title'>🎬 LightClaw Admin</h1>
        <p class='subtitle'>Manage integrations, social media, and automation pipeline</p>
        {message_html}
        
        <div class='tabs'>
            <button class='tab active' onclick='showTab("core")'>Core Services</button>
            <button class='tab' onclick='showTab("social")'>Social Media</button>
            <button class='tab' onclick='showTab("skills")'>Skills</button>
        </div>
        
        <!-- Core Services Tab -->
        <div id='tab-core' class='tab-content active'>
            <h2 class='section-title'>Core Services</h2>
            <div class='grid'>
                <div class='card'>
                    <h3>Google (Gmail + Calendar)<span class='required'>Required</span></h3>
                    <div class='status'>Status: <span class='{"ok" if google_connected else ""}'>{status_google}</span></div>
                    {google_action_html}
                    <div class='muted'>Uses OAuth consent and stores tokens automatically.</div>
                </div>

                <div class='card'>
                    <h3>Webchat<span class='required'>Required</span></h3>
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
            </div>
        </div>
        
        <!-- Social Media Tab -->
        <div id='tab-social' class='tab-content'>
            <h2 class='section-title'>Social Media Automation</h2>
            <p class='tab-subtitle'>Configure platforms for automated video uploads</p>
            <div class='grid'>
                <div class='card'>
                    <h3>🎥 YouTube<span class='required'>Required</span></h3>
                    <div class='status'>Status: <span class='{"ok" if youtube_connected else ""}'>{status_youtube}</span></div>
                    {youtube_action_html}
                    <div class='muted'>OAuth 2.0 authentication for video uploads. Required for automation pipeline.</div>
                </div>

                <div class='card'>
                    <h3>📱 Facebook Page</h3>
                    <div class='status'>Status: <span class='{"ok" if facebook_configured else ""}'>{status_facebook}</span></div>
                    {facebook_action_html}
                    <div class='muted'>
                        Get credentials from <a href='https://developers.facebook.com/' target='_blank'>Meta Developer Console</a>.<br>
                        <a href='/docs/social-media' target='_blank'>Setup Guide</a>
                    </div>
                </div>

                <div class='card'>
                    <h3>📷 Instagram</h3>
                    <div class='status'>Status: <span class='{"ok" if instagram_configured else ""}'>{status_instagram}</span></div>
                    {instagram_action_html}
                    <div class='muted'>
                        Requires Instagram Business Account linked to Facebook Page.<br>
                        <a href='/docs/social-media#instagram' target='_blank'>Setup Guide</a>
                    </div>
                </div>

                <div class='card'>
                    <h3>🌐 CDN / File Server</h3>
                    <div class='status'>Status: <span class='ok'>{status_cdn}</span></div>
                    {cdn_action_html}
                    <div class='muted'>
                        Instagram requires publicly accessible URLs.<br>
                        Use local for testing, S3/R2 for production.
                    </div>
                </div>
                
                <div class='card pipeline-status'>
                    <h3>⚙️ Pipeline Status</h3>
                    <div id='pipeline-status' class='status'>Checking...</div>
                    <div class='pipeline-actions'>
                        <button class='button' onclick='testPipeline()'>Test Pipeline</button>
                        <button class='button secondary' onclick='viewLogs()'>View Logs</button>
                    </div>
                    <div class='muted'>Run automation pipeline test to verify all integrations.</div>
                </div>
            </div>
        </div>
        
        <!-- Skills Tab -->
        <div id='tab-skills' class='tab-content'>
            <h2 class='section-title'>Skills Management</h2>
            <p class='tab-subtitle'>Enable or disable skills without restarting the server</p>
            <div id='skills-list' class='skill-list'></div>
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
        
        // Tab switching
        function showTab(tabName) {{
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
            
            // Show selected tab
            document.getElementById('tab-' + tabName).classList.add('active');
            event.target.classList.add('active');
        }}
        
        // Pipeline testing
        async function testPipeline() {{
            const statusEl = document.getElementById('pipeline-status');
            statusEl.innerHTML = '<span style="color: #fbbf24;">⏳ Testing pipeline...</span>';
            
            try {{
                const response = await fetch('/api/pipeline/test', {{ method: 'POST' }});
                const data = await response.json();
                
                if (data.success) {{
                    statusEl.innerHTML = '<span style="color: #10b981;">✅ Pipeline test passed!</span>';
                }} else {{
                    statusEl.innerHTML = '<span style="color: #ef4444;">❌ Test failed: ' + (data.error || 'Unknown error') + '</span>';
                }}
            }} catch (error) {{
                statusEl.innerHTML = '<span style="color: #ef4444;">❌ Test failed: ' + error.message + '</span>';
            }}
        }}
        
        function viewLogs() {{
            window.open('/logs', '_blank');
        }}
        
        // Check pipeline status on load
        async function checkPipelineStatus() {{
            try {{
                const response = await fetch('/api/pipeline/status');
                const data = await response.json();
                const statusEl = document.getElementById('pipeline-status');
                
                const platforms = [];
                if (data.youtube) platforms.push('YouTube');
                if (data.facebook) platforms.push('Facebook');
                if (data.instagram) platforms.push('Instagram');
                
                if (platforms.length === 0) {{
                    statusEl.innerHTML = '<span style="color: #ef4444;">❌ No platforms configured</span>';
                }} else if (platforms.length === 3) {{
                    statusEl.innerHTML = '<span style="color: #10b981;">✅ All platforms ready: ' + platforms.join(', ') + '</span>';
                }} else {{
                    statusEl.innerHTML = '<span style="color: #fbbf24;">⚠️ Partial: ' + platforms.join(', ') + '</span>';
                }}
            }} catch (error) {{
                document.getElementById('pipeline-status').innerHTML = '<span style="color: #6b7280;">Status unavailable</span>';
            }}
        }}
        
        checkPipelineStatus();
        setInterval(checkPipelineStatus, 10000); // Check every 10 seconds
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


@app.post("/auth/facebook/config")
def facebook_configure(
    page_access_token: Annotated[str, Form()],
    page_id: Annotated[str, Form()],
    app_id: Annotated[str, Form()] = "",
    app_secret: Annotated[str, Form()] = "",
) -> RedirectResponse:
    updates = {
        "FACEBOOK_PAGE_ACCESS_TOKEN": page_access_token,
        "FACEBOOK_PAGE_ID": page_id,
    }
    if app_id:
        updates["FACEBOOK_APP_ID"] = app_id
    if app_secret:
        updates["FACEBOOK_APP_SECRET"] = app_secret
    
    upsert_tokens(updates)
    os.environ.update({key: str(value) for key, value in updates.items() if value})
    return RedirectResponse(url="/admin?message=Facebook+configured", status_code=303)


@app.post("/auth/instagram/config")
def instagram_configure(
    account_id: Annotated[str, Form()],
) -> RedirectResponse:
    updates = {
        "INSTAGRAM_BUSINESS_ACCOUNT_ID": account_id,
    }
    upsert_tokens(updates)
    os.environ.update({key: str(value) for key, value in updates.items() if value})
    return RedirectResponse(url="/admin?message=Instagram+configured", status_code=303)


@app.post("/auth/cdn/config")
def cdn_configure(
    cdn_backend: Annotated[str, Form()],
    server_port: Annotated[str, Form()] = "8080",
    s3_bucket: Annotated[str, Form()] = "",
    aws_region: Annotated[str, Form()] = "us-east-1",
) -> RedirectResponse:
    updates = {
        "CDN_BACKEND": cdn_backend,
        "FILE_SERVER_PORT": server_port,
    }
    if s3_bucket:
        updates["AWS_S3_BUCKET"] = s3_bucket
        updates["CLOUDFLARE_R2_BUCKET"] = s3_bucket  # Can be used for both
    if aws_region:
        updates["AWS_REGION"] = aws_region
    
    upsert_tokens(updates)
    os.environ.update({key: str(value) for key, value in updates.items() if value})
    return RedirectResponse(url="/admin?message=CDN+configured", status_code=303)


@app.get("/api/pipeline/status")
def pipeline_status() -> dict[str, Any]:
    """Get pipeline configuration status."""
    return {
        "youtube": _connected("youtube"),
        "facebook": bool(os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN") and os.getenv("FACEBOOK_PAGE_ID")),
        "instagram": bool(os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID") and os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")),
        "cdn_backend": os.getenv("CDN_BACKEND", "local"),
    }


@app.post("/api/pipeline/test")
def pipeline_test() -> dict[str, Any]:
    """Test the automation pipeline configuration."""
    try:
        # Check YouTube
        if not _connected("youtube"):
            return {"success": False, "error": "YouTube not connected"}
        
        # Check if pipeline script exists
        pipeline_path = Path("automation_pipeline.py")
        if not pipeline_path.exists():
            return {"success": False, "error": "Pipeline script not found"}
        
        # Try to import and check
        import sys
        sys.path.insert(0, str(Path.cwd()))
        
        # Basic validation
        errors = []
        
        if not os.getenv("GOOGLE_OAUTH_CLIENT_ID"):
            errors.append("Missing GOOGLE_OAUTH_CLIENT_ID")
        
        facebook_configured = bool(os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN") and os.getenv("FACEBOOK_PAGE_ID"))
        instagram_configured = bool(os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID") and os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN"))
        
        platforms = ["YouTube"]
        if facebook_configured:
            platforms.append("Facebook")
        if instagram_configured:
            platforms.append("Instagram")
        
        if errors:
            return {"success": False, "error": ", ".join(errors)}
        
        return {
            "success": True,
            "message": f"Pipeline ready for {', '.join(platforms)}",
            "platforms": platforms
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/logs", response_class=HTMLResponse)
def view_logs() -> HTMLResponse:
    """View automation logs."""
    log_file = Path("logs/automation.log")
    
    if not log_file.exists():
        content = "No logs found. Pipeline hasn't run yet."
    else:
        try:
            # Read last 1000 lines
            with open(log_file, 'r') as f:
                lines = f.readlines()
                content = ''.join(lines[-1000:])
        except Exception as e:
            content = f"Error reading logs: {e}"
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Pipeline Logs</title>
    <style>
        body {{ font-family: 'Courier New', monospace; background: #1e1e1e; color: #d4d4d4; padding: 20px; }}
        .log-container {{ background: #252526; padding: 20px; border-radius: 8px; }}
        .log-content {{ white-space: pre-wrap; word-wrap: break-word; font-size: 13px; line-height: 1.5; }}
        .back-link {{ display: inline-block; margin-bottom: 15px; color: #4fc3f7; text-decoration: none; }}
        .back-link:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <a href="/admin" class="back-link">← Back to Admin</a>
    <div class="log-container">
        <div class="log-content">{escape(content)}</div>
    </div>
</body>
</html>
"""
    return HTMLResponse(html)


@app.get("/docs/social-media", response_class=HTMLResponse)
def social_media_docs() -> HTMLResponse:
    """Redirect to social media documentation."""
    return RedirectResponse(url="https://github.com/your-repo/blob/main/SOCIAL_MEDIA_INTEGRATION.md", status_code=303)


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
