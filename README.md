# VoiceDesk

Real-time AI voice receptionist. Answers calls, books appointments, and remembers returning callers. Ships as a single Docker container and can be configured for any business without touching code.

---

## How it works

A caller speaks naturally. VoiceDesk transcribes in real time, detects intent, answers from a business knowledge base or runs a booking flow — then responds with streamed audio. End-to-end latency under 2.5 seconds.

```
Caller (Browser / Phone)
         │
         │  WebSocket (/ws)
         ▼
    FastAPI Server
  ┌──────┬────────┬──────┐
  │ STT  │  LLM   │ TTS  │
  └──┬───┴────┬───┴──┬───┘
     │        │      │
  Voice    OpenAI  Voice
  Provider         Provider
     │                │
  Supabase        Cal.com
```

---

## Features

- Continuous real-time speech recognition with voice activity detection
- Intent routing: general Q&A or a 4-phase deterministic booking flow
- Cal.com integration — fetches live availability and creates confirmed bookings
- Returning caller memory via Supabase — call history injected into context per session
- Swappable voice providers controlled by environment variables
- Single-file frontend, no build step

---

## Quick start

```bash
cp .env.example .env
# Fill in your API keys
docker compose up --build
```

Open `http://localhost:8000` and click **Start Call**.

---

## Configuration

All business settings are environment variables — no code changes needed.

```env
# Required
OPENAI_API_KEY=
ELEVENLABS_API_KEY=
SUPABASE_URL=
SUPABASE_ANON_KEY=
CAL_COM_API_KEY=
CAL_COM_EVENT_TYPE_ID=

# Business identity
COMPANY_NAME=Your Business Name
RECEPTIONIST_NAME=Sarah
CUSTOM_INSTRUCTIONS=We are a dental clinic in Melbourne...
CAL_COM_TIMEZONE=Australia/Melbourne

# Voice providers  (elevenlabs | valsea)
STT_PROVIDER=elevenlabs
TTS_PROVIDER=elevenlabs
```

---

## Project structure

```
app/
├── main.py          # WebSocket handler, turn logic, booking state machine
├── config.py        # All env vars in one place
├── session.py       # Per-call state
├── prompt.py        # System prompt builder
├── memory.py        # Supabase read/write
├── database.py      # Startup connection check
└── services/
    ├── stt.py       # STT provider abstraction
    ├── tts.py       # TTS provider abstraction
    ├── llm.py       # OpenAI calls
    └── cal.py       # Cal.com v2 REST
static/
└── index.html       # Entire frontend — single file
```

---

## Deployment

CI validates the Docker build on every push to `main` via GitHub Actions.

```bash
# Local
docker compose up --build

# Production
docker compose up -d
```

---

## Customising for a new business

Update four env vars and redeploy:

```env
COMPANY_NAME=Melbourne Physio Centre
RECEPTIONIST_NAME=Emma
CUSTOM_INSTRUCTIONS=We are a physiotherapy clinic...
CAL_COM_EVENT_TYPE_ID=<your event type id>
```
