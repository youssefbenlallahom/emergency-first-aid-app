"""
FastAPI REST API for the Emergency First Aid Assistant
Provides endpoints for chat, conversation history, and health checks
"""
import os
import uuid
import json
import base64
import asyncio
import struct
import logging
from typing import Optional, List, Union
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

# Load .env from the assistant directory before other imports
# api.py -> monkedh -> src -> assistant (3 parents)
import dotenv
env_path = Path(__file__).parent.parent.parent / ".env"
dotenv.load_dotenv(env_path)

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn
import tempfile
import shutil
import json

from monkedh.crew import Monkedh
from monkedh.tools.redis_storage import redis_memory

# Video Report Module
try:
    from monkedh.tools.video_report import (
        VideoReportCrew,
        extract_frames,
        get_video_info,
        analyze_video_audio,
        generate_report,
        markdown_to_html,
        EmailSender
    )
    VIDEO_REPORT_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Video report module not available: {e}")
    VIDEO_REPORT_AVAILABLE = False

# Path to emergency images
EMERGENCY_IMAGES_PATH = Path(__file__).parent / "tools" / "image_suggestion" / "emergency_image_db"

# Path to video report output
VIDEO_REPORT_OUTPUT_PATH = Path(__file__).parent / "tools" / "video_report" / "output"
VIDEO_REPORT_FRAMES_PATH = VIDEO_REPORT_OUTPUT_PATH / "frames"
VIDEO_REPORT_REPORTS_PATH = VIDEO_REPORT_OUTPUT_PATH / "reports"

# Ensure video report directories exist
VIDEO_REPORT_FRAMES_PATH.mkdir(parents=True, exist_ok=True)
VIDEO_REPORT_REPORTS_PATH.mkdir(parents=True, exist_ok=True)


# ============================================
# Pydantic Models for Request/Response
# ============================================

class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str = Field(..., min_length=1, description="User message/question")
    channel_id: Optional[str] = Field(default=None, description="Channel ID for conversation context")
    user_id: Optional[str] = Field(default=None, description="User ID")
    username: Optional[str] = Field(default="Utilisateur", description="Display name")


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    response: str = Field(..., description="AI assistant response")
    channel_id: str = Field(..., description="Channel ID used for this conversation")
    timestamp: str = Field(..., description="Response timestamp")


class ConversationPair(BaseModel):
    """Model for a single conversation pair"""
    user_query: str
    bot_response: str
    username: str
    timestamp: str
    user_id: str


class ConversationHistoryResponse(BaseModel):
    """Response model for conversation history endpoint"""
    channel_id: str
    conversations: List[ConversationPair]
    total_count: int


class HealthResponse(BaseModel):
    """Response model for health check endpoint"""
    status: str
    redis_connected: bool
    timestamp: str


class ClearHistoryResponse(BaseModel):
    """Response model for clear history endpoint"""
    success: bool
    message: str


# Video Report Models
class VideoAnalysisResponse(BaseModel):
    """Response model for video analysis endpoint"""
    report_id: str
    status: str
    message: str
    video_info: Optional[dict] = None


class VideoReportItem(BaseModel):
    """Model for a video report list item"""
    id: str
    title: str
    date: str
    status: str
    thumbnail: Optional[str] = None
    summary: Optional[str] = None


class VideoReportListResponse(BaseModel):
    """Response model for video reports list endpoint"""
    reports: List[VideoReportItem]
    total_count: int


class VideoReportDetailResponse(BaseModel):
    """Response model for video report detail endpoint"""
    id: str
    title: str
    date: str
    status: str
    content_html: str
    content_markdown: str
    video_info: Optional[dict] = None
    frame_analyses: Optional[List[dict]] = None
    audio_analysis: Optional[dict] = None


class EmailReportRequest(BaseModel):
    """Request model for emailing a report"""
    email: str
    subject: Optional[str] = None


# Video analysis tasks storage (in-memory for now, can be moved to Redis)
video_analysis_tasks: dict = {}


# ============================================
# Global State
# ============================================

# CrewAI instance - initialized once
crew_factory: Optional[Monkedh] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources"""
    global crew_factory
    print("🚀 Initializing Emergency First Aid Assistant API...")
    crew_factory = Monkedh()
    print("✅ CrewAI Medical Assistant initialized")
    yield
    print("👋 Shutting down API...")


# ============================================
# FastAPI Application
# ============================================

app = FastAPI(
    title="Emergency First Aid Assistant API",
    description="AI-powered medical emergency assistant using CrewAI",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://192.168.1.59:3000",
        "http://172.16.8.78:3000",
        # Add your production domains here
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for emergency images
if EMERGENCY_IMAGES_PATH.exists():
    app.mount("/images", StaticFiles(directory=str(EMERGENCY_IMAGES_PATH)), name="emergency_images")
    print(f"📸 Emergency images mounted from: {EMERGENCY_IMAGES_PATH}")


# ============================================
# Helper Functions
# ============================================

def process_question(channel_id: str, user_id: str, username: str, question: str) -> str:
    """Process a question through the CrewAI medical agents."""
    global crew_factory
    
    if crew_factory is None:
        crew_factory = Monkedh()
    
    # Get conversation history for context
    conversation_history = redis_memory.get_conversation_pairs(
        channel_id=channel_id,
        limit=10
    )
    conversation_context = redis_memory.build_conversation_context(conversation_history)
    
    inputs = {
        "question": question,
        "conversation_history": conversation_context if conversation_context else "Aucun historique précédent. C'est le début de la conversation."
    }
    
    try:
        crew = crew_factory.crew()
        result = crew.kickoff(inputs=inputs)
        output = getattr(result, "raw", str(result))
        
        # Store conversation pair
        redis_memory.store_conversation_pair(
            channel_id=channel_id,
            user_id=user_id,
            user_query=question,
            bot_response=output,
            username=username
        )
        
        return output
        
    except Exception as exc:
        error_msg = f"Une erreur est survenue lors du traitement: {str(exc)}"
        print(f"❌ Error processing question: {exc}")
        return error_msg


# ============================================
# API Endpoints
# ============================================

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API information"""
    return {
        "name": "Emergency First Aid Assistant API",
        "version": "1.0.0",
        "description": "AI-powered medical emergency assistant",
        "endpoints": {
            "POST /api/chat": "Send a message to the AI assistant",
            "GET /api/history/{channel_id}": "Get conversation history",
            "DELETE /api/history/{channel_id}": "Clear conversation history",
            "GET /api/health": "Health check",
            "WS /api/voice/{session_id}": "WebSocket for voice communication",
        }
    }


