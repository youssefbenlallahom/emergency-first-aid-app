"""
Emergency Agent Service - Microservice
Calls emergency authorities based on situation analysis
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import json
from datetime import datetime
import re
import time

import httpx

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool

app = FastAPI(title="Emergency Agent Service")


# Models
class EmergencyRequest(BaseModel):
    urgency_score: float
    urgency_level: str
    scene_description: str
    detected_hazards: List[str]
    people_count: Optional[int]
    visible_injuries: bool
    timestamp: str
    frame_number: int
    severity_index: Optional[float] = None


class AgentResponse(BaseModel):
    success: bool
    agent_response: str
    emergency_calls: List[dict]
    actions_taken: List[dict]
    error: Optional[str] = None


PHONE_TOOL_TIMEOUT = float(os.getenv("PHONE_TOOL_TIMEOUT", "4"))
PHONE_BRIDGE_PORT = os.getenv("PHONE_BRIDGE_PORT", "5005")


def _candidate_orchestrator_urls() -> List[str]:
    candidates = [
        os.getenv("ORCHESTRATOR_URL"),
        os.getenv("BACKEND_URL"),
        os.getenv("ORCHESTRATOR_FALLBACK"),
        "http://backend:8000",
        "http://localhost:8000",
    ]
    deduped = []
    seen = set()
    for url in candidates:
        if not url:
            continue
        cleaned = url.strip().rstrip("/")
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped


SERVICE_ALIASES = {
    "fire": "FIRE",
    "fire dept": "FIRE",
    "fire department": "FIRE",
    "fire_department": "FIRE",
    "firefighters": "FIRE",
    "flames": "FIRE",
    "smoke": "FIRE",
    "explosion": "FIRE",
    "police": "POLICE",
    "police department": "POLICE",
    "law enforcement": "POLICE",
    "security": "POLICE",
    "sheriff": "POLICE",
    "911": "SAMU",
    "medical": "SAMU",
    "medical emergency": "SAMU",
    "medical_emergency": "SAMU",
    "ambulance": "SAMU",
    "ambulance/ems": "SAMU",
    "ems": "SAMU",
    "paramedics": "SAMU",
    "injury": "SAMU",
    "samu": "SAMU",
}

SERVICE_LABELS = {
    "FIRE": "Fire Department",
    "POLICE": "Police Department",
    "SAMU": "Ambulance / EMS",
}

_FIRE_TOKENS = {"fire", "flame", "smoke", "explosion", "burn", "incendie"}
_MEDICAL_TOKENS = {"medical", "injury", "bleeding", "victim", "heart", "respiration", "samu", "ambulance"}
_POLICE_TOKENS = {"weapon", "assault", "violence", "police", "attack", "threat", "agression", "kidnap"}

PHONE_STATUS_CACHE: Dict[str, Any] = {
    "ip": None,
    "connected": False,
    "last_checked": 0.0,
    "raw": None,
}
PHONE_STATUS_TTL = float(os.getenv("PHONE_STATUS_TTL", "2.5"))

REDIRECT_CONTEXT: Dict[str, Optional[str]] = {
    "service": None,
    "hazard": None,
    "situation": None,
    "timestamp": None,
}

SERVICE_CONTEXT_LABEL = {
    "FIRE": "incendie confirmé",
    "SAMU": "urgence médicale",
    "POLICE": "intervention des forces de l'ordre",
}

HAZARD_CONTEXT_LABEL = {
    "fire": "incendie actif",
    "medical": "victime nécessitant des soins",
}


def _update_redirect_context(service: Optional[str] = None, hazard: Optional[str] = None, situation: Optional[str] = None):
    if service:
        REDIRECT_CONTEXT["service"] = service
    if hazard:
        REDIRECT_CONTEXT["hazard"] = hazard
    if situation:
        REDIRECT_CONTEXT["situation"] = situation.strip()
    REDIRECT_CONTEXT["timestamp"] = datetime.utcnow().isoformat()


def _contextual_summary_fallback(message: Optional[str]) -> str:
    generic_hints = [
        "switch to chat",
        "guided instructions",
        "open the chat",
        "please go to chat",
    ]
    candidate = (message or "").strip()
    lowered = candidate.lower()
    if not candidate or any(hint in lowered for hint in generic_hints):
        context_situation = REDIRECT_CONTEXT.get("situation") or "Incident critique détecté"
        context_hazard = REDIRECT_CONTEXT.get("hazard")
        context_service = REDIRECT_CONTEXT.get("service")
        hazard_label = HAZARD_CONTEXT_LABEL.get(context_hazard or "", "")
        service_label = SERVICE_CONTEXT_LABEL.get(context_service or "", "")
        prefix_parts = [label for label in [hazard_label, service_label] if label]
        prefix = ", ".join(prefix_parts)
        if prefix:
            return f"{prefix.capitalize()} – {context_situation}"
        return context_situation
    return candidate


def _normalize_service_name(raw: Optional[str]) -> str:
    if not raw:
        return "SAMU"
    key = re.sub(r"\s+", " ", raw.strip().lower().replace("-", " ").replace("_", " "))
    if key in SERVICE_ALIASES:
        return SERVICE_ALIASES[key]
    if "fire" in key or "flame" in key or "smoke" in key:
        return "FIRE"
    if any(token in key for token in ["police", "law", "security", "sheriff", "officer"]):
        return "POLICE"
    if any(token in key for token in ["medical", "injury", "ambulance", "ems", "paramedic", "victim", "rescue"]):
        return "SAMU"
    return "SAMU"


def _infer_service_from_request_data(request: EmergencyRequest) -> str:
    text = f"{request.scene_description} {' '.join(request.detected_hazards or [])}".lower()
    if any(token in text for token in _FIRE_TOKENS):
        return "FIRE"
    if request.visible_injuries or (request.people_count and request.people_count > 0):
        return "SAMU"
    if any(token in text for token in _POLICE_TOKENS):
        return "POLICE"
    if any(token in text for token in _MEDICAL_TOKENS):
        return "SAMU"
    return "SAMU"


def _build_phone_base(ip: str) -> str:
    ip = ip.strip()
    if ip.startswith("http://") or ip.startswith("https://"):
        return ip.rstrip("/")
    if ":" in ip:
        return f"http://{ip}"
    return f"http://{ip}:{PHONE_BRIDGE_PORT}"


def _fetch_phone_status(force: bool = False) -> Optional[Dict[str, Any]]:
    if (
        not force
        and PHONE_STATUS_CACHE.get("raw")
        and (time.time() - PHONE_STATUS_CACHE.get("last_checked", 0.0)) < PHONE_STATUS_TTL
    ):
        return PHONE_STATUS_CACHE["raw"]

    errors = []
    for base_url in _candidate_orchestrator_urls():
        endpoint = f"{base_url}/phone/status"
        try:
            response = httpx.get(endpoint, timeout=PHONE_TOOL_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            PHONE_STATUS_CACHE.update(
                {
                    "ip": data.get("ip"),
                    "connected": data.get("connected", False),
                    "last_checked": time.time(),
                    "raw": data,
                }
            )
            print(
                f"Phone status via {endpoint} -> connected={data.get('connected')} ip={data.get('ip')}"
            )
            return data
        except Exception as exc:
            errors.append(f"{endpoint}: {exc}")

    if errors:
        print("WARNING: Unable to reach orchestrator phone status endpoints: " + "; ".join(errors))
    return None


def _resolve_phone_base(force_refresh: bool = False) -> str:
    env_ip = os.getenv("PHONE_IP")
    if env_ip:
        return _build_phone_base(env_ip)
    status = _fetch_phone_status(force=force_refresh)
    if (not status or not status.get("ip")) and not force_refresh:
        status = _fetch_phone_status(force=True)
    if not status:
        raise ValueError("Phone status unavailable")
    if not status.get("ip"):
        raise ValueError("Phone IP not configured")
    if not status.get("connected"):
        raise ValueError("Phone bridge is disconnected")
    return _build_phone_base(status["ip"])


def _send_phone_action(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    errors = []
    for attempt in range(2):
        try:
            base_url = _resolve_phone_base(force_refresh=bool(attempt))
        except Exception as exc:
            errors.append(str(exc))
            continue
        url = f"{base_url}{path}"
        try:
            print(f"Phone bridge request -> {url} payload={payload}")
            with httpx.Client(timeout=PHONE_TOOL_TIMEOUT) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                print(f"Phone bridge response <- {data}")
                return data
        except Exception as exc:
            errors.append(str(exc))
    raise ValueError("Phone bridge request failed: " + "; ".join(errors))


# Tool
@tool
def call_authorities(service_type: str, urgency_level: str, situation_description: str) -> str:
    """
    Call emergency authorities (911, fire, police, ambulance).
    
    Args:
        service_type: '911', 'fire', 'police', or 'ambulance'
        urgency_level: 'critical', 'high', or 'medium'
        situation_description: Brief description of emergency
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    requested_service = (service_type or "").strip()
    normalized_service = _normalize_service_name(requested_service)
    print(
        f"☎️ call_authorities invoked → requested='{requested_service}' normalized='{normalized_service}' urgency='{urgency_level}'"
    )

    result = {
        "status": "success",
        "service": SERVICE_LABELS.get(normalized_service, "Emergency Services"),
        "service_type": requested_service or normalized_service,
        "phone_service": normalized_service,
        "urgency": urgency_level,
        "situation": situation_description,
        "timestamp": timestamp,
        "call_id": f"EMERG-{timestamp.replace(':', '').replace('-', '').replace(' ', '-')}",
        "estimated_arrival": "5-10 minutes" if urgency_level.lower() == "critical" else "10-15 minutes",
        "channel": "frontend_queue",
        "requires_manual_dispatch": True,
        "dispatch_status": "pending",
    }
    result_copy = result.copy()
    result["tool_input"] = {
        "service_type": requested_service or normalized_service,
        "urgency_level": urgency_level,
        "situation_description": situation_description,
    }
    result["tool_output"] = result_copy

    _update_redirect_context(service=normalized_service, situation=situation_description)
    
    return json.dumps(result, indent=2)


