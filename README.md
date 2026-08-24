# 🎯 PlacementOS — AI Placement Intelligence Monitor

> A self-hosted, single-user placement assistant that watches your college
> placement Telegram group 24/7, reads every message / PDF / Excel sheet /
> photo / Google Form link, extracts real opportunities with local NLP
> (Gemini optional), tracks deadlines deterministically, and alerts you on
> Telegram before it's too late.

**Design principle:** recall > precision. A false alert is acceptable; a
missed genuine opportunity is not. The core loop works fully offline — no
AI API keys required.

---

## ✨ Features (as implemented)

| Feature | Description |
|---------|-------------|
| 🔴 **Live Monitoring** | Telethon userbot listens to your placement group + catches up missed history |
| 🤖 **Local-First Extraction** | spaCy/dateparser NLP engine always runs; Gemini Flash→Pro is an *optional* enhancer |
| 🧑‍💼 **Excel Shortlist Finder** | Result sheets (.xlsx/.csv) scanned cell-by-cell for your USN/name → instant 🎉 shortlist Telegram alert |
| 🎯 **Role-First CSE Engine** | 150+ CSE-family roles (SDE/FSD/QA/Data Analyst/DevOps…) matched even when branches aren't mentioned; verdicts `CSE_BOTH/CSE_ROLE/CSE_BRANCH/NOT_CSE/UNKNOWN` — unknowns are never hidden |
| 📝 **Google Forms Detection** | `forms.gle` / `docs.google.com/forms` links auto-flagged as registration-required |
| 🖼️ **Image OCR** | Photo posters read offline via Tesseract (pytesseract) |
| 📄 **PDF/DOCX Reading** | JD text extracted locally; source file retained and downloadable |
| ⏰ **Deadline Engine** | TODAY/WITHIN_24H/TOMORROW/… buckets computed in UTC, shown in IST; reminders at 3d/24h/3h |
| 🔄 **Dedup + Timeline** | Signature + fuzzy dedup merges repeat posts into ONE drive with a full event timeline incl. deadline extensions |
| ♻️ **Lifecycle Janitor** | Hourly auto-expiry of dead drives + zombie reminder cleanup |
| 🔗 **Same-Company Merge** | JD PDFs, form links and follow-ups converge into ONE drive per recruiter — one timeline, no duplicate alerts |
| 💾 **Storage Guardian** | Live quota meter (512 MB Atlas tier), Telegram warning at 450 MB, checklist bulk-delete, 25-day auto-purge |
| ✨ **Gemini Assistant** | Opt-in chat page grounded in your live drive data — enable/disable buttons, answers only from stored facts |
| 📊 **Dashboard** | Morning briefing, urgency stats, calendar, raw message inbox, import with SSE progress |
| 🧠 **Eligibility Profile** | Your branch/batch/CGPA → per-drive ELIGIBLE / UNCLEAR / NOT_ELIGIBLE verdicts + relevance score |
| 🔐 **JWT Auth** | Single-admin login enforced on every data route |

---

## 🏗️ Architecture

### System flow

```
                 ┌─────────────────────────────────────────────┐
                 │                  TELEGRAM                   │
                 │   placement group · bot chats · exports     │
                 └──────┬─────────────────┬────────────────┬───┘
                        │ userbot         │ Bot API        │ JSON/TXT/HTML
                        │ (Telethon)      │ (forwards,     │ export files
                        │  live listener  │  /commands)    │
                        │                 │                ▼
                        │                 │        telegram_importer.py
                        │                 │        (SSE progress upload)
                        └────────┬────────┴────────┬───────┘
                                 ▼                 ▼
                    ┌──────────────────────────────────────┐
                    │       message_pipeline.py            │
                    │  content-hash dedup → persist raw →  │
                    │  classify_and_extract()              │
                    └──────────────────┬───────────────────┘
                                       ▼
              ┌───────────────────────────────────────────────┐
              │          AI LAYER — local first               │
              │  nlp_extractor.py (spaCy · dateparser · regex)│
              │  PDF/DOCX text · Tesseract OCR for posters    │
              │  Gemini Flash → Pro escalation (OPTIONAL)     │
              └───────────────────────┬───────────────────────┘
                                      ▼
   ┌──────────────── opportunity_engine.py ────────────────────────┐
   │  L1 signature dedup → L1.5 same-company merge →               │
   │  L2 RapidFuzz fuzzy match → create/update ONE drive record    │
   │  event timeline · eligibility & relevance scoring             │
   └──────────────┬───────────────────────────┬───────────────────┘
                  ▼                           ▼
   ┌────────────────────────────┐   ┌──────────────────────────────┐
   │     MongoDB (Motor async)  │   │     deadline_engine.py       │
   │  opportunities · messages  │◄─►│  EXPIRED/TODAY/24H/TOMORROW/ │
   │  events · reminders ·      │   │  WEEK/UPCOMING — computed in │
   │  app_settings              │   │  UTC, displayed in IST       │
   └─────────────┬──────────────┘   └──────────────┬───────────────┘
                 │                                 ▼
                 │              ┌──────────────────────────────────┐
                 │              │    scheduler.py (APScheduler)    │
                 │              │  reminder checks every 15 min ·  │
                 │              │  daily summary 08:00 IST ·       │
                 │              │  watchdog · janitor purge 03:15  │
                 │              └───────────────┬──────────────────┘
                 ▼                              ▼
   ┌────────────────────────────┐   ┌──────────────────────────────┐
   │   FastAPI — main.py        │   │  notification_service.py     │
   │   JWT auth on ALL routes   │   │  Telegram alerts + 🎉        │
   │   REST + SSE endpoints     │   │  shortlist pings + inline    │
   │   /api/health probe        │   │  Mark Applied / Snooze       │
   └─────────────┬──────────────┘   └──────────────────────────────┘
                 ▼
   ┌────────────────────────────┐        Hosting: MongoDB Atlas · Render
   │  React 19 + Vite dashboard │        (API) · Vercel (UI)
   │  Dashboard · Opportunities │
   │  Calendar · Messages ·     │
   │  Import · Settings · Gemini│
   └────────────────────────────┘
```

