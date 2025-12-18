"""
Data models for emergency analysis
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class UrgencyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EmergencyMetrics(BaseModel):
    """emergency metrics from AI analysis"""
    timestamp: str
    frame_number: int
    scene_description: str
    urgency_level: UrgencyLevel
    urgency_score: float = Field(ge=0, le=10, description="Urgency score from 0-10")
    detected_hazards: List[str] = Field(default_factory=list)
    people_count: Optional[int] = None
    visible_injuries: bool = False
    environmental_conditions: str = ""
    accessibility_issues: List[str] = Field(default_factory=list)
    recommended_action: str = ""
    confidence: float = Field(ge=0, le=1, default=0.0)
    raw_response: str = ""


class AnalysisRequest(BaseModel):
    """Request model for frame analysis"""
    image_base64: str
    timestamp: str = ""
    frame_number: int = 0


class AnalysisResponse(BaseModel):
    """Response model for frame analysis"""
    success: bool
    metrics: Optional[EmergencyMetrics] = None
    error: Optional[str] = None


class AgentAction(BaseModel):
    """Action taken by the emergency agent"""
    tool_name: str
    tool_input: Dict[str, Any]
    tool_output: str
    timestamp: str


class AgentDecision(BaseModel):
    """Decision made by the emergency agent"""
    success: bool
    agent_response: str
    actions_taken: List[AgentAction] = Field(default_factory=list)
    reasoning: str = ""
    urgency_level: str
    urgency_score: float
    timestamp: str
    error: Optional[str] = None


class VideoAnalysisSession(BaseModel):
    """Session for tracking video analysis"""
    session_id: str
    video_path: str
    start_time: datetime
    end_time: Optional[datetime] = None
    metrics_history: List[EmergencyMetrics] = Field(default_factory=list)
    
    class Config:
        arbitrary_types_allowed = True
    
    def add_metrics(self, metrics: EmergencyMetrics):
        """Add metrics to history"""
        self.metrics_history.append(metrics)
    
    def get_summary(self) -> Dict[str, Any]:
        """Generate summary of the analysis session"""
        if not self.metrics_history:
            return {
                "session_id": self.session_id,
                "total_frames": 0,
                "max_urgency": "low",
                "average_urgency": 0.0,
                "all_hazards": [],
                "critical_moments": []
            }
        
        urgency_scores = [m.urgency_score for m in self.metrics_history]
        all_hazards = set()
        for m in self.metrics_history:
            all_hazards.update(m.detected_hazards)
        
        # Find critical moments (urgency >= 7)
        critical_moments = [
            {
                "frame": m.frame_number,
                "timestamp": m.timestamp,
                "urgency": m.urgency_score,
                "description": m.scene_description,
                "hazards": m.detected_hazards
            }
            for m in self.metrics_history if m.urgency_score >= 7.0
        ]
        
        # Find max urgency level
        max_urgency = max(self.metrics_history, key=lambda m: m.urgency_score)
        
        return {
            "session_id": self.session_id,
            "total_frames": len(self.metrics_history),
            "max_urgency_level": max_urgency.urgency_level,
            "max_urgency_score": max(urgency_scores),
            "average_urgency_score": sum(urgency_scores) / len(urgency_scores),
            "all_hazards_detected": list(all_hazards),
            "critical_moments_count": len(critical_moments),
            "critical_moments": critical_moments,
            "total_people_detected": sum(m.people_count or 0 for m in self.metrics_history),
            "injuries_detected": any(m.visible_injuries for m in self.metrics_history),
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "full_history": [m.dict() for m in self.metrics_history]
        }
