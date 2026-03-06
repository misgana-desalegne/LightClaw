# Lightweight AI Agent (Skill-Focused)

Lightweight, extensible AI agent system for personal productivity workflows:
- Manage calendar (create, update, delete, conflict checks, reminders)
- Read and classify emails (summaries, action-item extraction)
- Search events/web and suggest options
- Update calendar from email and event search outcomes

## Phase 1: Architecture

### Core design
- `Orchestrator`: routes intents to skills and coordinates cross-skill flows
- `SkillRegistry`: plugin-style registration and intent-based resolution
- `Context`: shared state/memory for current session
- `Skills`: focused business logic per domain (`calendar`, `email`, `events`)
- `Integrations`: provider adapters (currently mock/in-memory stubs)
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
      web_search.py
   models/
      schemas.py
   skills/
      calendar/skill.py
      email/skill.py
      events/skill.py
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
   - "Find AI events this weekend and schedule the best option"

### Skills
- `CalendarSkill`: create/update/delete/list, conflict checks, scheduling action items
- `EmailSkill`: unread summary, basic classification, action-item extraction
- `EventsSkill`: event search and best-option selection

### Integration stubs (replaceable)
- `CalendarProvider`: in-memory event store with overlap detection
- `GmailProvider`: mock unread inbox data
- `WebSearchProvider`: mock event suggestions
- `LLMProvider`: `mock`, `ollama`, or OpenAI-compatible backends
- `WhatsAppProvider`: message channel adapter for command intake/response

### FastAPI automation layer
- Google OAuth connect/callback endpoints for automatic credential persistence
- WhatsApp webhook endpoints for Twilio and Meta Cloud API
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

```powershell
python -m src.main "Find AI events this weekend and schedule the best option"
```

Run API server:
```powershell
uvicorn src.api.server:app --reload --port 8000
```

Open admin UI:
```text
http://localhost:8000/admin
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
- `WHATSAPP_PROVIDER=mock` for local tests
- `WHATSAPP_PROVIDER=twilio` with `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER`
- `WHATSAPP_PROVIDER=meta` with `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_VERIFY_TOKEN`

You can also configure WhatsApp credentials from the admin page forms (`/admin`) and they are persisted in `.runtime_tokens.json`.

## LLM + local model setup

### Local (Ollama)
```powershell
ollama pull qwen2.5:7b-instruct
```

Set in `.env`:
```dotenv
LLM_BACKEND=ollama
LLM_MODEL=qwen2.5:7b-instruct
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
    - `name`
    - `can_handle(intent: str) -> bool`
    - `execute(action: str, payload: dict, context: Context) -> SkillResult`
2. Add provider adapter under `src/integrations/` if needed.
3. Register skill in `bootstrap_orchestrator()` in `src/main.py`.
4. Add tests in `tests/test_skills.py` and optional orchestration tests.

This keeps runtime lightweight while allowing incremental skill growth.