@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint"""
    redis_connected = redis_memory.redis_client is not None
    if redis_connected:
        try:
            redis_memory.redis_client.ping()
        except Exception:
            redis_connected = False
    
    return HealthResponse(
        status="healthy" if redis_connected else "degraded",
        redis_connected=redis_connected,
        timestamp=datetime.now().isoformat()
    )


@app.post("/api/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Send a message to the AI medical assistant.
    
    The assistant will:
    - Detect emergencies and provide immediate guidance
    - Use medical protocols and images when relevant
    - Maintain conversation context across messages
    """
    # Generate IDs if not provided
    channel_id = request.channel_id or f"web_channel_{uuid.uuid4().hex[:8]}"
    user_id = request.user_id or str(uuid.uuid4())
    username = request.username or "Utilisateur"
    
    try:
        response = process_question(
            channel_id=channel_id,
            user_id=user_id,
            username=username,
            question=request.message
        )
        
        return ChatResponse(
            response=response,
            channel_id=channel_id,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        print(f"❌ Error in chat endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du traitement de votre message: {str(e)}"
        )


@app.get("/api/history/{channel_id}", response_model=ConversationHistoryResponse, tags=["History"])
async def get_history(channel_id: str, limit: int = 10):
    """
    Get conversation history for a channel.
    
    Args:
        channel_id: The channel ID to get history for
        limit: Maximum number of conversation pairs to return (default: 10)
    """
    try:
        conversations = redis_memory.get_conversation_pairs(
            channel_id=channel_id,
            limit=limit
        )
        
        conversation_pairs = [
            ConversationPair(
                user_query=conv.get("user_query", ""),
                bot_response=conv.get("bot_response", ""),
                username=conv.get("username", "Unknown"),
                timestamp=conv.get("timestamp", ""),
                user_id=conv.get("user_id", "")
            )
            for conv in conversations
        ]
        
        return ConversationHistoryResponse(
            channel_id=channel_id,
            conversations=conversation_pairs,
            total_count=len(conversation_pairs)
        )
        
    except Exception as e:
        print(f"❌ Error getting history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la récupération de l'historique: {str(e)}"
        )


@app.delete("/api/history/{channel_id}", response_model=ClearHistoryResponse, tags=["History"])
async def clear_history(channel_id: str):
    """
    Clear conversation history for a channel.
    
    Args:
        channel_id: The channel ID to clear history for
    """
    try:
        success = redis_memory.clear_conversation_history(channel_id)
        
        return ClearHistoryResponse(
            success=success,
            message="Historique effacé avec succès" if success else "Échec de l'effacement de l'historique"
        )
        
    except Exception as e:
        print(f"❌ Error clearing history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'effacement de l'historique: {str(e)}"
        )


@app.get("/api/stats", tags=["Stats"])
async def get_stats():
    """Get memory usage statistics"""
    try:
        stats = redis_memory.get_memory_stats()
        return stats
    except Exception as e:
        print(f"❌ Error getting stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la récupération des statistiques: {str(e)}"
        )


# ============================================
# Error Handlers
# ============================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    print(f"❌ Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "timestamp": datetime.now().isoformat()
        }
    )


# ============================================
# WebRTC Realtime Token Endpoint
# ============================================

import httpx

# Azure GPT-Realtime configuration
AZURE_REALTIME_API_KEY = os.getenv("AZURE_REALTIME_API_KEY")
AZURE_REALTIME_API_BASE = os.getenv("AZURE_REALTIME_API_BASE")


class WebRTCTokenRequest(BaseModel):
    """Request model for WebRTC token endpoint"""
    voice: str = Field(default="cedar", description="Voice to use")


class WebRTCTokenResponse(BaseModel):
    """Response model for WebRTC token endpoint"""
    token: str = Field(..., description="Ephemeral token for WebRTC")
    expires_at: Union[str, int] = Field(..., description="Token expiration time (timestamp or ISO string)")
    webrtc_url: str = Field(..., description="WebRTC endpoint URL")
    ice_servers: list = Field(default_factory=list, description="ICE servers for WebRTC")