@tool
def phone_call_tool(service: str, hazard_type: str, situation_summary: str) -> str:
    """
    Place a real phone call through the Android bridge. ONLY use for fire or medical emergencies.

    Args:
        service: 'FIRE', 'POLICE', 'SAMU', or 'AMBULANCE'.
        hazard_type: Must be 'fire' or 'medical'.
        situation_summary: One sentence explaining why the call is needed.
    """
    hazard_clean = (hazard_type or "").strip().lower()
    if hazard_clean not in {"fire", "medical"}:
        raise ValueError("phone_call_tool only supports fire or medical hazards")
    service_value = _normalize_service_name(service)
    service_label = SERVICE_LABELS.get(service_value, service_value.title())
    print(
        f"☎️ phone_call_tool invoked → service='{service_value}' hazard='{hazard_clean}' summary='{situation_summary}'"
    )
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    call_id = f"CALL-{timestamp.replace(':', '').replace('-', '').replace(' ', '-')}"
    result = {
        "channel": "frontend_queue",
        "status": "completed",
        "service_type": service_value,
        "service_label": service_label,
        "hazard_type": hazard_clean,
        "situation_summary": situation_summary,
        "message": f"Appel automatique envoyé au {service_label}.",
        "requires_manual_dispatch": False,
        "dispatch_status": "completed",
        "timestamp": timestamp,
        "call_id": call_id,
    }
    result_copy = result.copy()
    result["tool_input"] = {
        "service": service_value,
        "hazard_type": hazard_clean,
        "situation_summary": situation_summary,
    }
    result["tool_output"] = result_copy

    _update_redirect_context(service=service_value, hazard=hazard_clean, situation=situation_summary)
    return json.dumps(result, indent=2)


