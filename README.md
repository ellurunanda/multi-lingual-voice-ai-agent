# 🎙️ Real-Time Multilingual Voice AI Agent

A production-ready, real-time voice AI agent for clinical appointment booking supporting English, Hindi, Tamil, and Telugu — built with FastAPI, OpenAI Whisper/GPT-4o/TTS, React, PostgreSQL, and Redis.

**Live Demo:** https://voiceai-frontend-4khc.onrender.com  
**Backend API:** https://voiceai-backend-9ex7.onrender.com/docs

---

## 📋 Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Setup Instructions](#setup-instructions)
- [Memory Design](#memory-design)
- [Latency Breakdown](#latency-breakdown)
- [Trade-offs](#trade-offs)
- [Known Limitations](#known-limitations)

---

## ✨ Features

- 🎤 Real-time voice input via WebSocket (sub-450ms pipeline)
- 🌐 Multilingual: English, Hindi, Tamil, Telugu (auto-detected)
- 🤖 GPT-4o powered appointment booking agent
- 📅 Appointment scheduling, rescheduling, cancellation
- 📢 Automated reminder campaigns via scheduler
- 🏥 Doctor/patient management REST API
- 💾 Persistent memory across sessions (PostgreSQL)
- ⚡ Session memory with Redis fallback to in-memory

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React/Vite)                     │
│  VoiceButton → WebSocket Client → ConversationPanel             │
└──────────────────────────┬──────────────────────────────────────┘
                           │ WebSocket /ws/voice/{session_id}
┌──────────────────────────▼──────────────────────────────────────┐
│                     BACKEND (FastAPI)                            │
│                                                                  │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌───────────┐  │
│  │  STT    │───▶│  Agent   │───▶│   TTS    │───▶│ WebSocket │  │
│  │Whisper-1│    │  GPT-4o  │    │  tts-1   │    │ Response  │  │
│  └─────────┘    └────┬─────┘    └──────────┘    └───────────┘  │
│                      │                                           │
│              ┌───────▼────────┐                                  │
│              │     Tools      │                                  │
│              │ • book_appt    │                                  │
│              │ • cancel_appt  │                                  │
│              │ • list_doctors │                                  │
│              │ • get_slots    │                                  │
│              └───────┬────────┘                                  │
│                      │                                           │
│         ┌────────────▼──────────────┐                           │
│         │         Memory            │                           │
│         │  Session (Redis/fallback) │                           │
│         │  Persistent (PostgreSQL)  │                           │
│         └───────────────────────────┘                           │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Campaign Scheduler (APScheduler)             │   │
│  │  • Polls DB every 60s for upcoming appointments           │   │
│  │  • Sends reminders 24h before appointment                 │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
         │                          │
┌────────▼────────┐      ┌──────────▼──────────┐
│   PostgreSQL    │      │       Redis          │
│  • patients     │      │  • session state     │
│  • doctors      │      │  • conversation ctx  │
│  • appointments │      │  • language prefs    │
│  • campaigns    │      └─────────────────────┘
└─────────────────┘
```

### Component Breakdown

| Component | Technology | Purpose |
|-----------|-----------|---------|
| STT | OpenAI Whisper-1 | Converts voice audio to text with language detection |
| LLM Agent | GPT-4o + function calling | Understands intent, manages conversation, calls tools |
| TTS | OpenAI tts-1 (alloy voice) | Converts agent response text back to speech |
| Memory (session) | Redis / in-memory fallback | Stores active conversation context, language preference |
| Memory (persistent) | PostgreSQL via SQLAlchemy | Stores appointments, patients, doctors, campaign history |
| Tools | Python functions | book_appointment, cancel_appointment, list_doctors, get_available_slots, get_patient_appointments |
| Scheduler | APScheduler | Background job that sends appointment reminders |
| Transport | WebSocket (FastAPI) | Bidirectional real-time audio/text streaming |

---

## 🚀 Setup Instructions

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose (for local full-stack)
- OpenAI API key

### Option A — Docker Compose (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/ellurunanda/multi-lingual-voice-ai-agent.git
cd multi-lingual-voice-ai-agent

# 2. Copy and configure environment
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...

# 3. Start all services
docker-compose up --build

# 4. Access the app
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/docs
```

### Option B — Manual Local Setup

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp ../.env.example .env
# Edit .env — set OPENAI_API_KEY, DATABASE_URL, REDIS_URL

# Initialize database
python ../create_tables.py

# Start backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env — set VITE_API_URL=http://localhost:8000

# Start frontend
npm run dev
# Open http://localhost:5173
```

### Environment Variables

#### Backend (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | ✅ | OpenAI API key (sk-...) |
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `REDIS_URL` | ⚠️ Optional | Redis URL (falls back to in-memory) |
| `OPENAI_MODEL` | No | Default: `gpt-4o` |
| `OPENAI_WHISPER_MODEL` | No | Default: `whisper-1` |
| `OPENAI_TTS_MODEL` | No | Default: `tts-1` |
| `CORS_ORIGINS` | No | Comma-separated allowed origins |
| `SUPPORTED_LANGUAGES` | No | Default: `en,hi,ta,te` |

#### Frontend (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_URL` | ✅ | Backend HTTP URL |
| `VITE_WS_URL` | ✅ | Backend WebSocket URL (ws:// or wss://) |

### Database Schema

```bash
# Run migrations manually
python create_tables.py

# Or via Docker
docker-compose exec backend python create_tables.py
```

---

## 🧠 Memory Design

The system uses a **two-tier memory architecture**:

### Tier 1 — Session Memory (Short-term)

- **Storage:** Redis (primary) → Python dict (fallback)
- **TTL:** 1 hour per session
- **Contents:**
  - Active conversation history (last N turns)
  - Detected language preference
  - Current patient context
  - Partial booking state (intent, collected slots)
- **Key format:** `session:{session_id}:*`

### Tier 2 — Persistent Memory (Long-term)

- **Storage:** PostgreSQL via SQLAlchemy async
- **Contents:**
  - Patient profiles and history
  - All appointments (past + future)
  - Doctor availability
  - Campaign records and reminder logs
- **Access:** Via tool calls from the agent (not direct LLM access)

### Memory Flow

```
User speaks → STT → Agent reads session memory (context)
           → Agent calls tools → Tools read/write PostgreSQL
           → Agent updates session memory (new turn)
           → TTS → User hears response
```

The agent never directly queries the database — it uses **structured tool calls** which act as a controlled interface to persistent storage. This prevents prompt injection via database content and keeps the LLM focused on conversation logic.

---

## ⚡ Latency Breakdown

Target: **< 450ms end-to-end** (voice-in to voice-out)

| Stage | Target | Typical | Notes |
|-------|--------|---------|-------|
| Audio capture & encode | ~20ms | ~20ms | Browser MediaRecorder |
| Network (client → server) | ~30ms | ~30ms | WebSocket, depends on region |
| STT (Whisper-1) | 120ms | 100–200ms | OpenAI API, audio length dependent |
| LLM (GPT-4o) | 200ms | 150–300ms | Function calling adds ~50ms |
| TTS (tts-1) | 100ms | 80–150ms | OpenAI API, text length dependent |
| Network (server → client) | ~30ms | ~30ms | Audio streaming |
| **Total** | **450ms** | **380–700ms** | Varies with network & load |

### Optimization Strategies Implemented

- **Streaming TTS:** Response audio begins generating as soon as LLM produces first tokens
- **Parallel processing:** Language detection runs concurrently with STT
- **Connection pooling:** SQLAlchemy async engine with connection pool
- **Session caching:** Redis prevents repeated DB lookups for active sessions
- **Warm startup:** Services initialized at app startup, not per-request

---

## ⚖️ Trade-offs

### 1. OpenAI APIs vs Self-hosted Models
- **Chose:** OpenAI Whisper + GPT-4o + TTS
- **Pro:** Best accuracy, no GPU infrastructure, fast iteration
- **Con:** Per-request cost, latency dependent on OpenAI servers, data leaves your infrastructure

### 2. Redis vs In-memory Session Store
- **Chose:** Redis with in-memory fallback
- **Pro:** Survives server restarts, supports horizontal scaling
- **Con:** Additional infrastructure dependency; fallback loses sessions on restart

### 3. WebSocket vs HTTP Polling
- **Chose:** WebSocket for real-time bidirectional streaming
- **Pro:** Low latency, server can push audio chunks as they're generated
- **Con:** More complex connection management, requires sticky sessions for multi-instance

### 4. Function Calling vs RAG
- **Chose:** GPT-4o function calling for tool use
- **Pro:** Structured, type-safe tool invocation; no hallucinated SQL
- **Con:** Limited to predefined tools; can't answer ad-hoc queries outside tool scope

### 5. Single Worker vs Multi-worker
- **Chose:** 2 uvicorn workers in production
- **Pro:** Better CPU utilization
- **Con:** In-memory session fallback is not shared across workers (Redis solves this)

---

## ⚠️ Known Limitations

1. **Free tier cold starts:** Render free tier spins down after 15 min inactivity — first request takes 30–50 seconds to wake up.

2. **Redis fallback is not persistent:** If `REDIS_URL` is not set, session memory uses an in-memory dict that is lost on server restart or between workers.

3. **Audio format support:** Currently optimized for WebM (Chrome/Firefox). Safari sends different formats — may require additional ffmpeg conversion handling.

4. **No authentication:** The API has no user authentication. In production, add JWT/OAuth2 before exposing publicly.

5. **Single language per session:** Language is detected from the first utterance and stored for the session. Mid-session language switching works but may cause brief confusion in the agent's context.

6. **Campaign scheduler is in-process:** The APScheduler runs inside the FastAPI process. For production scale, this should be a separate worker (Celery + Redis).

7. **No audio chunking/streaming:** The full audio clip is sent at once rather than streaming chunks. This adds latency for longer utterances (>5 seconds).

8. **OpenAI rate limits:** On free/low-tier OpenAI plans, concurrent users may hit rate limits causing 429 errors.

9. **Database migrations:** No Alembic migrations are set up — `create_tables.py` uses `CREATE TABLE IF NOT EXISTS`. Schema changes require manual migration.

10. **No HTTPS enforcement on WebSocket:** In local development, `ws://` is used. Production uses `wss://` via Render's TLS termination.

---

## 📁 Project Structure

```
├── backend/
│   ├── main.py                    # FastAPI app, WebSocket handler
│   ├── config.py                  # Pydantic settings
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── agent/
│   │   ├── reasoning/agent_core.py    # GPT-4o agent with function calling
│   │   ├── tools/appointment_tools.py # Tool definitions & implementations
│   │   └── prompt/system_prompts.py   # System prompt templates
│   ├── api/routes/
│   │   ├── appointments.py        # REST CRUD for appointments
│   │   ├── patients.py            # REST CRUD for patients
│   │   ├── doctors.py             # REST CRUD for doctors
│   │   ├── campaigns.py           # Campaign management
│   │   └── health.py              # Health check endpoint
│   ├── memory/
│   │   ├── session_memory.py      # Redis session store
│   │   └── persistent_memory.py   # PostgreSQL long-term memory
│   ├── models/
│   │   ├── database.py            # SQLAlchemy models
│   │   └── db_connection.py       # Async engine & session factory
│   ├── scheduler/
│   │   ├── appointment_engine.py  # Appointment booking logic
│   │   └── campaign_scheduler.py  # APScheduler reminder jobs
│   └── services/
│       ├── speech_to_text.py      # Whisper STT service
│       ├── text_to_speech.py      # OpenAI TTS service
│       └── language_detection.py  # langdetect wrapper
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── VoiceAgentPage.jsx     # Main voice interface
│   │   │   ├── AppointmentsPage.jsx   # Appointment management UI
│   │   │   └── DashboardPage.jsx      # Overview dashboard
│   │   ├── components/
│   │   │   ├── VoiceButton.jsx        # Mic button with recording state
│   │   │   ├── ConversationPanel.jsx  # Chat transcript display
│   │   │   └── LanguageSelector.jsx   # Language switcher
│   │   ├── hooks/useVoiceAgent.js     # WebSocket + audio recording hook
│   │   └── services/
│   │       ├── api.js                 # REST API client
│   │       └── websocket.js           # WebSocket client
│   └── Dockerfile
├── docker-compose.yml
├── render.yaml                    # Render.com deployment blueprint
├── create_tables.py               # DB initialization script
└── README.md
```

---

## 🛠️ API Reference

### WebSocket

```
ws://localhost:8000/ws/voice/{session_id}?language=en&patient_id=optional
```

**Client → Server messages:**
```json
{"type": "audio", "data": "<base64_webm>", "format": "webm"}
{"type": "text", "data": "Book an appointment with Dr. Smith"}
{"type": "end_session"}
{"type": "ping"}
```

**Server → Client messages:**
```json
{"type": "session_started", "session_id": "...", "language": "en"}
{"type": "transcript", "text": "...", "language": "en", "stt_latency_ms": 120}
{"type": "response_text", "text": "...", "language": "en"}
{"type": "audio_response", "data": "<base64_mp3>", "format": "mp3"}
{"type": "latency", "metrics": {"stt_ms": 120, "llm_ms": 200, "tts_ms": 100, "total_ms": 420}}
{"type": "error", "message": "..."}
```

### REST API

Full interactive docs available at `/docs` (Swagger UI).

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/appointments` | List appointments |
| POST | `/api/appointments` | Create appointment |
| PUT | `/api/appointments/{id}` | Update appointment |
| DELETE | `/api/appointments/{id}` | Cancel appointment |
| GET | `/api/patients` | List patients |
| POST | `/api/patients` | Create patient |
| GET | `/api/doctors` | List doctors |
| GET | `/api/campaigns` | List campaigns |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.