# Lightweight AI Agent 
Lightweight, extensible AI agent system for personal productivity workflows:
- Manage calendar (create, update, delete, conflict checks, reminders)
- Read and classify emails (summaries, action-item extraction)
- Update calendar from extracted email action items

## Phase 1: Architecture

### Core design
- `Orchestrator`: routes intents to skills and coordinates cross-skill flows
- `SkillRegistry`: plugin-style registration and intent-based resolution
- `Context`: shared state/memory for current session
- `Skills`: focused business logic per domain (`calendar`, `email`)
- `Integrations`: provider adapters (Google Calendar, Gmail)
- `Schemas`: typed models with Pydantic for requests/results/entities

### Folder structure
```text
src/
   main.py
   agent/
      context.py
      orchestrator.py
      registry.py
   integrations/
      gmail.py
      google_calendar.py
   models/
      schemas.py
   skills/
      calendar/skill.py
      email/skill.py
   utils/
      logger.py
tests/
   test_orchestrator.py
   test_skills.py
```

## Phase 2-4: Implemented capabilities

### Orchestration
- Intent routing by `preferred_skill` or skill `can_handle()`
- Retries and failure-safe `SkillResult`
- Built-in multi-skill workflows:
   - "Summarize my unread emails and add action items to calendar"

### Skills
- `CalendarSkill`: create/update/delete/list, conflict checks, scheduling action items
- `EmailSkill`: unread summary, basic classification, action-item extraction

### Integrations
- `CalendarProvider`: Google Calendar API (in-memory fallback for testing)
- `GmailProvider`: Gmail API for unread inbox
- `LLMProvider`: selectable backend (`gemini`, `ollama`, `openai`, `mock`)
- `WhatsAppProvider`: message channel adapter for command intake/response
- `TelegramProvider`: Telegram Bot API adapter for inbound/outbound chat
- `WebChatProvider`: built-in local webchat adapter

### FastAPI automation layer
- Google OAuth connect/callback endpoints for automatic credential persistence
- WhatsApp webhook endpoints for Twilio and Meta Cloud API
- Telegram webhook endpoint
- Built-in webchat page and message endpoint
- Token persistence in `.runtime_tokens.json` (configurable via `TOKEN_STORE_PATH`)

## Setup (Windows-friendly)

### Option A: pip + requirements
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

### Option B: Poetry
```powershell
poetry install
Copy-Item .env.example .env
```

## Run

```powershell
python -m src.main "Summarize my unread emails and add action items to calendar"
```

Run API server:
```powershell
uvicorn src.api.server:app --reload --port 8000
```

Open admin UI:
```text
http://localhost:8000/admin
```

Open built-in webchat:
```text
http://localhost:8000/chat
```

WhatsApp-style command (creates task/event via LLM parsing):
```powershell
python -m src.main "add task prepare sprint demo" --channel whatsapp --from "+15551234567"
```

With explicit action/payload:
```powershell
python -m src.main "Create a meeting" --skill calendar --action create --payload '{"title":"1:1","start_time":"2026-03-07T10:00:00","end_time":"2026-03-07T10:30:00"}'
```

## Test

```powershell
pytest -q
```

## FastAPI OAuth + WhatsApp setup

### Google OAuth (auto token integration)
1. Set `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, and `GOOGLE_OAUTH_REDIRECT_URI` in `.env`.
2. Start API server.
3. Open:
    - `http://localhost:8000/auth/google/start?services=gmail,calendar&redirect=true`
4. Approve consent in Google.
5. Callback auto-saves tokens to `.runtime_tokens.json`.

### WhatsApp webhooks
- Meta verify/callback:
   - GET `http://localhost:8000/webhooks/whatsapp/meta`
   - POST `http://localhost:8000/webhooks/whatsapp/meta`
- Twilio callback:
   - POST `http://localhost:8000/webhooks/whatsapp/twilio`

Set provider mode in `.env`:
- `WHATSAPP_PROVIDER=twilio` with `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER`
- `WHATSAPP_PROVIDER=meta` with `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_VERIFY_TOKEN`

You can also configure WhatsApp credentials from the admin page forms (`/admin`) and they are persisted in `.runtime_tokens.json`.

### Telegram webhook
- Endpoint:
   - POST `http://localhost:8000/webhooks/telegram`
- Configure credentials in `.env` or from `/admin`:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_WEBHOOK_SECRET` (optional but recommended)

#### Telegram review mode (before calendar save)
- For Telegram, `email_to_calendar` requests are collected first and sent back as numbered candidates.
- Nothing is saved to calendar until you confirm in chat.
- Reply commands:
   - `keep 1,3` → save only selected items
   - `disregard 2` → remove item(s) from pending list
   - `keep all` / `approve all` → save all pending items
   - `show` → reprint current review list
   - `cancel` → discard everything pending

### Webchat
- Open `http://localhost:8000/chat`
- Send commands in plain language (same command style as CLI/WhatsApp)

### LLM model choice from Admin
- Open `http://localhost:8000/admin`
- In the **LLM Model** card choose backend + model and save.
- Settings are persisted and applied immediately.
- Examples:
   - Local Mistral via Ollama: backend `ollama`, model `mistral:7b-instruct`, base URL `http://localhost:11434`
   - Gemini cloud: backend `gemini`, model `gemini-2.5-flash`, set `LLM_API_KEY`

## LLM + local model setup

### Local (Ollama)
```powershell
ollama pull qwen2.5:7b-instruct
```

Set in `.env`:
```dotenv
LLM_BACKEND=ollama
LLM_MODEL=mistral:7b-instruct
LLM_BASE_URL=http://localhost:11434
```

### Cloud (OpenAI-compatible)
Set in `.env`:
```dotenv
LLM_BACKEND=openai
LLM_MODEL=gpt-4.1-mini
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your_key_here
```

## Phase 6: Extension points for new skills

1. Create `src/skills/<new_skill>/skill.py` with:
   - `name`, `version`, `description`, `actions`, `required_env`
    - `can_handle(intent: str) -> bool`
    - `execute(action: str, payload: dict, context: Context) -> SkillResult`
   - `create_skill(dependencies: dict[str, Any]) -> Skill`
2. Add provider adapter under `src/integrations/` if needed.
3. Skill modules are auto-discovered from `src/skills/*/skill.py` by the loader.
4. Optionally disable any skill at startup with `SKILLS_DISABLED=skill_name_1,skill_name_2`.
5. Manage skill enable/disable at runtime via admin UI or API (`/admin/skills`).
6. Add tests in `tests/test_skills.py` and optional orchestration tests.

This keeps runtime lightweight while allowing incremental skill growth.