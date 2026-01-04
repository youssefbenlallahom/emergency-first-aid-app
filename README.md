
# Emergency First Aid App (Monkedh)

Emergency-first-aid assistant for the Tunisian context: a Next.js web UI + a Python/FastAPI backend powered by CrewAI.

This repository is a prototype / research project. In a real emergency, call your local emergency number (Tunisia: SAMU **190**, Protection Civile **198**, Police **197**).

## What’s in this repo

- **Frontend**: Next.js app in `frontend/`
  - Pages: chat, voice call, CPR camera, video report, realtime analysis.
- **Main assistant backend**: FastAPI + CrewAI in `backend/assistant/`
  - REST API for chat + history
  - Optional voice support (WebRTC token endpoint + WebSocket voice endpoint)
  - Video report generation endpoints (upload a video, generate report, list reports)
  - Serves emergency guide images from `/images`.
- **CPR camera backend**: Flask + Socket.IO in `backend/cpr_assistant/`
  - Receives frames from the browser, runs YOLO-based CPR keypoints/metrics, streams feedback back.
- **Realtime video analysis backend** (separate): Docker Compose in `backend/realtime_vlm/`
  - Powers the `/realtime-analysis` UI.

## Features that exist (based on current code)

- **Text chat** (web + API): `POST /api/chat` routes messages through a single CrewAI agent and stores recent history in Redis.
- **RAG for first-aid protocols**: a Qdrant collection (`first_aid_manual`) queried via an Ollama embedding model.
- **Visual guides**: the agent can return a “📷 GUIDE VISUEL …” path; the backend serves the images and the frontend renders them.
- **Voice call (web)**: browser ↔ Azure Realtime over WebRTC; the backend is used to mint an ephemeral token and to answer function calls by calling the assistant chat endpoint.
- **Voice mode (CLI)**: optional GPT-Realtime STT/TTS via WebSocket (requires `pyaudio` + `websockets`).
- **Video report (web)**: upload a video, backend processes frames/audio and generates a report you can view/download; optional email sending via SMTP env vars.
- **CPR camera guide (web)**: live CPR feedback via Socket.IO to the CPR backend.

## Quickstart (local)

This is the minimal setup to run the web UI + the assistant API.

### 1) Start the assistant API (FastAPI)

```powershell
cd backend/assistant

python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install and register the package (recommended)
pip install -e .

# Start API on http://localhost:8000
python -m monkedh.api
```

### 2) Start the frontend (Next.js)

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Configuration

### Backend env file

The assistant API loads environment variables from `backend/assistant/.env`.

Create `backend/assistant/.env`:

```env
# Azure OpenAI (CrewAI LLM)
AZURE_API_KEY=...
AZURE_API_BASE=https://<your-resource>.openai.azure.com/
AZURE_API_VERSION=...
model=azure/<your-deployment-name>

# Redis (conversation history)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# Optional web search
SERPER_API_KEY=...

# Azure Realtime (web voice + CLI voice)
AZURE_REALTIME_API_KEY=...
AZURE_REALTIME_API_BASE=...

# Optional: email sending for video reports
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=...
SENDER_PASSWORD=...
```

### Frontend env file

The frontend reads env vars from `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_BACKEND_URL=http://localhost:5000
NEXT_PUBLIC_REALTIME_VLM_URL=http://localhost:8000
```

Notes:

- `NEXT_PUBLIC_API_URL` points to the **assistant FastAPI** server.
- `NEXT_PUBLIC_BACKEND_URL` points to the **CPR Flask/Socket.IO** server.
- `NEXT_PUBLIC_REALTIME_VLM_URL` points to the **realtime_vlm** orchestrator.
- The assistant API and `realtime_vlm` orchestrator both default to port **8000** → you must run them on different ports if you want both at the same time.

## Running optional components

### CPR camera backend

```powershell
cd backend/cpr_assistant

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
python api_server.py
```

Default URL: `http://localhost:5000`.

### Realtime video analysis backend (Docker)

```powershell
cd backend/realtime_vlm
docker compose up --build
```

Default URL: `http://localhost:8000` (see `docker-compose.yml`).

## RAG / Qdrant / Ollama notes

- The RAG pipeline expects an Ollama server at `http://localhost:11434`.
- A one-time vectorization script exists at `backend/assistant/src/monkedh/tools/rag/vectorize_document.py`.
- Current Qdrant connection details are referenced in code. For production, move Qdrant/Redis credentials to environment variables and rotate any leaked keys.

## API overview (assistant backend)

- `GET /api/health`
- `POST /api/chat`
- `GET /api/history/{channel_id}` / `DELETE /api/history/{channel_id}`
- `POST /api/realtime/token` (ephemeral token for WebRTC voice)
- `WS /api/voice/{session_id}` (WebSocket voice mode)
- `POST /api/video/analyze` + `GET /api/video/reports` + `GET /api/video/reports/{id}`

## Tech stack (as used in this repo)

- **Frontend**: Next.js (App Router), React, TypeScript, Tailwind, shadcn/ui.
- **Assistant backend**: FastAPI + CrewAI, Redis for short-term memory, Qdrant + Ollama embeddings for RAG.
- **CPR backend**: Flask + Socket.IO, OpenCV, Ultralytics YOLO.
- **Realtime analysis backend**: Dockerized microservices (see `backend/realtime_vlm`).

## License

No license file is included in this repository yet.
