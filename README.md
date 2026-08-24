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
| 📊 **Dashboard** | Morning briefing, urgency stats, calendar, raw message inbox, import with SSE progress |
| 🧠 **Eligibility Profile** | Your branch/batch/CGPA → per-drive ELIGIBLE / UNCLEAR / NOT_ELIGIBLE verdicts + relevance score |
| 🔐 **JWT Auth** | Single-admin login enforced on every data route |

---

## 🏗️ Architecture

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

Full step-by-step guide (PC + mobile + free hosting deployment): see
**[`strps.txt`](strps.txt)**.

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
| `GEMINI_ENABLED` / `GEMINI_API_KEY` | Optional. Leave false to run fully offline |

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
| GET | `/api/reminders` | Upcoming reminders |
| POST | `/api/import/upload` | Historical export (SSE progress) |
| GET | `/api/settings/profile` · `/system_config` · `/system` | Settings & health |
| GET | `/api/health` | Public health probe |

All data routes require `Authorization: Bearer <JWT>`.

## 💬 Telegram Bot Commands

`/start /help /jobs /today /urgent /deadlines /applied /pending /expired /stats /search <company>` — plus inline **Mark Applied / Remind Later / Ignore** buttons on every alert.

---

## 🛠️ Tech Stack

**Backend**: FastAPI, Motor, Telethon, python-telegram-bot, APScheduler,
spaCy + dateparser, RapidFuzz, openpyxl, PyMuPDF/pdfplumber, pytesseract,
PyJWT *(Google Gemini optional)*
**Frontend**: React 19, Vite, React Router, Axios, Lucide, react-hot-toast
**Database**: MongoDB
