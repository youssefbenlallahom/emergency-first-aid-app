"""
Video Report Module for Monkedh Emergency First Aid Assistant.

This module provides video incident analysis capabilities including:
- Frame extraction from video files
- Vision AI analysis for emergency detection
- Audio analysis (classification, transcription, emotion detection)
- Comprehensive report generation (Markdown, HTML)
- Email delivery of reports

Integrated with CrewAI for multi-agent orchestration.
"""

from .frame_extractor import extract_frames, get_video_info
from .vision_client import VisionClient
from .vision_analyzer import analyze_frame, VISION_PROMPT
from .audio_analyzer import analyze_video_audio, format_audio_summary, extract_audio_from_video
from .audio_classifier import SimpleAudioClassifier
from .emotion_analyzer import SimpleEmotionAnalyzer
from .report_generator import generate_report, summarize_report
from .report_formatter import markdown_to_html
from .email_sender import EmailSender
from .crew import VideoReportCrew
from .tools import (
    FrameExtractionTool,
    VisionAnalysisTool,
    ReportGenerationTool,
    AudioAnalysisTool
)

__all__ = [
    # Core functions
    "extract_frames",
    "get_video_info",
    "VisionClient",
    "analyze_frame",
    "VISION_PROMPT",
    "analyze_video_audio",
    "format_audio_summary",
    "extract_audio_from_video",
    "generate_report",
    "summarize_report",
    "markdown_to_html",
    "EmailSender",
    # CrewAI components
    "VideoReportCrew",
    "FrameExtractionTool",
    "VisionAnalysisTool",
    "ReportGenerationTool",
    "AudioAnalysisTool",
]
