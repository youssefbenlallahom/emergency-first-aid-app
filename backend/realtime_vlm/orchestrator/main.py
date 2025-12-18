"""
Orchestrator Service - Main Backend
Coordinates vision and agent services for video analysis
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import aiohttp
import tempfile
import os

from video_processor import VideoProcessor
from models import EmergencyMetrics, UrgencyLevel


PHONE_HEALTH_INTERVAL_SECONDS = float(os.getenv("PHONE_HEALTH_INTERVAL", "3"))
PHONE_DEFAULT_PORT = os.getenv("PHONE_BRIDGE_PORT", "5005")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_phone_ip(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    if cleaned.startswith("http://"):
        cleaned = cleaned[len("http://"):]
    elif cleaned.startswith("https://"):
        cleaned = cleaned[len("https://"):]
    return cleaned.strip().rstrip("/") or None


def _phone_base_url(ip: Optional[str]) -> Optional[str]:
    if not ip:
        return None
    if ip.startswith("http://") or ip.startswith("https://"):
        return ip.rstrip("/")
    host = ip
    if "/" in host:
        host = host.split("/")[0]
    if ":" in host:
        return f"http://{ip.rstrip('/')}"
    return f"http://{host}:{PHONE_DEFAULT_PORT}"


SYSTEM_STATE = {
    "phone": {
        "connected": False,
        "ip": _normalize_phone_ip(os.getenv("PHONE_IP")),
        "last_checked": None,
        "last_error": None,
    }
}

phone_monitor_task: Optional[asyncio.Task] = None

SESSION_STREAMS: Dict[str, asyncio.Queue] = {}
SESSION_TASKS: Dict[str, asyncio.Task] = {}


def _register_session(session_id: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    SESSION_STREAMS[session_id] = queue
    return queue


def _cleanup_session(session_id: str) -> None:
    SESSION_STREAMS.pop(session_id, None)
    task = SESSION_TASKS.pop(session_id, None)
    if task and not task.done():
        task.cancel()


async def _publish_event(session_id: str, event: str, data: dict) -> None:
    queue = SESSION_STREAMS.get(session_id)
    if not queue:
        return
    await queue.put({"event": event, "data": data})

app = FastAPI(title="Emergency Video Orchestrator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _hazard_weight(hazard: str) -> float:
    weights = {
        "fire": 3.0,
        "medical_emergency": 3.0,
        "violence": 2.5,
        "smoke": 2.0,
        "structural_damage": 2.0,
        "gas": 2.0,
        "water": 1.2,
        "blocked_exit": 1.0,
    }
    return weights.get(hazard, 0.8)


def calculate_emergency_severity(metrics: EmergencyMetrics) -> float:
    hazard_score = sum(_hazard_weight(h) for h in metrics.detected_hazards)
    injury_bonus = 2.5 if metrics.visible_injuries else 0.0
    people_bonus = min(metrics.people_count or 0, 5) * 0.3
    base = metrics.urgency_score * 0.4
    severity = min(10.0, round(base + hazard_score + injury_bonus + people_bonus, 2))
    return severity


def requires_agent_dispatch(metrics: EmergencyMetrics, severity_index: float) -> bool:
    critical_hazards = {"fire", "medical_emergency"}
    has_critical_hazard = any(h in critical_hazards for h in metrics.detected_hazards)
    return bool(
        (has_critical_hazard or metrics.visible_injuries)
        and (metrics.urgency_score >= 6.0 or severity_index >= 6.5)
    )


URGENCY_PRIORITY = {
    UrgencyLevel.LOW.value: 0,
    UrgencyLevel.NORMAL.value: 1,
    UrgencyLevel.MEDIUM.value: 2,
    UrgencyLevel.HIGH.value: 3,
}


def _classify_urgency(score: Optional[float]) -> UrgencyLevel:
    if score is None:
        return UrgencyLevel.NORMAL
    if score >= 7.0:
        return UrgencyLevel.HIGH
    if score >= 5.0:
        return UrgencyLevel.MEDIUM
    if score >= 3.0:
        return UrgencyLevel.NORMAL
    return UrgencyLevel.LOW


def _resolve_urgency_label(metrics: EmergencyMetrics) -> str:
    raw_level = metrics.urgency_level
    if isinstance(raw_level, UrgencyLevel):
        level_value = raw_level.value
    else:
        level_value = str(raw_level).lower()

    if level_value == UrgencyLevel.CRITICAL.value:
        return UrgencyLevel.HIGH.value
    if level_value in URGENCY_PRIORITY:
        return level_value
    return _classify_urgency(getattr(metrics, "urgency_score", None)).value


class PhoneUpdateRequest(BaseModel):
    ip: str


class PhoneStatusResponse(BaseModel):
    connected: bool
    ip: Optional[str]
    last_checked: Optional[str]
    last_error: Optional[str]


async def _update_phone_health(force: bool = False) -> None:
    ip = SYSTEM_STATE["phone"].get("ip")
    last_checked = SYSTEM_STATE["phone"].get("last_checked")

    if last_checked and not force:
        # Avoid hammering when called externally; background loop handles cadence
        try:
            last_dt = datetime.fromisoformat(last_checked)
            if (datetime.now(timezone.utc) - last_dt).total_seconds() < PHONE_HEALTH_INTERVAL_SECONDS / 2:
                return
        except ValueError:
            pass

    if not ip:
        SYSTEM_STATE["phone"].update(
            {
                "connected": False,
                "last_checked": _now_iso(),
                "last_error": "Phone IP not configured",
            }
        )
        return

    base_url = _phone_base_url(ip)
    if not base_url:
        SYSTEM_STATE["phone"].update(
            {
                "connected": False,
                "last_checked": _now_iso(),
                "last_error": "Invalid phone IP",
            }
        )
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{base_url}/health",
                timeout=aiohttp.ClientTimeout(total=3),
            ) as resp:
                ok = resp.status == 200
                SYSTEM_STATE["phone"].update(
                    {
                        "connected": ok,
                        "last_checked": _now_iso(),
                        "last_error": None if ok else f"Unexpected status {resp.status}",
                    }
                )
                if ok:
                    return
                try:
                    detail = await resp.text()
                    SYSTEM_STATE["phone"]["last_error"] = detail[:200]
                except Exception:
                    pass
    except Exception as exc:
        SYSTEM_STATE["phone"].update(
            {
                "connected": False,
                "last_checked": _now_iso(),
                "last_error": str(exc),
            }
        )


async def _phone_health_monitor() -> None:
    try:
        while True:
            await _update_phone_health(force=True)
            await asyncio.sleep(PHONE_HEALTH_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        pass


@app.on_event("startup")
async def _startup_events():
    global phone_monitor_task
    if phone_monitor_task is None:
        phone_monitor_task = asyncio.create_task(_phone_health_monitor())


@app.on_event("shutdown")
async def _shutdown_events():
    global phone_monitor_task
    if phone_monitor_task:
        phone_monitor_task.cancel()
        try:
            await phone_monitor_task
        except asyncio.CancelledError:
            pass
        phone_monitor_task = None

def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# Service URLs
VISION_SERVICE_URL = os.getenv("VISION_SERVICE_URL", "http://vision-service:8002")
AGENT_SERVICE_URL = os.getenv("AGENT_SERVICE_URL", "http://agent-service:8001")
XAI_SERVICE_URL = os.getenv("XAI_SERVICE_URL", "http://xai-service:8004")
XAI_REQUEST_GRID = int(os.getenv("XAI_REQUEST_GRID", "8"))
XAI_ENABLED = _env_flag("XAI_ENABLED", True)


@app.get("/")
async def root():
    return {"message": "Emergency Video Orchestrator", "status": "running"}


@app.get("/health")
async def health():
    """Check health of all services"""
    health_status = {"status": "healthy", "services": {}}
    
    # Check vision service
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{VISION_SERVICE_URL}/health", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                if resp.status == 200:
                    vision_health = await resp.json()
                    health_status["services"]["vision"] = "healthy"
                    health_status["llama_server"] = vision_health.get("vllm_connected", False)
                else:
                    health_status["services"]["vision"] = "unhealthy"
                    health_status["llama_server"] = False
    except:
        health_status["services"]["vision"] = "unreachable"
        health_status["llama_server"] = False
    
    # Check agent service  
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{AGENT_SERVICE_URL}/health", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                if resp.status == 200:
                    health_status["services"]["agent"] = "healthy"
                else:
                    health_status["services"]["agent"] = "unhealthy"
    except:
        health_status["services"]["agent"] = "unreachable"

    health_status["services"]["xai"] = "enabled" if XAI_ENABLED else "disabled"
    
    # Overall status
    if any(v != "healthy" for v in health_status["services"].values()):
        health_status["status"] = "degraded"
    
    await _update_phone_health()
    health_status["phone"] = SYSTEM_STATE["phone"]
    return health_status


@app.get("/phone/status", response_model=PhoneStatusResponse)
async def get_phone_status():
    await _update_phone_health()
    state = SYSTEM_STATE["phone"]
    return PhoneStatusResponse(
        connected=state.get("connected", False),
        ip=state.get("ip"),
        last_checked=state.get("last_checked"),
        last_error=state.get("last_error"),
    )


@app.post("/phone/update_ip")
async def update_phone_ip(request: PhoneUpdateRequest):
    normalized_ip = _normalize_phone_ip(request.ip)
    if not normalized_ip:
        raise HTTPException(status_code=400, detail="Invalid IP address")
    SYSTEM_STATE["phone"]["ip"] = normalized_ip
    os.environ["PHONE_IP"] = normalized_ip
    await _update_phone_health(force=True)
    return {"saved": True, "ip": normalized_ip}


def _format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _request_xai_heatmap(
    image_base64: str,
    frame_number: int,
    timestamp: str,
    scene_description: str,
    detected_hazards: List[str],
) -> dict:
    if not XAI_ENABLED:
        raise RuntimeError("XAI attribution is disabled")
    payload = {
        "image_base64": image_base64,
        "frame_number": frame_number,
        "timestamp": timestamp,
        "scene_description": scene_description,
        "detected_hazards": detected_hazards,
        "grid_size": XAI_REQUEST_GRID,
    }
    timeout = aiohttp.ClientTimeout(total=45)
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{XAI_SERVICE_URL}/analyze", json=payload, timeout=timeout
        ) as resp:
            if resp.status != 200:
                detail = await resp.text()
                raise RuntimeError(
                    f"XAI service error {resp.status}: {detail[:200]}"
                )
            return await resp.json()


@app.get("/stream/video/{session_id}")
async def stream_video_updates(session_id: str):
    queue = SESSION_STREAMS.get(session_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        try:
            while True:
                payload = await queue.get()
                event = payload.get("event", "message")
                data = payload.get("data", {})
                yield _format_sse(event, data)
                if event == "end":
                    break
        except asyncio.CancelledError:
            raise

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/analyze/frame", response_model=EmergencyMetrics)
async def analyze_single_frame(request: dict):
    """Analyze a single frame - proxies to vision service"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{VISION_SERVICE_URL}/analyze", json=request) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise HTTPException(status_code=resp.status, detail=f"Vision service error: {error_text}")
                
                metrics_data = await resp.json()
                return EmergencyMetrics(**metrics_data)
    except aiohttp.ClientError as e:
        raise HTTPException(status_code=503, detail=f"Vision service unavailable: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/video-emergency")
