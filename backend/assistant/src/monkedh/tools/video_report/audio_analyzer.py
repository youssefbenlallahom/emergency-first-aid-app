"""
Audio Analysis Module for Video Report.

Provides three-phase audio analysis:
1. Audio Classification - Segment and classify all sounds
2. Speech Transcription - Extract and transcribe speech (Groq/OpenAI)
3. Emotion Detection - Analyze emotions from speech (Hume AI)

Integrates with the main video analysis pipeline.
"""

import os
import sys
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
import re

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import audio classification and emotion modules
try:
    from .audio_classifier import SimpleAudioClassifier
    logger.info("Audio classifier module loaded")
except ImportError as e:
    logger.warning(f"Audio classifier not available: {e}")
    SimpleAudioClassifier = None

try:
    from .emotion_analyzer import SimpleEmotionAnalyzer
    logger.info("Emotion analyzer module loaded")
except ImportError as e:
    logger.warning(f"Emotion analyzer not available: {e}")
    SimpleEmotionAnalyzer = None


def extract_audio_from_video(video_path: str) -> Optional[str]:
    """
    Extract audio track from video file.
    
    Args:
        video_path: Path to video file
        
    Returns:
        Path to extracted audio file (WAV format) or None if no audio
    """
    # Try with moviepy first
    try:
        from moviepy.editor import VideoFileClip
        clip = VideoFileClip(video_path)
        
        if clip.audio is None:
            clip.close()
            logger.warning(f"No audio track found in video: {video_path}")
            return None
        
        # Create temporary WAV file
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        tmp_path = tmp.name
        tmp.close()
        
        # Export audio
        clip.audio.write_audiofile(
            tmp_path, 
            fps=16000, 
            nbytes=2, 
            codec="pcm_s16le", 
            verbose=False, 
            logger=None
        )
        clip.close()
        
        if Path(tmp_path).exists() and Path(tmp_path).stat().st_size > 0:
            logger.info(f"Audio extracted successfully to: {tmp_path}")
            return tmp_path
        
        # Clean up if failed
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return None
        
    except Exception as e:
        logger.warning(f"MoviePy extraction failed, trying ffmpeg: {e}")
        
        # Fallback to ffmpeg
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        tmp_path = tmp.name
        tmp.close()
        
        try:
            # Get ffmpeg executable
            try:
                import imageio_ffmpeg as iio_ffmpeg
                ffmpeg_bin = iio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                ffmpeg_bin = "ffmpeg"
            
            # Extract audio with ffmpeg
            subprocess.run([
                ffmpeg_bin, "-y", "-i", video_path,
                "-vn",  # No video
                "-ac", "1",  # Mono
                "-ar", "16000",  # 16kHz sample rate
                tmp_path
            ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if Path(tmp_path).exists() and Path(tmp_path).stat().st_size > 0:
                logger.info(f"Audio extracted with ffmpeg to: {tmp_path}")
                return tmp_path
            
            # Clean up if failed
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            return None
            
        except Exception as e:
            logger.error(f"Failed to extract audio with ffmpeg: {e}")
            try:
                if Path(tmp_path).exists():
                    os.unlink(tmp_path)
            except Exception:
                pass
            return None


def transcribe_audio_groq(audio_path: str, language: str = "fr") -> Optional[Dict[str, Any]]:
    """
    Transcribe audio using Groq Whisper API.
    
    Args:
        audio_path: Path to audio file
        language: Language code (fr, ar, en)
        
    Returns:
        Transcription result or None
    """
    api_key = os.getenv('GROQ_API_KEY') or os.getenv('API_KEY')
    if not api_key:
        logger.warning("No Groq API key found for transcription")
        return None
    
    try:
        from groq import Groq
        
        client = Groq(api_key=api_key)
        
        with open(audio_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-large-v3",
                language=language,
                response_format="verbose_json"
            )
        
        # Parse segments - they can be dicts or objects
        segments = []
        if hasattr(transcription, 'segments') and transcription.segments:
            for seg in transcription.segments:
                if isinstance(seg, dict):
                    segments.append({
                        "start_time": seg.get("start", 0),
                        "end_time": seg.get("end", 0),
                        "text": seg.get("text", "")
                    })
                else:
                    segments.append({
                        "start_time": getattr(seg, "start", 0),
                        "end_time": getattr(seg, "end", 0),
                        "text": getattr(seg, "text", "")
                    })
        
        return {
            "full_transcript": transcription.text,
            "language": getattr(transcription, "language", language),
            "duration": getattr(transcription, "duration", 0),
            "segments": segments
        }
        
    except Exception as e:
        logger.error(f"Groq transcription failed: {e}")
        return None


def transcribe_audio_openai(audio_path: str, language: str = "fr") -> Optional[Dict[str, Any]]:
    """
    Transcribe audio using OpenAI Whisper API.
    
    Args:
        audio_path: Path to audio file
        language: Language code
        
    Returns:
        Transcription result or None
    """
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.debug("No OpenAI API key found for transcription")
        return None
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=api_key)
        
        with open(audio_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1",
                language=language,
                response_format="verbose_json"
            )
        
        return {
            "full_transcript": transcription.text,
            "language": transcription.language,
            "duration": transcription.duration,
            "segments": [
                {
                    "start_time": seg["start"],
                    "end_time": seg["end"],
                    "text": seg["text"]
                }
                for seg in (transcription.segments or [])
            ]
        }
        
    except Exception as e:
        logger.error(f"OpenAI transcription failed: {e}")
        return None


def analyze_emotions_hume(audio_path: str) -> Optional[Dict[str, Any]]:
    """
    Analyze emotions in audio using Hume AI.
    
    Args:
        audio_path: Path to audio file
        
    Returns:
        Emotion analysis result or None
    """
    api_key = os.getenv('HUME_API_KEY')
    if not api_key:
        logger.warning("No Hume API key found for emotion analysis")
        return None
    
    try:
        import httpx
        import base64
        
        # Read and encode audio
        with open(audio_path, "rb") as f:
            audio_data = base64.b64encode(f.read()).decode()
        
        headers = {
            "X-Hume-Api-Key": api_key,
            "Content-Type": "application/json"
        }
        
        # Note: This is a simplified example. Hume's actual API may differ.
        # You may need to use their official SDK or different endpoint.
        payload = {
            "models": {
                "prosody": {}
            },
            "raw_text": False,
            "data": audio_data
        }
        
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                "https://api.hume.ai/v0/batch/jobs",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
            
    except Exception as e:
        logger.error(f"Hume emotion analysis failed: {e}")
        return None


def analyze_video_audio(video_path: str, language: str = "fr") -> Optional[Dict[str, Any]]:
    """
    Complete audio analysis workflow for a video.
    Three phases:
    1. Audio segmentation and classification
    2. Speech transcription (Groq or OpenAI)
    3. Emotion detection (from transcription text)
    
    Args:
        video_path: Path to video file
        language: Language for transcription
        
    Returns:
        Dictionary with all audio analysis results
    """
    # Extract audio from video
    audio_path = extract_audio_from_video(video_path)
    
    if not audio_path:
        logger.warning("No audio track found in video")
        return None
    
    results = {
        "has_audio": True,
        "segments": [],
        "emotions": [],
        "audio_events": []
    }
    
    try:
        logger.info("=" * 60)
        logger.info("AUDIO ANALYSIS PIPELINE")
        logger.info("=" * 60)
        
        # Load audio for analysis
        audio = None
        sr = 16000
        try:
            import librosa
            logger.info("Loading audio with librosa...")
            audio, sr = librosa.load(audio_path, sr=16000)
            logger.info(f"✓ Audio loaded: {len(audio)} samples @ {sr}Hz")
        except Exception as e:
            logger.warning(f"Librosa failed: {e}, trying scipy...")
            try:
                import numpy as np
                from scipy.io import wavfile
                sr, audio_raw = wavfile.read(audio_path)
                audio = audio_raw.astype(np.float32)
                if np.max(np.abs(audio)) > 1:
                    audio = audio / np.iinfo(audio_raw.dtype).max
                logger.info(f"✓ Audio loaded with scipy: {len(audio)} samples @ {sr}Hz")
            except Exception as e2:
                logger.error(f"Failed to load audio: {e2}")
                audio = None
        
        # PHASE 1: Audio Classification
        logger.info("\nPHASE 1: Audio Classification & Segmentation")
        logger.info("-" * 60)
        if audio is not None:
            try:
                classifier = SimpleAudioClassifier()
                classification_results = classifier.classify_audio(audio, sr)
                
                if classification_results.get('segments'):
                    results["segments"] = [
                        {
                            "start_time": seg["start_time"],
                            "end_time": seg["end_time"],
                            "label": seg["category"],
                            "confidence": seg["confidence"]
                        }
                        for seg in classification_results["segments"]
                    ]
                    logger.info(f"✓ Segmented into {len(results['segments'])} parts")
                
                if classification_results.get('top_categories'):
                    results["audio_events"] = list(classification_results["top_categories"].keys())
                    logger.info(f"✓ Detected events: {', '.join(results['audio_events'][:5])}")
                
            except Exception as e:
                logger.error(f"✗ Classification failed: {e}")
        
        # PHASE 2: Speech Transcription
        logger.info("\nPHASE 2: Speech Transcription")
        logger.info("-" * 60)
        transcription = transcribe_audio_groq(audio_path, language)
        if not transcription:
            transcription = transcribe_audio_openai(audio_path, language)
        
        if transcription:
            results["transcription"] = transcription
            results["full_transcript"] = transcription.get("full_transcript", "")
            results["duration"] = transcription.get("duration", 0)
            results["language"] = transcription.get("language", language)
            logger.info(f"✓ Transcribed: {len(results['full_transcript'])} chars")
            logger.info(f"  Text: {results['full_transcript'][:80]}...")
        else:
            logger.warning("✗ No transcription obtained")
        
        # PHASE 3: Emotion Detection
        logger.info("\nPHASE 3: Emotion Detection")
        logger.info("-" * 60)
        try:
            analyzer = SimpleEmotionAnalyzer()
            if results.get("full_transcript"):
                emotions = analyzer.analyze_text(results["full_transcript"])
                if emotions:
                    results["emotions"] = emotions
                    logger.info(f"✓ Detected emotions:")
                    for emotion in emotions:
                        logger.info(f"  - {emotion['name']}: {emotion['score']*100:.1f}%")
                else:
                    logger.warning("✗ No emotions detected")
            else:
                logger.warning("✗ No transcript for emotion analysis")
        except Exception as e:
            logger.error(f"✗ Emotion analysis failed: {e}")
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ AUDIO ANALYSIS COMPLETE")
        logger.info("=" * 60)
        return results
        
    except Exception as e:
        logger.error(f"Fatal error during audio analysis: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return results
        
    finally:
        # Clean up
        try:
            if audio_path and Path(audio_path).exists():
                os.unlink(audio_path)
                logger.debug(f"Cleaned up: {audio_path}")
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")


def format_audio_summary(results: Dict[str, Any]) -> str:
    """
    Format audio analysis results into human-readable summary with all three phases.
    
    Args:
        results: Audio analysis results dictionary
        
    Returns:
        Formatted markdown string
    """
    if not results or not results.get("has_audio"):
        return "Aucune piste audio détectée dans la vidéo."
    
    lines = []
    lines.append("## Analyse Audio")
    lines.append("")
    
    # Overview metadata
    duration = results.get('duration')
    language = results.get('language', 'N/A')
    
    if duration or language:
        lines.append("### Informations Générales")
        if duration:
            lines.append(f"- **Durée audio:** {duration:.1f} secondes")
        if language:
            lines.append(f"- **Langue détectée:** {language}")
        lines.append("")
    
    # Phase 1: Audio Segmentation/Classification
    segments = results.get('segments', [])
    if segments:
        lines.append("### Phase 1: Segmentation Audio")
        lines.append("")
        lines.append("Analyse des segments audio détectés:")
        lines.append("")
        
        # Group segments by category
        category_counts = {}
        for seg in segments:
            category = seg.get('category', 'unknown')
            category_counts[category] = category_counts.get(category, 0) + 1
        
        if category_counts:
            lines.append("**Catégories détectées:**")
            for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"- {category}: {count} segments")
            lines.append("")
        
        # Show first 15 segments with timestamps
        lines.append("**Timeline des segments:**")
        for seg in segments[:15]:
            start = seg.get('start_time', 0)
            end = seg.get('end_time', 0)
            category = seg.get('category', 'unknown')
            lines.append(f"- `[{start:.2f}s - {end:.2f}s]` {category}")
        
        if len(segments) > 15:
            lines.append(f"- *... et {len(segments) - 15} segments supplémentaires*")
        lines.append("")
    
    # Phase 2: Transcription
    full_transcript = results.get('full_transcript', '')
    if full_transcript:
        lines.append("### Phase 2: Transcription")
        lines.append("")
        lines.append("**Transcription complète:**")
        lines.append("")
        lines.append(f'> "{full_transcript}"')
        lines.append("")
    
    # Phase 3: Emotion Detection
    emotions = results.get('emotions', [])
    if emotions:
        lines.append("### Phase 3: Détection des Émotions")
        lines.append("")
        lines.append("**Émotions identifiées dans le discours:**")
        lines.append("")
        
        # Sort emotions by score
        sorted_emotions = sorted(emotions, key=lambda x: x.get('score', 0), reverse=True)
        for emotion in sorted_emotions:
            name = emotion.get('name', 'unknown')
            score = emotion.get('score', 0)
            percentage = score * 100
            # Create a simple progress bar
            bar_length = int(percentage / 5)  # 20 chars max
            bar = '█' * bar_length + '░' * (20 - bar_length)
            lines.append(f"- **{name}:** {percentage:.1f}% `{bar}`")
        lines.append("")
    
    # Audio Events (if any)
    audio_events = results.get('audio_events', [])
    if audio_events:
        lines.append("### Événements Audio Détectés")
        lines.append("")
        for event in audio_events:
            event_name = event if isinstance(event, str) else event.get('name', 'unknown')
            lines.append(f"- {event_name}")
        lines.append("")
    
    return "\n".join(lines) if lines else "Analyse audio complète, aucun contenu significatif détecté."


def correlate_audio_with_frames(
    audio_results: Dict[str, Any],
    frame_descriptions: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Correlate audio events with video frames for integrated analysis.
    
    Args:
        audio_results: Results from audio analysis
        frame_descriptions: List of frame analysis results
        
    Returns:
        List of frames with correlated audio information
    """
    if not audio_results or not frame_descriptions:
        return frame_descriptions
    
    transcription = audio_results.get('transcription', {})
    segments = transcription.get('segments', [])
    
    integrated_frames = []
    
    for frame in frame_descriptions:
        # Extract frame timestamp
        frame_time = 0.0
        if 'timestamp' in frame:
            frame_time = float(frame['timestamp'])
        elif 'frame_path' in frame:
            # Try to extract from filename like "frame_0002_t2.00s.jpg"
            match = re.search(r't(\d+\.?\d*)s', frame['frame_path'])
            if match:
                frame_time = float(match.group(1))
        
        # Find speech segments near this frame (within 1 second window)
        frame_audio = {
            'speech': None,
            'speech_text': None
        }
        
        for seg in segments:
            seg_start = seg.get('start_time', 0)
            seg_end = seg.get('end_time', 0)
            
            # Check if frame is within this speech segment
            if seg_start <= frame_time <= seg_end or abs(seg_start - frame_time) < 1.0:
                frame_audio['speech'] = True
                frame_audio['speech_text'] = seg.get('text', '')
                break
        
        # Add audio to frame
        integrated_frame = frame.copy()
        integrated_frame['audio'] = frame_audio
        integrated_frames.append(integrated_frame)
    
    return integrated_frames