@app.post("/api/realtime/token", response_model=WebRTCTokenResponse, tags=["Voice"])
async def get_realtime_token(request: WebRTCTokenRequest = WebRTCTokenRequest()):
    """
    Generate an ephemeral token for WebRTC connection to Azure OpenAI Realtime.
    
    Based on Azure docs: https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/realtime-webrtc
    
    Token URL: https://{resource}.openai.azure.com/openai/v1/realtime/client_secrets
    WebRTC URL: https://{resource}.openai.azure.com/openai/v1/realtime/calls
    """
    if not AZURE_REALTIME_API_KEY or not AZURE_REALTIME_API_BASE:
        raise HTTPException(
            status_code=503,
            detail="Azure Realtime API not configured"
        )
    
    try:
        # Parse the base URL to extract the resource name
        # User format: https://youss-mhtmnf7z-swedencentral.cognitiveservices.azure.com/openai/realtime?...
        # Docs format: https://{resource}.openai.azure.com/openai/v1/realtime/client_secrets
        api_base = AZURE_REALTIME_API_BASE.replace("wss://", "https://").replace("ws://", "http://")
        
        # Extract hostname and resource name
        hostname = api_base.split("//")[1].split("/")[0]
        
        # Extract the resource name (everything before the domain)
        # For cognitiveservices: youss-mhtmnf7z-swedencentral.cognitiveservices.azure.com -> youss-mhtmnf7z-swedencentral
        # For openai: myresource.openai.azure.com -> myresource
        if "cognitiveservices.azure.com" in hostname:
            azure_resource = hostname.replace(".cognitiveservices.azure.com", "")
        elif "openai.azure.com" in hostname:
            azure_resource = hostname.replace(".openai.azure.com", "")
        else:
            azure_resource = hostname.split(".")[0]
        
        # Per Azure docs, use openai.azure.com domain
        # URL: https://{azure_resource}.openai.azure.com/openai/v1/realtime/client_secrets
        # Removing api-version as it caused 400 errors, but keeping it for WebRTC as handshake usually needs it
        token_url = f"https://{azure_resource}.openai.azure.com/openai/v1/realtime/client_secrets"
        # Using 2024-10-01-preview for WebRTC handshake
        webrtc_calls_url = f"https://{azure_resource}.openai.azure.com/openai/v1/realtime/calls?api-version=2024-10-01-preview"
        
        print(f"🔧 Original hostname: {hostname}")
        print(f"🔧 Azure resource: {azure_resource}")
        print(f"🔧 Token URL: {token_url}")
        
        # Session configuration per Azure docs
        # Extract deployment name from the original URL if available
        deployment_name = "gpt-realtime"
        if "deployment=" in AZURE_REALTIME_API_BASE:
            deployment_name = AZURE_REALTIME_API_BASE.split("deployment=")[1].split("&")[0]
        
        print(f"🔧 Deployment name: {deployment_name}")
        
        session_config = {
            "session": {
                "type": "realtime",
                "model": deployment_name,
                "instructions": """Tu es 'MonkEDH', l'assistant vocal du SAMU Tunisien (190).
                
                RÈGLE D'OR : ADAPTATION LINGUISTIQUE AUTOMATIQUE
                - Si l'utilisateur parle FRANÇAIS -> Réponds en FRANÇAIS.
                - Si l'utilisateur parle ARABE / TUNISIEN (Derja) -> Réponds en DERJA TUNISIEN.
                - Ne demande jamais quelle langue utiliser. Adapte-toi instantanément.

                MISSION :
                1. Écoute l'utilisateur.
                2. Consulte TOUJOURS 'query_medical_assistant' pour l'expertise médicale.
                3. Reformule la réponse de l'expert dans la langue détectée.

                TON ET STYLE :
                - En Tunisien : Utilise le dialecte local (Derja) + termes médicaux français si nécessaire (ex: "Sbitar", "Ambulance", "Massage").
                - En Français : Professionnel, clair, empathique.
                - URGENCE : Ton FERME et DIRECT ("Appuyez maintenant !").
                - RASSURANCE : Ton CALME et DOUX ("Respire, ça va aller").

                RÈGLES TECHNIQUES :
                - NE LIS PAS de Markdown, URLs ou chemins de fichiers.
                - Dis "Je vous montre..." pour les images.
                - Phrases courtes, optimisées pour la synthèse vocale.""",
                "audio": {
                    "output": {
                        "voice": request.voice,
                    },
                },
                "tools": [
                    {
                        "type": "function",
                        "name": "query_medical_assistant",
                        "description": "Consult the medical CrewAI expert system for emergency advice, diagnosis, or procedure.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The user's description of the emergency or medical question."
                                }
                            },
                            "required": ["query"]
                        }
                    }
                ],
                "tool_choice": "auto",
            },
        }
        
        # Request ephemeral token using api-key authentication
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                headers={
                    "api-key": AZURE_REALTIME_API_KEY,
                    "Content-Type": "application/json"
                },
                json=session_config,
                timeout=30.0
            )
            
            print(f"🔧 Response status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"❌ Token request failed: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to get ephemeral token: {response.text}"
                )
            
            data = response.json()
            print(f"🔧 Response data keys: {list(data.keys())}")
        
        print(f"🔧 WebRTC URL: {webrtc_calls_url}")
        
        # Extract token - per docs it's in "value" field
        token = data.get("value", data.get("token", data.get("client_secret", {}).get("value", "")))
        
        return WebRTCTokenResponse(
            token=token,
            expires_at=data.get("expires_at", data.get("client_secret", {}).get("expires_at", "")),
            webrtc_url=webrtc_calls_url,
            ice_servers=data.get("ice_servers", [])
        )
        
    except httpx.HTTPError as e:
        print(f"❌ HTTP error getting token: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to communicate with Azure: {str(e)}"
        )
    except Exception as e:
        print(f"❌ Error getting realtime token: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating token: {str(e)}"
        )


# ============================================
# Voice WebSocket - GPT Realtime Integration (Legacy)
# ============================================

import re
import websockets