async def analyze_video_emergency(file: UploadFile = File(...)):
    """Initialize a video analysis session and stream results via SSE"""

    session_id = str(uuid.uuid4())
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        _register_session(session_id)
        task = asyncio.create_task(_process_video_session(session_id, tmp_file_path))
        SESSION_TASKS[session_id] = task

        return {"session_id": session_id, "status": "processing"}
    except Exception as exc:
        _cleanup_session(session_id)
        raise HTTPException(status_code=500, detail=str(exc))


async def _process_video_session(session_id: str, video_path: str) -> None:
    processor: Optional[VideoProcessor] = None
    try:
        processor = VideoProcessor(video_path)
        video_info = processor.get_video_info()
        all_metrics: List[EmergencyMetrics] = []
        critical_incidents: List[dict] = []
        max_severity = 0.0
        total_hazards = set()
        severity_scores: List[float] = []
        dispatch_candidates: List[Tuple[EmergencyMetrics, float]] = []
        urgency_timeline: List[dict] = []
        best_metrics_entry: Optional[Tuple[EmergencyMetrics, float]] = None
        urgency_counts = {level: 0 for level in URGENCY_PRIORITY.keys()}
        max_urgency_label = UrgencyLevel.LOW.value
        xai_analysis: Optional[dict] = None

        frame_count = 0
        async for frame_data in processor.extract_frames(interval_seconds=1.0):
            frame_count += 1

            async with aiohttp.ClientSession() as session:
                payload = {
                    "image_base64": frame_data["image_base64"],
                    "timestamp": frame_data["timestamp"],
                    "frame_number": frame_data["frame_number"],
                }
                async with session.post(f"{VISION_SERVICE_URL}/analyze", json=payload) as resp:
                    if resp.status != 200:
                        continue
                    metrics_data = await resp.json()
                    metrics = EmergencyMetrics(**metrics_data)

            severity_index = calculate_emergency_severity(metrics)
            severity_scores.append(severity_index)
            if severity_index >= max_severity:
                max_severity = severity_index
            if best_metrics_entry is None or severity_index > best_metrics_entry[1]:
                best_metrics_entry = (metrics, severity_index)
            all_metrics.append(metrics)
            total_hazards.update(metrics.detected_hazards)

            urgency_label = _resolve_urgency_label(metrics)
            urgency_counts[urgency_label] = urgency_counts.get(urgency_label, 0) + 1
            if URGENCY_PRIORITY.get(urgency_label, 0) >= URGENCY_PRIORITY.get(max_urgency_label, 0):
                max_urgency_label = urgency_label

            dispatch_recommended = requires_agent_dispatch(metrics, severity_index)
            if dispatch_recommended:
                dispatch_candidates.append((metrics, severity_index))

            frame_event = {
                "session_id": session_id,
                "frame_number": metrics.frame_number,
                "timestamp": metrics.timestamp,
                "urgency_level": urgency_label,
                "scene_description": metrics.scene_description,
                "detected_hazards": metrics.detected_hazards,
                "people_count": metrics.people_count,
                "visible_injuries": metrics.visible_injuries,
                "dispatch_recommended": dispatch_recommended,
                "recommended_action": metrics.recommended_action,
            }
            await _publish_event(session_id, "frame", frame_event)

            high_or_above = URGENCY_PRIORITY.get(urgency_label, 0) >= URGENCY_PRIORITY.get(UrgencyLevel.HIGH.value, 3)
            if high_or_above or severity_index >= 6.0:
                incident_entry = {
                    "timestamp": frame_data["timestamp"],
                    "frame_number": frame_data["frame_number"],
                    "urgency_level": urgency_label,
                    "scene_description": metrics.scene_description,
                    "detected_hazards": metrics.detected_hazards,
                    "people_count": metrics.people_count,
                    "visible_injuries": metrics.visible_injuries,
                    "dispatch_recommended": dispatch_recommended,
                }
                critical_incidents.append(incident_entry)
                await _publish_event(session_id, "incident", incident_entry)

                should_trigger_xai = (
                    xai_analysis is None
                    and (
                        URGENCY_PRIORITY.get(urgency_label, 0)
                        >= URGENCY_PRIORITY.get(UrgencyLevel.HIGH.value, 3)
                        or severity_index >= 7.0
                        or metrics.visible_injuries
                    )
                )
                if should_trigger_xai and XAI_ENABLED:
                    try:
                        xai_analysis = await _request_xai_heatmap(
                            image_base64=frame_data["image_base64"],
                            frame_number=metrics.frame_number,
                            timestamp=metrics.timestamp,
                            scene_description=metrics.scene_description,
                            detected_hazards=metrics.detected_hazards,
                        )
                        incident_entry["xai_analysis"] = xai_analysis
                        xai_event = {
                            "session_id": session_id,
                            "frame_number": metrics.frame_number,
                            "timestamp": metrics.timestamp,
                            "grid_size": xai_analysis.get("grid_size"),
                            "heatmap_image_base64": xai_analysis.get(
                                "heatmap_image_base64"
                            ),
                            "cells": xai_analysis.get("cells", []),
                            "explanation": xai_analysis.get("explanation", ""),
                            "max_score": xai_analysis.get("max_score", 0.0),
                        }
                        await _publish_event(session_id, "xai_heatmap", xai_event)
                    except Exception as xai_error:
                        await _publish_event(
                            session_id,
                            "xai_error",
                            {
                                "frame_number": metrics.frame_number,
                                "timestamp": metrics.timestamp,
                                "detail": str(xai_error),
                            },
                        )
                elif should_trigger_xai and not XAI_ENABLED:
                    await _publish_event(
                        session_id,
                        "xai_disabled",
                        {
                            "frame_number": metrics.frame_number,
                            "timestamp": metrics.timestamp,
                            "reason": "XAI attribution disabled via environment variable",
                        },
                    )

            urgency_point = {
                "timestamp": metrics.timestamp,
                "frame_number": metrics.frame_number,
                "urgency_level": urgency_label,
                "scene_description": metrics.scene_description,
                "detected_hazards": metrics.detected_hazards,
            }
            urgency_timeline.append(urgency_point)

        # Calculate statistics
        avg_severity = sum(severity_scores) / len(severity_scores) if severity_scores else 0.0
        high_frames = urgency_counts.get(UrgencyLevel.HIGH.value, 0)
        medium_frames = urgency_counts.get(UrgencyLevel.MEDIUM.value, 0)
        normal_frames = urgency_counts.get(UrgencyLevel.NORMAL.value, 0)
        low_frames = urgency_counts.get(UrgencyLevel.LOW.value, 0)

        threat_level = max_urgency_label
        if frame_count > 0:
            dominant_label = max(
                urgency_counts.items(),
                key=lambda item: (item[1], URGENCY_PRIORITY.get(item[0], 0)),
            )[0]
        else:
            dominant_label = UrgencyLevel.LOW.value

        emergency_responses = []
        selected_metrics: Optional[EmergencyMetrics] = None
        selected_severity = 0.0
        should_invoke_agent = bool(dispatch_candidates)
        if not should_invoke_agent and best_metrics_entry:
            should_invoke_agent = best_metrics_entry[1] >= 5.0
        if should_invoke_agent and best_metrics_entry:
            if dispatch_candidates:
                selected_metrics, selected_severity = max(dispatch_candidates, key=lambda item: item[1])
            else:
                selected_metrics, selected_severity = best_metrics_entry

        if selected_metrics:
            try:
                async with aiohttp.ClientSession() as session:
                    agent_payload = {
                        "urgency_score": selected_metrics.urgency_score,
                        "urgency_level": selected_metrics.urgency_level.value,
                        "scene_description": selected_metrics.scene_description,
                        "detected_hazards": selected_metrics.detected_hazards,
                        "people_count": selected_metrics.people_count,
                        "visible_injuries": selected_metrics.visible_injuries,
                        "timestamp": selected_metrics.timestamp,
                        "frame_number": selected_metrics.frame_number,
                        "severity_index": selected_severity,
                    }
                    async with session.post(f"{AGENT_SERVICE_URL}/analyze", json=agent_payload) as resp:
                        if resp.status == 200:
                            agent_result = await resp.json()
                            emergency_responses = agent_result.get("emergency_calls", [])
                            for incident in critical_incidents:
                                if incident["frame_number"] == selected_metrics.frame_number:
                                    incident["agent_response"] = agent_result.get("agent_response", "")
                                    incident["actions_taken"] = agent_result.get("actions_taken", [])
                                    break
                            agent_actions = agent_result.get("actions_taken", [])
                            agent_event = {
                                "session_id": session_id,
                                "frame_number": selected_metrics.frame_number,
                                "agent_response": agent_result.get("agent_response", ""),
                                "emergency_responses": emergency_responses,
                                "actions_taken": agent_actions,
                                "tool_calls": agent_actions,
                            }
                            await _publish_event(session_id, "agent_call", agent_event)
                            for emergency_call in emergency_responses:
                                tool_event = {
                                    "session_id": session_id,
                                    "frame_number": selected_metrics.frame_number,
                                    **emergency_call,
                                }
                                await _publish_event(session_id, "tool_call", tool_event)
            except Exception as agent_error:
                print(f"Agent dispatch error: {agent_error}")

        report = {
            "session_id": session_id,
            "video_info": video_info,
            "analysis_summary": {
                "total_frames_analyzed": frame_count,
                "threat_level": threat_level,
                "dominant_urgency_level": dominant_label,
                "high_urgency_frames": high_frames,
                "medium_urgency_frames": medium_frames,
                "normal_urgency_frames": normal_frames,
                "low_urgency_frames": low_frames,
                "max_severity_index": round(max_severity, 2),
                "average_severity_index": round(avg_severity, 2),
                "unique_hazards_detected": list(total_hazards),
                "total_incidents": len(critical_incidents),
                "requires_immediate_response": bool(dispatch_candidates),
                "phone_bridge_connected": SYSTEM_STATE["phone"].get("connected", False),
                "phone_bridge_ip": SYSTEM_STATE["phone"].get("ip"),
            },
            "emergency_responses": emergency_responses,
            "critical_incidents": critical_incidents,
            "urgency_timeline": urgency_timeline,
            "xai_analysis": xai_analysis,
            "xai_enabled": XAI_ENABLED,
        }

        await _publish_event(session_id, "complete", report)

    except Exception as exc:
        await _publish_event(session_id, "error", {"detail": str(exc)})
    finally:
        if processor:
            processor.release()
        if os.path.exists(video_path):
            os.remove(video_path)
        await _publish_event(session_id, "end", {"session_id": session_id})
        _cleanup_session(session_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
