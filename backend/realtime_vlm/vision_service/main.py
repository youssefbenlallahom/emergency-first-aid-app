"""
Vision Service - VLLM Analysis Microservice
Analyzes images using SmolVLM vision model
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os

from ai_client import AIClient
from models import EmergencyMetrics

app = FastAPI(title="Vision Analysis Service")


class AnalysisRequest(BaseModel):
    image_base64: str
    timestamp: str = ""
    frame_number: int = 0


# Initialize AI client
llama_url = os.getenv("LLAMA_SERVER_URL", "http://host.docker.internal:8080")
ai_client = AIClient(base_url=llama_url)


@app.get("/health")
async def health():
    is_healthy = await ai_client.check_health()
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "vllm_connected": is_healthy,
        "service": "vision-analysis"
    }


@app.post("/analyze", response_model=EmergencyMetrics)
async def analyze_frame(request: AnalysisRequest):
    """Analyze a single frame and return emergency metrics"""
    try:
        metrics = await ai_client.analyze_frame(
            image_base64=request.image_base64,
            timestamp=request.timestamp,
            frame_number=request.frame_number
        )
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
