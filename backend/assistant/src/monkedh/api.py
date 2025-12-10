"""
FastAPI REST API for the Emergency First Aid Assistant
Provides endpoints for chat, conversation history, and health checks
"""
import os
import uuid
import base64
import asyncio
from typing import Optional, List
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path

# Load .env from the assistant directory before other imports
# api.py -> monkedh -> src -> assistant (3 parents)
import dotenv
env_path = Path(__file__).parent.parent.parent / ".env"
dotenv.load_dotenv(env_path)

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn

from monkedh.crew import Monkedh
from monkedh.tools.redis_storage import redis_memory

# Path to emergency images
EMERGENCY_IMAGES_PATH = Path(__file__).parent / "tools" / "image_suggestion" / "emergency_image_db"


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
