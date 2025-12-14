"""CrewAI tools for video analysis pipeline."""
from typing import Type, List, Dict, Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from .frame_extractor import extract_frames, get_video_info
from .vision_analyzer import analyze_frame, analyze_frames_batch
from .report_generator import summarize_report, generate_report
from .audio_analyzer import analyze_video_audio, format_audio_summary
from .vision_client import VisionClient


# Input schemas
class FrameExtractorInput(BaseModel):
    """Input schema for frame extraction tool."""
    video_path: str = Field(..., description="Path to video file")
    every_n_seconds: float = Field(default=2.0, description="Extract one frame every N seconds")


class VisionAnalysisInput(BaseModel):
    """Input schema for vision analysis tool."""
    frame_paths: List[str] = Field(..., description="List of frame paths to analyze")
    language: str = Field(default="français", description="Language for analysis (français or english)")


class ReportGenerationInput(BaseModel):
    """Input schema for report generation tool."""
    descriptions: List[Dict[str, Any]] = Field(..., description="Frame descriptions from vision analysis")
    audio_results: Dict[str, Any] = Field(default=None, description="Optional audio analysis results")
    language: str = Field(default="français", description="Report language (français or arabe)")


class AudioAnalysisInput(BaseModel):
    """Input schema for audio analysis tool."""
    video_path: str = Field(..., description="Path to video file for audio extraction and analysis")
    language: str = Field(default="fr", description="Language code for transcription (fr, ar, en)")


class VideoInfoInput(BaseModel):
    """Input schema for video info tool."""
    video_path: str = Field(..., description="Path to video file")


# Tools
class FrameExtractionTool(BaseTool):
    """Tool for extracting frames from video files."""
    
    name: str = "extract_frames"
    description: str = "Extracts frames from video at specified intervals. Returns list of frame image paths."
    args_schema: Type[BaseModel] = FrameExtractorInput
    
    def _run(self, video_path: str, every_n_seconds: float = 2.0) -> List[str]:
        """Extract frames from video.
        
        Args:
            video_path: Path to video file
            every_n_seconds: Sampling rate in seconds
            
        Returns:
            List of paths to extracted frame images
        """
        print(f"\n🎬 Extracting frames: {video_path} (every {every_n_seconds}s)")
        frame_paths = extract_frames(video_path, every_n_seconds)
        print(f"✅ Extracted {len(frame_paths)} frames\n")
        return frame_paths


class VisionAnalysisTool(BaseTool):
    """Tool for analyzing frames using vision AI."""
    
    name: str = "analyze_frames"
    description: str = "Analyzes video frames using vision AI to detect incidents, people, dangers, and emergency situations."
    args_schema: Type[BaseModel] = VisionAnalysisInput
    
    def _run(self, frame_paths: List[str], language: str = "français") -> List[Dict[str, Any]]:
        """Analyze frames with vision AI.
        
        Args:
            frame_paths: List of frame image paths
            language: Language for analysis
            
        Returns:
            List of frame descriptions
        """
        print(f"\n🔍 Analyzing {len(frame_paths)} frames with Vision AI...\n")
        client = VisionClient(provider="llava")
        
        descriptions = analyze_frames_batch(
            frame_paths,
            vision_client=client,
            language=language
        )
        
        print(f"\n✅ Vision analysis complete\n")
        return descriptions


class ReportGenerationTool(BaseTool):
    """Tool for generating incident reports from analysis results."""
    
    name: str = "generate_report"
    description: str = "Generates comprehensive incident report from frame descriptions and optional audio analysis."
    args_schema: Type[BaseModel] = ReportGenerationInput
    
    def _run(
        self, 
        descriptions: List[Dict[str, Any]], 
        audio_results: Dict[str, Any] = None,
        language: str = "français"
    ) -> str:
        """Generate incident report.
        
        Args:
            descriptions: Frame analysis results
            audio_results: Optional audio analysis results
            language: Report language
            
        Returns:
            Path to generated report
        """
        lang_display = "arabe" if language == "arabe" else "français"
        print(f"\n📝 Génération du rapport en {lang_display}...\n")
        
        client = VisionClient(provider="llava")
        md_path, html_path = summarize_report(
            descriptions, 
            audio_results=audio_results,
            vision_client=client,
            language=language
        )
        
        print(f"✅ Rapport sauvegardé: {md_path}\n")
        if html_path:
            print(f"✅ Rapport HTML: {html_path}\n")
        
        return md_path


class AudioAnalysisTool(BaseTool):
    """Tool for analyzing audio from video files."""
    
    name: str = "analyze_audio"
    description: str = "Analyzes audio from video: extracts audio track, transcribes speech, and detects emotions."
    args_schema: Type[BaseModel] = AudioAnalysisInput
    
    def _run(self, video_path: str, language: str = "fr") -> str:
        """Analyze audio from video.
        
        Args:
            video_path: Path to video file
            language: Language code for transcription
            
        Returns:
            Formatted audio analysis summary
        """
        print(f"\n🎧 Analyzing audio from video: {video_path}\n")
        
        results = analyze_video_audio(video_path, language=language)
        
        if not results:
            print("⚠️ No audio found or analysis failed\n")
            return "No audio track detected in the video or audio analysis is not available."
        
        summary = format_audio_summary(results)
        
        print(f"✅ Audio analysis complete\n")
        return summary


class VideoInfoTool(BaseTool):
    """Tool for getting video metadata."""
    
    name: str = "get_video_info"
    description: str = "Gets video metadata including FPS, duration, resolution, and frame count."
    args_schema: Type[BaseModel] = VideoInfoInput
    
    def _run(self, video_path: str) -> Dict[str, Any]:
        """Get video information.
        
        Args:
            video_path: Path to video file
            
        Returns:
            Dictionary with video metadata
        """
        print(f"\n📹 Getting video info: {video_path}\n")
        info = get_video_info(video_path)
        print(f"✅ Video info retrieved: {info['duration']:.2f}s, {info['width']}x{info['height']}\n")
        return info