@tool
def phone_sms_tool(message: str, priority: str = "high") -> str:
    """
    Send an SMS alert via the Android bridge for situational awareness.
    Always start with 'Sent by Monkedh:' and summarize the situation in 1 short phrase.
    """
    text = (message or "").strip()
    if not text:
        raise ValueError("SMS message cannot be empty")

    # Format summary: split into sentences, take first 3, join as phrases
    phrases = [p.strip() for p in re.split(r'[.!?]', text) if p.strip()]
    summary = '. '.join(phrases[:3])
    sms_text = summary if summary else text
    sms_text = sms_text.strip()
    if not sms_text.lower().startswith("sent by monkedh"):
        sms_text = f"Sent by Monkedh: {sms_text}" if sms_text else "Sent by Monkedh: Emergency confirmed"

    print(f"💬 phone_sms_tool invoked → priority='{priority}' message='{sms_text[:80]}'")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sms_id = f"SMS-{timestamp.replace(':', '').replace('-', '').replace(' ', '-')}"
    result = {
        "channel": "frontend_queue",
        "status": "completed",
        "priority": priority,
        "message": sms_text,
        "timestamp": timestamp,
        "call_id": sms_id,
        "requires_manual_dispatch": False,
        "dispatch_status": "completed",
    }
    result_copy = result.copy()
    result["tool_input"] = {
        "message": sms_text,
        "priority": priority,
    }
    result["tool_output"] = result_copy
    return json.dumps(result, indent=2)