### Repository layout

```
placement-tracker/
├── backend/                  # FastAPI + Python
│   ├── main.py               # App entry, router wiring, lifespan (db/scheduler/userbot/bot)
│   ├── config.py             # pydantic-settings (env-driven)
│   ├── database.py           # Async Motor/MongoDB + indexes
│   ├── scheduler.py          # APScheduler: reminders, daily summary, watchdog, janitor
│   ├── userbot.py            # Telethon listener + media router (pdf/excel/photo)
│   ├── telegram_bot.py       # Bot API: commands, forwards, documents, photos, callbacks
│   ├── setup_session.py      # One-time Telethon session generator
│   ├── api/routes/
│   │   ├── auth.py           # JWT login/me + require_auth dependency
│   │   ├── opportunities.py  # CRUD + filters(role_class/forms_only) + briefing/calendar/messages
│   │   ├── reminders.py      # Upcoming reminders
│   │   ├── settings.py       # Eligibility profile, system config, scan trigger
│   │   └── import_.py        # Historical import (SSE streaming)
│   ├── services/
│   │   ├── ai_service.py         # Local-first + optional Gemini escalation
│   │   ├── nlp_extractor.py      # Offline extraction engine (spaCy/dateparser/regex)
│   │   ├── eligibility_service.py# Role DB + role-first classifier + profile matching
│   │   ├── excel_service.py      # Spreadsheet parse + student identity scan
│   │   ├── image_ocr.py          # Offline pytesseract OCR
│   │   ├── pdf_service.py        # PDF/DOCX/HTML/TXT text extraction + doc vault
│   │   ├── opportunity_engine.py # Dedup layers, timeline, create/update logic
│   │   ├── deadline_engine.py    # Urgency buckets + reminder times (IST-aware)
│   │   ├── reminder_service.py   # Schedule/cancel/due reminders
│   │   ├── notification_service.py # Telegram alert templates (+shortlist 🎉)
│   │   ├── telegram_importer.py  # JSON/TXT/HTML historical import
│   │   ├── lifecycle_janitor.py  # Auto-expire stale drives
│   │   ├── message_pipeline.py   # Shared ingestion path for all sources
│   │   └── pre_filter.py / watchdog.py / message_retention.py
│   └── models/               # Pydantic schemas (opportunity, message)
│
└── frontend/                 # React 19 + Vite
    └── src/
        ├── App.jsx           # Routes (public landing + protected app)
        ├── pages/Landing.jsx # Animated public landing page
        ├── pages/            # Dashboard, Opportunities(+filters), Detail,
        │                     # Applications, Calendar, Messages, Reminders,
        │                     # Import(SSE), Settings, Login
        ├── components/       # Navbar, OpportunityCard(badges), MatchScore, Timeline…
        ├── hooks/useAuth.jsx # Token context + logout
        └── api/client.js     # Axios + JWT interceptors + SSE upload
```

---

## 🚀 Quick Start (PC)

```bash
# 1. Backend
cd backend
pip install -r requirements.txt
python -m spacy download en_core_web_sm     # NLP model (one-time)
python -m spacy validate                    # optional check
# Install Tesseract OCR binary (Windows):
# https://github.com/UB-Mannheim/tesseract/wiki

# 2. Configure environment
cp .env.example .env                        # then edit with your values
# NEVER commit .env. Set STRONG credentials — defaults are placeholders.

# 3. Generate Telegram session (one-time)
python setup_session.py

# 4. Run backend
uvicorn main:app --reload                   # http://localhost:8000/docs

# 5. Frontend
cd ../frontend
npm install
npm run dev                                 # http://localhost:5173
```

### Required `.env` values