class GPTRealtimeProxy:
    """
    Proxy between browser WebSocket and Azure GPT-Realtime.
    Handles bidirectional audio streaming with audio level tracking.
    """
    
    def __init__(self, session_id: str, client_ws: WebSocket):
        self.session_id = session_id
        self.client_ws = client_ws
        self.azure_stt_ws = None
        self.azure_tts_ws = None
        self.is_running = False
        self.is_speaking = False
        self.is_processing = False
        self.current_audio_level = 0.0
        self.has_audio_buffered = False
        # Azure STT requires >= ~100ms of audio before committing the input buffer.
        # For pcm16 mono @ 24kHz: 24000 samples/sec * 2 bytes = 48000 bytes/sec => 100ms ~= 4800 bytes.
        self._stt_buffer_bytes = 0
        self._min_commit_bytes = int(0.1 * 24000 * 2)
        self._response_lock = asyncio.Lock()
        self._current_turn_task: Optional[asyncio.Task] = None
        self._turn_seq = 0
        self.current_response_id: Optional[str] = None
        # Barge-in control: when True, allow audio forwarding even while speaking
        self.allow_audio_during_speech = False
        # STT response tracking: prevent duplicate response.create calls
        self.stt_response_in_progress = False

    @staticmethod
    def _estimate_b64_decoded_size(b64: str) -> int:
        if not b64:
            return 0
        s = b64.strip()
        padding = 2 if s.endswith("==") else 1 if s.endswith("=") else 0
        # Base64: 4 chars -> 3 bytes (minus padding)
        return max(0, (len(s) * 3) // 4 - padding)
        
    def _build_ws_url(self) -> str:
        ws_url = AZURE_REALTIME_API_BASE.replace("https://", "wss://").replace("http://", "ws://")
        return ws_url

    def _clean_for_speech(self, text: str) -> str:
        # Remove markdown + common artifacts that sound bad in TTS
        # Strip box/table drawing characters often produced by formatted outputs
        text = re.sub(r"[│┃║╎╏┆┇┊┋┌┐└┘├┤┬┴┼─━]+", " ", text)
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"\*(.+?)\*", r"\1", text)
        text = re.sub(r"#+\s*", "", text)
        text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
        text = re.sub(r"`(.+?)`", r"\1", text)
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
        text = re.sub(r"Image suggérée:.*?\.png", "", text)
        text = re.sub(r"📷.*?\.png", "", text)
        text = re.sub(r"\s*---+\s*", " ", text)
        text = re.sub(r"\n\s*\n", "\n", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    async def connect_azure(self):
        """Connect to Azure GPT-Realtime WebSockets (STT + TTS)."""
        if not AZURE_REALTIME_API_KEY or not AZURE_REALTIME_API_BASE:
            raise ValueError("Azure GPT-Realtime credentials not configured")

        ws_url = self._build_ws_url()
        headers = {"api-key": AZURE_REALTIME_API_KEY}

        # STT connection: server VAD + Whisper transcription, no assistant generation
        self.azure_stt_ws = await websockets.connect(
            ws_url,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=10
        )

        stt_session_config = {
            "type": "session.update",
            "session": {
                "modalities": ["text"],
                "instructions": "Tu es un service de transcription. Transcris uniquement l'audio utilisateur en français. Ne réponds jamais.",
                "input_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.45,
                    "prefix_padding_ms": 200,
                    "silence_duration_ms": 500
                }
            }
        }

        await self.azure_stt_ws.send(json.dumps(stt_session_config))

        while True:
            response = await self.azure_stt_ws.recv()
            data = json.loads(response)
            if data.get("type") in ["session.created", "session.updated"]:
                print(f"✅ GPT-Realtime STT session established for {self.session_id}")
                break

        # TTS connection: generate audio for CrewAI responses
        self.azure_tts_ws = await websockets.connect(
            ws_url,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=10
        )

        tts_session_config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": (
                    "Tu es la VOIX d'un assistant d'urgence (appel téléphonique) en français. "
                    "Tu transformes le texte reçu en paroles naturelles, réalistes et actionnables. "
                    "Objectif: aider vite, avec empathie et autorité quand c'est grave. "
                    "\n\nSTYLE/ÉMOTION: "
                    "- URGENCE VITALE: ton ferme et direct, rythme rapide, phrases très courtes, impératifs. "
                    "- Sinon: ton calme, chaleureux, rassurant. "
                    "Ajoute des micro-pauses avec la ponctuation (virgules, points) pour un rendu humain, sans exagérer. "
                    "\n\nFORMAT: "
                    "- 3 à 6 phrases maximum. Pas de listes, pas de numérotation, pas de titres. "
                    "- Termine par UNE question courte pour confirmer l'état (ex: 'Il respire, là, oui ou non ?'). "
                    "\n\nFILTRAGE STRICT: "
                    "- Ne lis jamais d'URLs http/https, ni de chemins de fichiers/images (ex: emergency_image_db/..., images/..., C:\\..., /home/...). "
                    "- Ne lis pas le markdown (#, **, -, 1.), ni tableaux/métadonnées. "
                    "- Si le texte mentionne une image/chemin, remplace par: 'Je t'accompagne avec un guide visuel.' "
                    "- Ignore les sections comme 'FORMAT', 'SOURCE', 'GUIDE VISUEL', séparateurs '---'. "
                    "Ne dis jamais que tu filtres ou que tu réécris."
                ),
                "voice": "cedar",
                "output_audio_format": "pcm16",
                "turn_detection": None,
            },
        }

        await self.azure_tts_ws.send(json.dumps(tts_session_config))

        while True:
            response = await self.azure_tts_ws.recv()
            data = json.loads(response)
            if data.get("type") in ["session.created", "session.updated"]:
                print(f"✅ GPT-Realtime TTS session established for {self.session_id}")
                break
    
    def calculate_audio_level(self, audio_data: bytes) -> float:
        """Calculate RMS audio level from PCM16 data (0.0 to 1.0)."""
        try:
            import struct
            samples = struct.unpack(f'{len(audio_data)//2}h', audio_data)
            if not samples:
                return 0.0
            rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
            # Normalize to 0-1 range (max PCM16 value is 32768)
            normalized = min(1.0, rms / 8000)  # 8000 as practical speech max
            return normalized
        except Exception:
            return 0.0
    
    async def _commit_and_request_transcription(self):
        if not self.azure_stt_ws:
            return
        if not self.has_audio_buffered:
            return
        if self._stt_buffer_bytes < self._min_commit_bytes:
            # Avoid committing tiny/empty buffers (Azure returns: "buffer too small").
            try:
                await self.azure_stt_ws.send(json.dumps({"type": "input_audio_buffer.clear"}))
            except Exception:
                pass
            self.has_audio_buffered = False
            self._stt_buffer_bytes = 0
            return

        try:
            await self.azure_stt_ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
            # Only create response if no STT response is already in progress
            if not self.stt_response_in_progress:
                self.stt_response_in_progress = True
                await self.azure_stt_ws.send(json.dumps({"type": "response.create"}))
            self.has_audio_buffered = False
            self._stt_buffer_bytes = 0
        except Exception as e:
            print(f"⚠️ Failed to commit audio buffer: {e}")
            # If Azure rejected the commit, reset the buffer to prevent repeated errors.
            try:
                await self.azure_stt_ws.send(json.dumps({"type": "input_audio_buffer.clear"}))
            except Exception:
                pass
            self.has_audio_buffered = False
            self._stt_buffer_bytes = 0

    async def _speak_text(self, text: str):
        if not self.azure_tts_ws:
            return

        speak_text = self._clean_for_speech(text)
        if not speak_text:
            return

        self.is_speaking = True
        self.allow_audio_during_speech = False  # Reset for new response
        self.current_response_id = str(uuid.uuid4())
        
        # Clear any pending audio in STT buffer to prevent stale audio from triggering VAD
        if self.azure_stt_ws:
            try:
                await self.azure_stt_ws.send(json.dumps({"type": "input_audio_buffer.clear"}))
                self.has_audio_buffered = False
                self._stt_buffer_bytes = 0
                print(f"🟢 Cleared STT buffer before TTS (response_id: {self.current_response_id})")
            except Exception:
                pass
        
        await self.client_ws.send_json({
            "type": "status", 
            "state": "speaking",
            "responseId": self.current_response_id
        })

        # Safety cap: cut off overly long TTS to keep emergency voice interactions snappy.
        # pcm16 mono @ 24kHz => 48000 bytes/sec
        max_tts_seconds = 14
        max_tts_bytes = max_tts_seconds * 24000 * 2
        spoken_bytes = 0

        msg = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Transforme le texte suivant en un court message ORAL d'urgence (appel téléphonique). "
                            "Garde uniquement l'essentiel, rends-le humain et réaliste, avec le ton adapté (grave => ferme, sinon rassurant). "
                            "Pas de listes, pas de numéros, pas de titres. 3 à 6 phrases maximum. "
                            "Ne lis jamais les URLs/chemins/markdown; si une image est mentionnée, dis: 'Je t'accompagne avec un guide visuel.' "
                            "Termine par une question courte pour confirmer l'état. "
                            f"Texte source: {speak_text}"
                        ),
                    }
                ],
            },
        }
        await self.azure_tts_ws.send(json.dumps(msg))
        await self.azure_tts_ws.send(json.dumps({"type": "response.create"}))

        try:
            while self.is_running and self.azure_tts_ws:
                # If we were interrupted, stop waiting for more audio.
                if not self.is_speaking:
                    break

                try:
                    response = await asyncio.wait_for(self.azure_tts_ws.recv(), timeout=0.25)
                except asyncio.TimeoutError:
                    continue

                data = json.loads(response)
                msg_type = data.get("type", "")

                if msg_type == "response.audio.delta":
                    audio_b64 = data.get("delta", "")
                    if audio_b64:
                        audio_data = base64.b64decode(audio_b64)
                        spoken_bytes += len(audio_data)
                        if spoken_bytes >= max_tts_bytes:
                            # Cancel remaining audio generation.
                            try:
                                await self.azure_tts_ws.send(json.dumps({"type": "response.cancel"}))
                            except Exception:
                                pass
                            break
                        audio_level = self.calculate_audio_level(audio_data)
                        await self.client_ws.send_json({
                            "type": "audio",
                            "data": audio_b64,
                            "level": audio_level,
                            "sampleRate": 24000,
                            "responseId": self.current_response_id
                        })
                elif msg_type == "response.done":
                    break
                elif msg_type == "error":
                    error = data.get("error", {})
                    await self.client_ws.send_json({
                        "type": "error",
                        "message": error.get("message", "Unknown error"),
                    })
                    break
        finally:
            self.is_speaking = False

    async def interrupt(self):
        """Immediately stop any ongoing TTS playback/generation."""
        print(f"🔴 INTERRUPT called! is_speaking was: {self.is_speaking}, response_id: {self.current_response_id}")
        self.is_speaking = False
        self.allow_audio_during_speech = True  # Allow audio through for the new turn
        # Ask Azure to cancel current response generation (if any)
        if self.azure_tts_ws:
            try:
                await self.azure_tts_ws.send(json.dumps({"type": "response.cancel"}))
            except Exception:
                pass
        # Tell the client to stop local playback right away
        try:
            await self.client_ws.send_json({"type": "status", "state": "listening"})
            await self.client_ws.send_json({
                "type": "control", 
                "action": "stop_playback",
                "responseId": self.current_response_id
            })
        except Exception:
            pass

    async def _handle_user_text_with_crew(self, transcript: str):
        async with self._response_lock:
            turn_seq = self._turn_seq
            self.is_processing = True
            try:
                await self.client_ws.send_json({"type": "status", "state": "processing"})

                channel_id = f"voice_{self.session_id}"
                user_id = self.session_id

                response_text = await asyncio.to_thread(
                    process_question,
                    channel_id=channel_id,
                    user_id=user_id,
                    username="Voice User",
                    question=transcript,
                )

                # If a newer turn has started, do not speak the older response.
                if self._turn_seq != turn_seq:
                    return

                clean_response = self._clean_for_speech(response_text)
                await self.client_ws.send_json({
                    "type": "transcript",
                    "text": clean_response,
                    "speaker": "assistant",
                })

                await self._speak_text(clean_response)
            except asyncio.CancelledError:
                # Newer user turn arrived; drop this one quietly.
                return
            except Exception as e:
                print(f"❌ CrewAI/TTS pipeline error: {e}")
                await self.client_ws.send_json({
                    "type": "error",
                    "message": str(e),
                })
            finally:
                self.is_processing = False
                self.is_speaking = False
                await self.client_ws.send_json({"type": "status", "state": "listening"})

    async def handle_azure_messages(self):
        """Process messages from Azure STT session and forward transcripts/status to client."""
        
        try:
            while self.is_running and self.azure_stt_ws:
                try:
                    response = await asyncio.wait_for(self.azure_stt_ws.recv(), timeout=0.1)
                    data = json.loads(response)
                    msg_type = data.get("type", "")
                    
                    # User's speech transcription completed
                    if msg_type == "conversation.item.input_audio_transcription.completed":
                        transcript = data.get("transcript", "")
                        if transcript:
                            await self.client_ws.send_json({
                                "type": "transcript",
                                "text": transcript,
                                "speaker": "user"
                            })

                            # Route transcript through CrewAI and then speak it back.
                            # Cancel any in-flight turn so the latest user request is handled ASAP.
                            self._turn_seq += 1
                            turn_seq = self._turn_seq

                            if self._current_turn_task and not self._current_turn_task.done():
                                try:
                                    self._current_turn_task.cancel()
                                except Exception:
                                    pass

                            self._current_turn_task = asyncio.create_task(self._handle_user_text_with_crew(transcript))
                    
                    # Speech started detection
                    elif msg_type == "input_audio_buffer.speech_started":
                        # COMPLETELY IGNORE speech events while TTS is playing
                        # to prevent any false barge-in from echo/mic feedback
                        if self.is_speaking:
                            print(f"� Ignoring VAD speech_started - TTS is playing")
                            continue  # Skip entirely, don't even send status
                        await self.client_ws.send_json({
                            "type": "status",
                            "state": "user_speaking"
                        })
                    
                    # Speech stopped detection
                    elif msg_type == "input_audio_buffer.speech_stopped":
                        # COMPLETELY IGNORE speech events while TTS is playing
                        if self.is_speaking:
                            print(f"🟡 Ignoring VAD speech_stopped - TTS is playing")
                            continue  # Skip entirely
                        await self.client_ws.send_json({
                            "type": "status",
                            "state": "processing"
                        })
                        await self._commit_and_request_transcription()
                    
                    # STT response tracking - clear flag when response is done
                    elif msg_type == "response.done":
                        self.stt_response_in_progress = False
                    
                    # Ignore other response events from STT session
                    elif msg_type.startswith("response."):
                        continue
                    
                    # Error handling - suppress non-critical Azure errors
                    elif msg_type == "error":
                        error = data.get("error", {})
                        error_msg = error.get("message", "Unknown error")
                        # Don't flood the client with Azure internal errors
                        if "buffer too small" in error_msg or "active response in progress" in error_msg:
                            print(f"⚠️ Azure non-critical error (suppressed): {error_msg}")
                            continue
                        await self.client_ws.send_json({
                            "type": "error",
                            "message": error_msg
                        })
                    
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    print(f"⚠️ Azure connection closed for {self.session_id}")
                    break
                    
        except Exception as e:
            print(f"❌ Azure message handler error: {e}")
            await self.client_ws.send_json({
                "type": "error",
                "message": str(e)
            })
    
    async def forward_audio_to_azure(self, audio_b64: str):
        """Forward audio chunk from client to Azure."""
        # Do not forward audio while assistant is speaking to prevent
        # the assistant's own voice from triggering false VAD interrupts.
        # Exception: if barge-in was triggered, allow audio through.
        if self.is_speaking and not self.allow_audio_during_speech:
            return
        if self.azure_stt_ws:
            msg = {
                "type": "input_audio_buffer.append",
                "audio": audio_b64
            }
            await self.azure_stt_ws.send(json.dumps(msg))
            self._stt_buffer_bytes += self._estimate_b64_decoded_size(audio_b64)
            self.has_audio_buffered = self._stt_buffer_bytes > 0
    
    async def send_text_to_azure(self, text: str):
        """Handle a text input from client (routes through CrewAI then speaks)."""
        if text:
            # Same prioritization as STT: latest user text wins.
            self._turn_seq += 1
            if self._current_turn_task and not self._current_turn_task.done():
                try:
                    self._current_turn_task.cancel()
                except Exception:
                    pass
            self._current_turn_task = asyncio.create_task(self._handle_user_text_with_crew(text))
    
    async def start(self):
        """Start the proxy connection."""
        self.is_running = True
        await self.connect_azure()
        
        # Start Azure message handler task
        asyncio.create_task(self.handle_azure_messages())
        
        await self.client_ws.send_json({
            "type": "status",
            "state": "connected",
            "message": "Connexion établie avec l'assistant vocal IA"
        })
    
    async def stop(self):
        """Stop the proxy connection."""
        self.is_running = False
        if self.azure_stt_ws:
            await self.azure_stt_ws.close()
            self.azure_stt_ws = None
        if self.azure_tts_ws:
            await self.azure_tts_ws.close()
            self.azure_tts_ws = None