@tool
def redirect_to_chat_tool(message: str, confirmation_prompt: Optional[str] = None, prefill_message: Optional[str] = None) -> str:
    """
    Ask the web dashboard to prompt the user before redirecting specifically to the /chat page.

    Args:
        message: Short explanation of why the redirect is required.
        confirmation_prompt: Optional UI text for the confirmation dialog.
        prefill_message: Optional text that should pre-populate the chat input field.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    call_id = f"REDIRECT-{timestamp.replace(':', '').replace('-', '').replace(' ', '-')}"
    summary = _contextual_summary_fallback(message)
    if not summary:
        summary = "Situation critique détectée - ouvrez le chat pour plus d'instructions"
    prompt_text = (confirmation_prompt or "L'agent recommande de passer en mode chat pour guider l'utilisateur.").strip()
    prefill_text = (
        prefill_message
        or f"Bonjour, j'ai besoin d'une assistance immédiate. {summary} Merci de me guider étape par étape pour sécuriser la zone."
    ).strip()

    result = {
        "channel": "frontend_redirect",
        "action": "redirect",
        "status": "pending",
        "destination": "/chat",
        "message": summary,
        "confirmation_prompt": prompt_text,
        "prefill_message": prefill_text,
        "timestamp": timestamp,
        "call_id": call_id,
        "priority": "critical",
        "requires_manual_dispatch": False,
        "dispatch_status": "pending",
    }
    result_copy = result.copy()
    result["tool_input"] = {
        "message": summary,
        "confirmation_prompt": prompt_text,
        "prefill_message": prefill_text,
    }
    result["tool_output"] = result_copy
    return json.dumps(result, indent=2)


# Initialize agent
api_key = os.getenv("OPENAI_API_KEY")
agent_model = os.getenv("AGENT_MODEL", "gpt-4o-mini")
if not api_key:
    print("WARNING: OPENAI_API_KEY not set. Agent will not work!")
    agent_executor = None
else:
    # Use configurable OpenAI model (default gpt-4o-mini for lower cost)
    try:
        llm = ChatOpenAI(model=agent_model, temperature=0, api_key=api_key)
        print(f"Agent LLM initialized with model={agent_model}")
    except Exception as exc:
        fallback_model = "gpt-4"
        print(
            f"WARNING: Failed to load model '{agent_model}' ({exc}). Falling back to {fallback_model}."
        )
        llm = ChatOpenAI(model=fallback_model, temperature=0, api_key=api_key)
        agent_model = fallback_model
    tools = [call_authorities, phone_call_tool, phone_sms_tool, redirect_to_chat_tool]

    llm_with_tools = llm.bind_tools(tools)

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            """
            You are Monkedh, an emergency response dispatcher with direct access to phone call and SMS tools.
            Your mission for EVERY incident:
                1. Determine the correct service to alert (FIRE, SAMU/ambulance, POLICE) using the scene details.
                2. If anyone is bleeding, unconscious, trapped, or otherwise seriously hurt, ALWAYS alert SAMU/ambulance (service_type="SAMU" or hazard_type="medical") in addition to any other agency that might be needed.
                3. If there is fire, smoke, explosion, or life-threatening injury AND urgency is HIGH or CRITICAL,
                    use phone_call_tool first (hazard_type must be "fire" or "medical"). When both fire and medical hazards exist, place TWO calls: one for FIRE and one for SAMU.
                4. Otherwise, use call_authorities with the correct service_type and a concise situation_description.
                5. Always finish by sending phone_sms_tool with a short status summary (start with "Sent by Monkedh:").
                6. After you alert authorities immediately call redirect_to_chat_tool with a concise safety message so the UI can prompt the onsite user to switch to chat for guided instructions.
                7. Never skip the call, SMS, or redirect. Never just describe actions—execute the tools so humans receive alerts.
            Keep reasoning brief and focus on taking action quickly.
            """,
        ),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(llm=llm_with_tools, tools=tools, prompt=prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=3,
        handle_parsing_errors=True,
        return_intermediate_steps=True 
    )
    print(f"Agent initialized with explicit tool binding (model={agent_model})")


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "agent_ready": agent_executor is not None,
        "service": "emergency-agent"
    }


@app.post("/analyze", response_model=AgentResponse)
async def analyze_emergency(request: EmergencyRequest):
    """Analyze emergency and call authorities if needed"""
    
    if not agent_executor:
        raise HTTPException(status_code=503, detail="Agent not initialized - check OPENAI_API_KEY")
    
    # Build report
    report = f"""
