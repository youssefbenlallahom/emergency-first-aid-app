# Monkedh Assistant (backend/assistant)

Python backend for the emergency first-aid assistant.

What it provides (in the current codebase):

- **CrewAI single-agent triage + guidance** (Tunisia-focused prompts)
- **FastAPI API** for chat + conversation history
- **Static image hosting** for emergency visual guides (`/images`)
- **Voice support hooks** (ephemeral token endpoint for WebRTC + a WebSocket voice endpoint)
- **Video report endpoints** (upload a video, generate a report, list/view reports)

## Requirements

- Python 3.10–3.12
- Redis (recommended for history; API can still run without it)
- Ollama running locally for embeddings (default: `http://localhost:11434`)
- Qdrant (local or cloud)
- Azure OpenAI credentials for the LLM

## Install

```powershell
cd backend/assistant

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -e .
```

## Configure

Create `backend/assistant/.env` (the API loads this file on startup):

```env
# Azure OpenAI (CrewAI)
AZURE_API_KEY=...
AZURE_API_BASE=https://<your-resource>.openai.azure.com/
AZURE_API_VERSION=...
model=azure/<your-deployment-name>

# Redis (history)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# Optional web search
SERPER_API_KEY=...

# Azure Realtime (voice)
AZURE_REALTIME_API_KEY=...
AZURE_REALTIME_API_BASE=...

# Optional: email for video reports
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=...
SENDER_PASSWORD=...
```

## Run

### Start the FastAPI server

```powershell
python -m monkedh.api
```

Default URL: `http://localhost:8000`.

### Run the CLI assistant

```powershell
python -m monkedh.main

# Optional voice mode (requires pyaudio + websockets + Azure Realtime env vars)
python -m monkedh.main --voice
```

## API endpoints

- `GET /api/health`
- `POST /api/chat`
- `GET /api/history/{channel_id}` / `DELETE /api/history/{channel_id}`
- `POST /api/realtime/token`
- `WS /api/voice/{session_id}`
- `POST /api/video/analyze`
- `GET /api/video/reports` / `GET /api/video/reports/{report_id}`

## RAG / ingestion

- A one-time script exists at `src/monkedh/tools/rag/vectorize_document.py`.
- Qdrant/Ollama configuration is referenced from code; for production, move credentials to environment variables and rotate any leaked keys.

## License

No license file is included in this repository yet.