| Variable | Notes |
|----------|-------|
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` / `ADMIN_SECURITY_CODE` | Dashboard login — choose strong values |
| `JWT_SECRET` | Long random string (`openssl rand -hex 32`) |
| `CORS_ORIGINS` | JSON list of allowed dashboard origins (add your deployed URL in prod) |
| `MONGODB_URI` / `MONGODB_DB` | Local or Atlas URI |
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` / `TELEGRAM_SESSION_STRING` | my.telegram.org + setup_session.py |
| `PLACEMENT_GROUP_ID` | Group the userbot listens to |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | @BotFather token + your user id (optional but recommended) |
| `STUDENT_NAME` / `STUDENT_USN` | Hardcoded shortlist-matching identity |
| `GEMINI_API_KEY` / `GEMINI_FLASH_MODEL` / `GEMINI_PRO_MODEL` | Optional. Extraction uses local NLP first; with a key present, Gemini enhances extraction, and the chat page unlocks after its own Enable press |
| `DATA_RETENTION_DAYS` | Auto-delete messages + dead drives older than this (default `25`) |
| `STORAGE_LIMIT_MB` / `STORAGE_WARN_MB` | Quota meter ceiling and Telegram warning line (default `512` / `450`) |

---

## 🌐 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login (credentials + security code) → JWT |
| GET | `/api/auth/me` | Current user |
| GET | `/api/opportunities` | List + filters: status/category/eligibility/**role_class**/**forms_only**/urgency/search/days/cse_only |
| GET | `/api/opportunities/stats` | Dashboard counts by urgency |
| GET | `/api/opportunities/meta/briefing` | Morning briefing |
| GET | `/api/opportunities/meta/calendar` | Calendar events |
| PATCH | `/api/opportunities/{id}/status` | Update status |
| GET | `/api/opportunities/messages` | Raw message inbox (+attachment download) |
| GET | `/api/reminders` | Upcoming reminders |
| POST | `/api/import/upload` | Historical export (SSE progress) |
| GET/POST | `/api/storage` · `/api/storage/*/delete-bulk` · `/api/storage/purge` | Quota meter, bulk delete, purge |
| GET | `/api/gemini/status` | Gemini chat toggle state + key presence |
| POST | `/api/gemini/toggle` | Enable/disable the opt-in chat |
| POST | `/api/gemini/chat` | Grounded Q&A over stored drives (429 = credits exhausted) |
| GET | `/api/settings/profile` · `/system_config` · `/system` | Settings & health |
| GET | `/api/health` | Public health probe |

All data routes require `Authorization: Bearer <JWT>`.

> 🔒 **Security posture:** credentials live only in `.env` (login is
> fail-closed without them), Swagger/ReDoc/openapi.json are hidden unless
> `DOCS_ENABLED=true`, and security headers are set on every response.
> If notifications show `chat not found`, open your bot in Telegram and
> press **START** once.

### ⚠️ Run exactly ONE backend instance

Telegram allows only one `getUpdates` poller per bot token. If you see

```
Conflict: terminated by other getUpdates request; make sure that only one
bot instance is running
```

an old uvicorn/reload worker survived (this happens after Ctrl+C under
`--reload`). Kill the strays and restart:

```powershell
# Windows — find who holds ports 8000/8001, then stop stale python processes
Get-NetTCPConnection -State Listen | ? { $_.LocalPort -in 8000,8001 }
Stop-Process -Id <stale_pid> -Force
```

The frontend dev server expects the API on **port 8000**
(`frontend/src/api/client.js`); override with `VITE_API_URL` if needed.

### 🚀 Deploying (production checklist)

1. **Backend**: host on a persistent VM/container (Render, Railway, Fly.io,
   or a home server) — the Telethon userbot must stay running; serverless
   platforms will kill the long-lived Telegram session.
2. **Frontend**: `npm run build` then serve `dist/` from Vercel/Netlify/
   Nginx. Set `VITE_API_URL` to your backend URL **at build time**.
3. **CORS**: set `CORS_ORIGINS='["https://your-frontend-domain"]'` in the
   backend environment — localhost origins are only defaults.
4. **MongoDB**: use Atlas (or self-host); keep `MONGODB_URI` secret.
5. **Secrets**: strong `ADMIN_PASSWORD` + `JWT_SECRET`; never commit `.env`;
   leave `DOCS_ENABLED=false`.
6. **Telegram**: run `setup_session.py` once on the deploy machine, press
   START on the bot from your account, and confirm the startup ping arrives.

## 💬 Telegram Bot Commands

`/start /help /jobs /today /urgent /deadlines /applied /pending /expired /stats /search <company>` — plus inline **Mark Applied / Remind Later / Ignore** buttons on every alert.

---

## 🛠️ Tech Stack

**Backend**: FastAPI, Motor, Telethon, python-telegram-bot, APScheduler,
spaCy + dateparser, RapidFuzz, openpyxl, PyMuPDF/pdfplumber, pytesseract,
PyJWT *(Google Gemini optional)*
**Frontend**: React 19, Vite, React Router, Axios, Lucide, react-hot-toast
**Database**: MongoDB