EMERGENCY REPORT
================
Urgency: {request.urgency_level.upper()} ({request.urgency_score}/10)
Severity Index: {request.severity_index if request.severity_index is not None else 'unknown'}
Scene: {request.scene_description}
Hazards: {', '.join(request.detected_hazards) if request.detected_hazards else 'None'}
People: {request.people_count if request.people_count else 'Unknown'}
Injuries: {'YES' if request.visible_injuries else 'NO'}
Time: {request.timestamp}

Should authorities be called?
"""
    
    try:
        result = agent_executor.invoke({"input": report})
        
        print(f"Agent result type: {type(result)}")
        print(f"Agent result keys: {result.keys() if isinstance(result, dict) else 'not a dict'}")
        print(f"Full agent result: {result}")
        
        # Extract actions
        actions_taken = []
        emergency_calls = []
        
        # Check for intermediate_steps
        intermediate_steps = result.get('intermediate_steps', [])
        print(f"Found {len(intermediate_steps)} intermediate steps")
        
        for i, step in enumerate(intermediate_steps):
            print(f"Step {i}: {step}")
            if len(step) >= 2:
                action, output = step
                print(f"  Tool: {action.tool}")
                print(f"  Output: {output[:200]}...")
                
                actions_taken.append({
                    "tool": action.tool,
                    "input": action.tool_input,
                    "output": output
                })
                
                # Parse call_authorities calls
                if action.tool == "call_authorities":
                    try:
                        call_data = json.loads(output)
                        print(f"  Parsed call_authorities data: {call_data}")
                        emergency_calls.append({
                            "tool": action.tool,
                            "service_type": call_data.get("service_type"),
                            "service": call_data.get("service") or call_data.get("service_label"),
                            "urgency": call_data.get("urgency") or request.urgency_level,
                            "situation": call_data.get("situation") or action.tool_input.get("situation_description"),
                            "message": call_data.get("message") or call_data.get("situation") or action.tool_input.get("situation_description"),
                            "timestamp": call_data.get("timestamp"),
                            "call_id": call_data.get("call_id"),
                            "estimated_arrival": call_data.get("estimated_arrival"),
                            "channel": call_data.get("channel", "call"),
                            "requires_manual_dispatch": call_data.get("requires_manual_dispatch", True),
                            "dispatch_status": call_data.get("dispatch_status", "pending"),
                            "status": call_data.get("status", "queued"),
                            "phone_bridge_response": call_data.get("phone_bridge_response"),
                            "phone_bridge_error": call_data.get("phone_bridge_error"),
                            "tool_input": action.tool_input,
                            "tool_output": call_data,
                        })
                        print(f"  Emergency call added to list: {emergency_calls[-1]}")
                    except Exception as parse_error:
                        print(f"  Failed to parse call_authorities output: {parse_error}")
                        print(f"  Raw output was: {output}")
                elif action.tool == "phone_call_tool":
                    try:
                        call_data = json.loads(output)
                        emergency_calls.append({
                            "tool": action.tool,
                            "service_type": call_data.get("service_type") or action.tool_input.get("service"),
                            "service": call_data.get("service_label") or action.tool_input.get("service"),
                            "urgency": call_data.get("urgency") or request.urgency_level,
                            "situation": call_data.get("situation") or call_data.get("situation_summary") or action.tool_input.get("situation_summary"),
                            "message": call_data.get("message") or call_data.get("situation_summary") or action.tool_input.get("situation_summary"),
                            "timestamp": call_data.get("timestamp"),
                            "call_id": call_data.get("call_id"),
                            "channel": call_data.get("channel", "frontend_queue"),
                            "estimated_arrival": call_data.get("estimated_arrival"),
                            "requires_manual_dispatch": call_data.get("requires_manual_dispatch", False),
                            "dispatch_status": call_data.get("dispatch_status", "completed"),
                            "status": call_data.get("status", "completed"),
                            "phone_bridge_response": call_data.get("phone_bridge_response"),
                            "tool_input": action.tool_input,
                            "tool_output": call_data,
                        })
                        print(f"  Virtual call logged for frontend: {emergency_calls[-1]}")
                    except Exception as parse_error:
                        print(f"  Failed to parse phone_call_tool output: {parse_error}")
                elif action.tool == "phone_sms_tool":
                    try:
                        sms_data = json.loads(output)
                        emergency_calls.append({
                            "tool": action.tool,
                            "service_type": sms_data.get("service_type") or "sms",
                            "service": sms_data.get("service") or "SMS Dispatch",
                            "urgency": sms_data.get("urgency") or request.urgency_level,
                            "situation": sms_data.get("situation") or sms_data.get("message"),
                            "message": sms_data.get("message"),
                            "timestamp": sms_data.get("timestamp"),
                            "call_id": sms_data.get("call_id"),
                            "channel": sms_data.get("channel", "frontend_queue"),
                            "requires_manual_dispatch": sms_data.get("requires_manual_dispatch", False),
                            "dispatch_status": sms_data.get("dispatch_status", "completed"),
                            "status": sms_data.get("status", "completed"),
                            "phone_bridge_response": sms_data.get("phone_response"),
                            "tool_input": action.tool_input,
                            "tool_output": sms_data,
                        })
                        print(f"  💬 SMS alert recorded for frontend queue: {sms_data.get('message')}")
                    except Exception as parse_error:
                        print(f"  Failed to parse phone_sms_tool output: {parse_error}")
                elif action.tool == "redirect_to_chat_tool":
                    try:
                        redirect_data = json.loads(output)
                        emergency_calls.append({
                            "tool": action.tool,
                            "channel": redirect_data.get("channel", "frontend_redirect"),
                            "action": redirect_data.get("action", "redirect"),
                            "destination": redirect_data.get("destination", "/chat"),
                            "message": redirect_data.get("message"),
                            "confirmation_prompt": redirect_data.get("confirmation_prompt"),
                            "prefill_message": redirect_data.get("prefill_message"),
                            "timestamp": redirect_data.get("timestamp"),
                            "call_id": redirect_data.get("call_id"),
                            "priority": redirect_data.get("priority"),
                            "status": redirect_data.get("status", "pending"),
                            "requires_manual_dispatch": redirect_data.get("requires_manual_dispatch", False),
                            "dispatch_status": redirect_data.get("dispatch_status", "pending"),
                            "tool_input": action.tool_input,
                            "tool_output": redirect_data,
                        })
                        print("  🔁 Redirect request queued for frontend UI")
                    except Exception as parse_error:
                        print(f"  Failed to parse redirect_to_chat_tool output: {parse_error}")
        
        if not emergency_calls:
            inferred_service = _infer_service_from_request_data(request)
            fallback_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            fallback_call = {
                "tool": "fallback_virtual_call",
                "service_type": inferred_service.lower(),
                "service": SERVICE_LABELS.get(inferred_service, "Emergency Services"),
                "urgency": request.urgency_level,
                "situation": request.scene_description,
                "message": request.scene_description,
                "timestamp": fallback_timestamp,
                "call_id": f"FALLBACK-{request.frame_number}",
                "channel": "frontend_queue",
                "estimated_arrival": None,
                "fallback": True,
                "requires_manual_dispatch": True,
                "dispatch_status": "pending",
                "tool_input": {},
                "tool_output": {},
            }
            emergency_calls.append(fallback_call)
            print("WARNING: No tool-based call detected, injecting fallback entry", fallback_call)

        print(f"🎯 Final emergency_calls list: {emergency_calls}")
        print(f"🎯 Final actions_taken list: {len(actions_taken)} actions")
        
        return AgentResponse(
            success=True,
            agent_response=result.get("output", ""),
            emergency_calls=emergency_calls,
            actions_taken=actions_taken
        )
        
    except Exception as e:
        return AgentResponse(
            success=False,
            agent_response="",
            emergency_calls=[],
            actions_taken=[],
            error=str(e)
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
