"""
FastAPI REST API for the Emergency First Aid Assistant
Provides endpoints for chat, conversation history, and health checks
"""
import os
import uuid
import base64
import asyncio
import logging
from typing import Optional, List
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
# Voice WebSocket
# ============================================

class VoiceConnectionManager:
    """Manages WebSocket connections for voice calls"""
    
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        print(f"🎤 Voice connection established: {session_id}")
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            print(f"🔌 Voice connection closed: {session_id}")
    
    async def send_message(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(message)


voice_manager = VoiceConnectionManager()


@app.websocket("/api/voice/{session_id}")
async def voice_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for voice communication.
    
    Protocol:
    - Client sends: {"type": "audio", "data": "<base64_audio>"} for audio chunks
    - Client sends: {"type": "text", "message": "<text>"} for text input
    - Client sends: {"type": "end"} to end session
    - Server sends: {"type": "transcript", "text": "<transcribed_text>"} for user speech
    - Server sends: {"type": "response", "text": "<ai_response>", "audio": "<base64_audio>"}
    - Server sends: {"type": "status", "state": "listening"|"processing"|"speaking"}
    - Server sends: {"type": "error", "message": "<error_message>"}
    """
    await voice_manager.connect(websocket, session_id)
    
    channel_id = f"voice_{session_id}"
    user_id = session_id
    
    try:
        await websocket.send_json({
            "type": "status",
            "state": "connected",
            "message": "Connexion établie. Vous pouvez parler ou écrire."
        })
        
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
                
                elif msg_type == "text":
                    # Handle text message - process through chat AI
                    message = data.get("message", "").strip()
                    if not message:
                        continue
                    
                    await websocket.send_json({
                        "type": "status",
                        "state": "processing"
                    })
                    
                    # Process through CrewAI
                    response = await asyncio.to_thread(
                        process_question,
                        channel_id=channel_id,
                        user_id=user_id,
                        username="Voice User",
                        question=message
                    )
                    
                    await websocket.send_json({
                        "type": "response",
                        "text": response,
                        "audio": None  # Text-only response for now
                    })
                    
                    await websocket.send_json({
                        "type": "status",
                        "state": "listening"
                    })
                
                elif msg_type == "audio":
                    # Handle audio chunk - for future Azure Realtime integration
                    audio_data = data.get("data", "")
                    
                    # For now, acknowledge receipt - full audio processing requires
                    # Azure GPT-Realtime integration which needs browser-compatible audio
                    await websocket.send_json({
                        "type": "status",
                        "state": "processing",
                        "message": "Audio reçu, traitement en cours..."
                    })
                    
                    # TODO: Integrate with Azure GPT-Realtime for audio processing
                    # For now, we support text-based voice interactions
                    await websocket.send_json({
                        "type": "info",
                        "message": "Pour l'instant, veuillez utiliser la reconnaissance vocale de votre navigateur et envoyer le texte."
                    })
                    
                    await websocket.send_json({
                        "type": "status",
                        "state": "listening"
                    })
                
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Type de message non reconnu: {msg_type}"
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
    finally:
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
        
        if html_path.exists():
            with open(html_path, "r", encoding="utf-8") as f:
                content_html = f.read()
        elif content_markdown:
            content_html = markdown_to_html(content_markdown) if VIDEO_REPORT_AVAILABLE else content_markdown
        
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