class VoiceConnectionManager:
    """Manages WebSocket connections for voice calls"""
    
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.active_proxies: dict[str, GPTRealtimeProxy] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        print(f"🎤 Voice connection established: {session_id}")
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            print(f"🔌 Voice connection closed: {session_id}")
        if session_id in self.active_proxies:
            del self.active_proxies[session_id]
    
    async def send_message(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(message)


voice_manager = VoiceConnectionManager()


@app.websocket("/api/voice/{session_id}")
async def voice_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time voice communication via Azure GPT-Realtime.
    
    Protocol:
    - Client sends: {"type": "audio", "data": "<base64_pcm16_24khz>"} for audio chunks
    - Client sends: {"type": "text", "message": "<text>"} for text input
    - Client sends: {"type": "end"} to end session
    - Client sends: {"type": "interrupt"} to stop assistant speech immediately
    
    - Server sends: {"type": "audio", "data": "<base64>", "level": 0.0-1.0, "sampleRate": 24000}
    - Server sends: {"type": "transcript", "text": "<text>", "speaker": "user"|"assistant"}
    - Server sends: {"type": "transcript_delta", "text": "<delta>", "speaker": "assistant"}
    - Server sends: {"type": "status", "state": "connected"|"listening"|"user_speaking"|"processing"|"speaking"|"ended"}
    - Server sends: {"type": "error", "message": "<error_message>"}
    - Server sends: {"type": "control", "action": "stop_playback"}
    """
    await voice_manager.connect(websocket, session_id)
    
    proxy = None
    
    try:
        # Check if Azure credentials are available
        if AZURE_REALTIME_API_KEY and AZURE_REALTIME_API_BASE:
            # Use GPT-Realtime proxy
            proxy = GPTRealtimeProxy(session_id, websocket)
            voice_manager.active_proxies[session_id] = proxy
            await proxy.start()
            
            # Handle client messages
            while True:
                try:
                    data = await websocket.receive_json()
                    msg_type = data.get("type", "")
                    
                    if msg_type == "end":
                        await websocket.send_json({
                            "type": "status",
                            "state": "ended",
                            "message": "Session terminée"
                        })
                        break
                    
                    elif msg_type == "audio":
                        audio_data = data.get("data", "")
                        if audio_data:
                            await proxy.forward_audio_to_azure(audio_data)
                    
                    elif msg_type == "text":
                        message = data.get("message", "").strip()
                        if message:
                            await proxy.send_text_to_azure(message)

                    elif msg_type == "interrupt":
                        if proxy:
                            await proxy.interrupt()
                    
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    print(f"❌ Voice WebSocket error: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e)
                    })
        else:
            # Fallback: Text-only mode with browser TTS
            await websocket.send_json({
                "type": "status",
                "state": "connected",
                "mode": "text_only",
                "message": "Mode texte uniquement (GPT-Realtime non configuré)"
            })
            
            channel_id = f"voice_{session_id}"
            user_id = session_id
            
            while True:
                try:
                    data = await websocket.receive_json()
                    msg_type = data.get("type", "")
                    
                    if msg_type == "end":
                        await websocket.send_json({
                            "type": "status",
                            "state": "ended"
                        })
                        break
                    
                    elif msg_type == "text":
                        message = data.get("message", "").strip()
                        if not message:
                            continue
                        
                        await websocket.send_json({
                            "type": "status",
                            "state": "processing"
                        })
                        
                        response = await asyncio.to_thread(
                            process_question,
                            channel_id=channel_id,
                            user_id=user_id,
                            username="Voice User",
                            question=message
                        )
                        
                        await websocket.send_json({
                            "type": "response",
                            "text": response
                        })
                        
                        await websocket.send_json({
                            "type": "status",
                            "state": "listening"
                        })
                    
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    print(f"❌ Voice WebSocket error: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e)
                    })
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"❌ Voice connection error: {e}")
    finally:
        if proxy:
            await proxy.stop()
        voice_manager.disconnect(session_id)


# ============================================
# Video Report Endpoints
# ============================================

async def run_video_analysis(
    report_id: str,
    video_path: str,
    language: str = "fr",
    send_email: bool = False,
    email: Optional[str] = None
):
    """Background task to run video analysis"""
    try:
        video_analysis_tasks[report_id]["status"] = "processing"
        
        # Get video info
        video_info = get_video_info(video_path)
        video_analysis_tasks[report_id]["video_info"] = video_info
        
        # Extract frames
        frames_dir = str(VIDEO_REPORT_FRAMES_PATH / report_id)
        os.makedirs(frames_dir, exist_ok=True)
        frames = extract_frames(video_path, every_n_seconds=2.0, output_dir=frames_dir)
        video_analysis_tasks[report_id]["status"] = "analyzing_frames"
        
        # Analyze audio
        video_analysis_tasks[report_id]["status"] = "analyzing_audio"
        audio_result = analyze_video_audio(video_path)
        
        # Generate report directly (skip CrewAI for now due to configuration issues)
        video_analysis_tasks[report_id]["status"] = "generating_report"
        logger.info("Generating report directly without CrewAI...")
        
        # Get the generated report or create one
        report_files = list(VIDEO_REPORT_REPORTS_PATH.glob(f"{report_id}*.md"))
        if not report_files:
            # Generate report manually
            logger.info("Generating manual report...")
            
            # Build frame descriptions
            frame_descriptions = []
            for frame_path in frames:
                frame_descriptions.append({
                    "frame_path": frame_path,
                    "timestamp": Path(frame_path).stem.split("_t")[-1].replace("s", "") if "_t" in frame_path else "0",
                    "description": "Frame extrait de la vidéo d'urgence"
                })
            
            # Generate report (returns tuple of (md_path, html_path))
            md_path, html_path = generate_report(
                frame_descriptions=frame_descriptions,
                audio_results=audio_result,
                vision_client=None,
                output_dir=str(VIDEO_REPORT_REPORTS_PATH),
                language="français" if language == "fr" else "arabe"
            )
            
            report_path = Path(md_path)
            
            # Rename to use report_id
            new_md_path = VIDEO_REPORT_REPORTS_PATH / f"{report_id}_report.md"
            new_html_path = VIDEO_REPORT_REPORTS_PATH / f"{report_id}_report.html"
            
            if report_path.exists():
                report_path.rename(new_md_path)
                report_path = new_md_path
            if Path(html_path).exists():
                Path(html_path).rename(new_html_path)
                html_path = new_html_path
                
            with open(report_path, "r", encoding="utf-8") as f:
                report_content = f.read()
            
            logger.info(f"Manual report generated: {report_path}")
        else:
            report_path = report_files[0]
            with open(report_path, "r", encoding="utf-8") as f:
                report_content = f.read()
            logger.info(f"Using CrewAI generated report: {report_path}")
        
        # Convert to HTML
        html_content = markdown_to_html(report_content)
        html_path = VIDEO_REPORT_REPORTS_PATH / f"{report_id}_report.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        # Save metadata
        metadata = {
            "id": report_id,
            "title": f"Rapport d'analyse - {video_info.get('filename', 'Vidéo')}",
            "date": datetime.now().isoformat(),
            "status": "completed",
            "video_info": video_info,
            "audio_analysis": audio_result,
            "report_path": str(report_path),
            "html_path": str(html_path)
        }
        metadata_path = VIDEO_REPORT_REPORTS_PATH / f"{report_id}_metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        video_analysis_tasks[report_id]["status"] = "completed"
        video_analysis_tasks[report_id]["metadata"] = metadata
        
        # Send email if requested
        if send_email and email:
            try:
                sender = EmailSender()
                sender.send_report(
                    to_email=email,
                    subject=f"Rapport d'urgence - {report_id}",
                    html_content=html_content,
                    markdown_content=report_content
                )
                video_analysis_tasks[report_id]["email_sent"] = True
            except Exception as e:
                print(f"❌ Failed to send email: {e}")
                video_analysis_tasks[report_id]["email_error"] = str(e)
        
        # Cleanup temp video file
        try:
            os.remove(video_path)
        except:
            pass
            
    except Exception as e:
        print(f"❌ Video analysis error: {e}")
        video_analysis_tasks[report_id]["status"] = "error"
        video_analysis_tasks[report_id]["error"] = str(e)


@app.post("/api/video/analyze", response_model=VideoAnalysisResponse, tags=["Video Report"])
async def analyze_video_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: str = Form("fr"),
    send_email: bool = Form(False),
    email: Optional[str] = Form(None)
):
    """
    Upload and analyze a video for emergency report generation.
    
    The analysis runs in the background and includes:
    - Frame extraction and visual analysis
    - Audio transcription and emotion detection
    - Comprehensive emergency report generation
    """
    if not VIDEO_REPORT_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Le module d'analyse vidéo n'est pas disponible. Vérifiez les dépendances."
        )
    
    # Validate file type
    allowed_types = ["video/mp4", "video/mpeg", "video/quicktime", "video/x-msvideo", "video/webm"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Type de fichier non supporté: {file.content_type}. Types acceptés: MP4, MPEG, MOV, AVI, WebM"
        )
    
    # Generate report ID
    report_id = f"report_{uuid.uuid4().hex[:12]}"
    
    # Save uploaded file temporarily
    temp_dir = tempfile.mkdtemp()
    video_path = os.path.join(temp_dir, file.filename or "video.mp4")
    
    try:
        with open(video_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'enregistrement de la vidéo: {str(e)}"
        )
    
    # Initialize task tracking
    video_analysis_tasks[report_id] = {
        "status": "queued",
        "created_at": datetime.now().isoformat(),
        "filename": file.filename
    }
    
    # Start background analysis
    background_tasks.add_task(
        run_video_analysis,
        report_id=report_id,
        video_path=video_path,
        language=language,
        send_email=send_email,
        email=email
    )
    
    return VideoAnalysisResponse(
        report_id=report_id,
        status="queued",
        message="Analyse vidéo démarrée. Utilisez GET /api/video/reports/{report_id} pour suivre la progression.",
        video_info={"filename": file.filename, "size": file.size}
    )


@app.get("/api/video/status/{report_id}", tags=["Video Report"])
async def get_video_analysis_status(report_id: str):
    """Get the status of a video analysis task"""
    if report_id not in video_analysis_tasks:
        raise HTTPException(status_code=404, detail="Rapport non trouvé")
    
    task = video_analysis_tasks[report_id]
    return {
        "report_id": report_id,
        "status": task.get("status"),
        "created_at": task.get("created_at"),
        "error": task.get("error")
    }


@app.get("/api/video/reports", response_model=VideoReportListResponse, tags=["Video Report"])
async def list_video_reports():
    """List all generated video reports"""
    reports = []
    
    # Scan for metadata files
    for metadata_file in VIDEO_REPORT_REPORTS_PATH.glob("*_metadata.json"):
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            
            # Get thumbnail if exists
            report_id = metadata.get("id", "")
            frames_dir = VIDEO_REPORT_FRAMES_PATH / report_id
            thumbnail = None
            if frames_dir.exists():
                frame_files = list(frames_dir.glob("*.jpg")) + list(frames_dir.glob("*.png"))
                if frame_files:
                    # Return relative URL for thumbnail
                    thumbnail = f"/api/video/frames/{report_id}/{frame_files[0].name}"
            
            reports.append(VideoReportItem(
                id=metadata.get("id", ""),
                title=metadata.get("title", "Rapport sans titre"),
                date=metadata.get("date", ""),
                status=metadata.get("status", "unknown"),
                thumbnail=thumbnail,
                summary=metadata.get("video_info", {}).get("filename")
            ))
        except Exception as e:
            print(f"⚠️ Error reading metadata {metadata_file}: {e}")
    
    # Also include in-progress tasks
    for report_id, task in video_analysis_tasks.items():
        if task.get("status") not in ["completed", "error"]:
            reports.append(VideoReportItem(
                id=report_id,
                title=f"Analyse en cours - {task.get('filename', 'Vidéo')}",
                date=task.get("created_at", ""),
                status=task.get("status", "processing"),
                summary=task.get("filename")
            ))
    
    # Sort by date descending
    reports.sort(key=lambda x: x.date, reverse=True)
    
    return VideoReportListResponse(
        reports=reports,
        total_count=len(reports)
    )


@app.get("/api/video/reports/{report_id}", response_model=VideoReportDetailResponse, tags=["Video Report"])
async def get_video_report(report_id: str):
    """Get a specific video report by ID"""
    metadata_path = VIDEO_REPORT_REPORTS_PATH / f"{report_id}_metadata.json"
    
    # Check in-progress tasks first
    if report_id in video_analysis_tasks:
        task = video_analysis_tasks[report_id]
        if task.get("status") != "completed":
            return VideoReportDetailResponse(
                id=report_id,
                title=f"Analyse en cours - {task.get('filename', 'Vidéo')}",
                date=task.get("created_at", ""),
                status=task.get("status", "processing"),
                content_html=f"<p>Statut: {task.get('status', 'En cours...')}</p>",
                content_markdown=f"**Statut:** {task.get('status', 'En cours...')}",
                video_info=task.get("video_info")
            )
    
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Rapport non trouvé")
    
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        # Read report content
        report_path = Path(metadata.get("report_path", ""))
        html_path = Path(metadata.get("html_path", ""))
        
        content_markdown = ""
        content_html = ""
        
        if report_path.exists():
            with open(report_path, "r", encoding="utf-8") as f:
                content_markdown = f.read()
        
        if content_markdown:
            content_html = markdown_to_html(content_markdown, full_html=False) if VIDEO_REPORT_AVAILABLE else content_markdown
        elif html_path.exists():
            with open(html_path, "r", encoding="utf-8") as f:
                content_html = f.read()
                # Simple strip for full HTML documents if they were saved previously
                if "<body" in content_html:
                    try:
                        import re
                        body_content = re.search(r'<div class="content">(.*?)<div class="emergency-numbers">', content_html, re.DOTALL)
                        if body_content:
                            content_html = body_content.group(1).strip()
                        else:
                            body_only = re.search(r'<body.*?>(.*?)</body>', content_html, re.DOTALL)
                            if body_only:
                                content_html = body_only.group(1).strip()
                    except:
                        pass
        
        return VideoReportDetailResponse(
            id=metadata.get("id", report_id),
            title=metadata.get("title", "Rapport"),
            date=metadata.get("date", ""),
            status=metadata.get("status", "completed"),
            content_html=content_html,
            content_markdown=content_markdown,
            video_info=metadata.get("video_info"),
            audio_analysis=metadata.get("audio_analysis")
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la lecture du rapport: {str(e)}"
        )


@app.delete("/api/video/reports/{report_id}", tags=["Video Report"])
async def delete_video_report(report_id: str):
    """Delete a video report and associated files"""
    deleted_files = []
    
    # Delete metadata
    metadata_path = VIDEO_REPORT_REPORTS_PATH / f"{report_id}_metadata.json"
    if metadata_path.exists():
        os.remove(metadata_path)
        deleted_files.append(str(metadata_path))
    
    # Delete report files
    for ext in [".md", ".html"]:
        for report_file in VIDEO_REPORT_REPORTS_PATH.glob(f"{report_id}*{ext}"):
            os.remove(report_file)
            deleted_files.append(str(report_file))
    
    # Delete frames directory
    frames_dir = VIDEO_REPORT_FRAMES_PATH / report_id
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
        deleted_files.append(str(frames_dir))
    
    # Remove from in-memory tasks
    if report_id in video_analysis_tasks:
        del video_analysis_tasks[report_id]
    
    if not deleted_files:
        raise HTTPException(status_code=404, detail="Rapport non trouvé")
    
    return {"success": True, "message": f"Rapport {report_id} supprimé", "deleted": deleted_files}


@app.post("/api/video/reports/{report_id}/email", tags=["Video Report"])
async def email_video_report(report_id: str, request: EmailReportRequest):
    """Send a video report via email"""
    if not VIDEO_REPORT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Module vidéo non disponible")
    
    metadata_path = VIDEO_REPORT_REPORTS_PATH / f"{report_id}_metadata.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Rapport non trouvé")
    
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        html_path = Path(metadata.get("html_path", ""))
        report_path = Path(metadata.get("report_path", ""))
        
        html_content = ""
        markdown_content = ""
        
        if html_path.exists():
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
        
        if report_path.exists():
            with open(report_path, "r", encoding="utf-8") as f:
                markdown_content = f.read()
        
        sender = EmailSender()
        sender.send_report(
            to_email=request.email,
            subject=request.subject or f"Rapport d'urgence - {report_id}",
            html_content=html_content,
            markdown_content=markdown_content
        )
        
        return {"success": True, "message": f"Rapport envoyé à {request.email}"}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'envoi de l'email: {str(e)}"
        )


@app.get("/api/video/frames/{report_id}/{filename}", tags=["Video Report"])
async def get_video_frame(report_id: str, filename: str):
    """Get a specific frame image from a video analysis"""
    frame_path = VIDEO_REPORT_FRAMES_PATH / report_id / filename
    
    if not frame_path.exists():
        raise HTTPException(status_code=404, detail="Image non trouvée")
    
    return FileResponse(frame_path)


# ============================================
# Entry Point
# ============================================

def run_api(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Run the FastAPI server"""
    uvicorn.run(
        "monkedh.api:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == "__main__":
    run_api()
