"""
Emotion Detection Module for Video Report
Analyzes emotional content from audio transcriptions
"""

import logging
import os
import base64
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class SimpleEmotionAnalyzer:
    """
    Emotion analyzer for audio segments and transcriptions
    Uses Hume AI API or fallback keyword-based analysis
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize emotion analyzer"""
        self.api_key = api_key or os.getenv('HUME_API_KEY')
        self.hume_available = bool(self.api_key and self.api_key != 'your-hume-api-key-here')
        logger.info(f"Emotion analyzer initialized. Hume available: {self.hume_available}")
    
    def _fallback_emotion_detection(self, text: str) -> List[Dict[str, Any]]:
        """
        Fallback emotion detection based on text analysis
        Uses keyword matching for sentiment analysis
        
        Args:
            text: Transcribed text
            
        Returns:
            List of emotions with confidence scores
        """
        # Define emotion keywords
        emotions_keywords = {
            "urgence": ["urgent", "urgence", "danger", "aide", "secours", "appel", "emergency"],
            "panique": ["panique", "peur", "terreur", "horrifié", "choc"],
            "calme": ["calme", "tranquille", "serein", "cool", "relaxe"],
            "determiné": ["décidé", "determiné", "résolu", "volonté"],
            "empathie": ["merci", "s'il vous plaît", "svp", "aide", "assistance", "comprendre"],
            "confusion": ["quoi", "pourquoi", "comment", "confus", "problème", "erreur"]
        }
        
        text_lower = text.lower() if text else ""
        emotion_scores = {}
        
        # Count keyword matches
        for emotion, keywords in emotions_keywords.items():
            count = sum(1 for keyword in keywords if keyword in text_lower)
            emotion_scores[emotion] = min(0.1 + (count * 0.15), 0.95)  # Cap at 0.95
        
        # Normalize scores
        total_score = sum(emotion_scores.values())
        if total_score > 0:
            emotion_scores = {e: s/total_score for e, s in emotion_scores.items()}
        else:
            emotion_scores = {e: 1/len(emotions_keywords) for e in emotions_keywords}
        
        # Return as list sorted by score
        return [
            {"name": emotion, "score": score}
            for emotion, score in sorted(emotion_scores.items(), key=lambda x: x[1], reverse=True)
            if score > 0.05  # Only include emotions with meaningful scores
        ]
    
    def analyze_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Analyze emotions from transcribed text
        
        Args:
            text: Transcribed text
            
        Returns:
            List of emotions with scores
        """
        if not text:
            return []
        
        # For now, use fallback (Hume async job is too complex for synchronous API)
        logger.info("Analyzing emotions from transcription...")
        emotions = self._fallback_emotion_detection(text)
        logger.info(f"✓ Emotion analysis complete: {[e['name'] for e in emotions[:3]]}")
        return emotions
    
    def analyze_multiple_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze emotions in multiple text segments
        
        Args:
            segments: List of segment dictionaries with 'text' field
            
        Returns:
            List of emotion analysis results
        """
        results = []
        
        for segment in segments:
            try:
                text = segment.get('text', '')
                start_time = segment.get('start_time', 0)
                end_time = segment.get('end_time', 0)
                
                emotions = self.analyze_text(text)
                
                if emotions:
                    results.append({
                        "start_time": start_time,
                        "end_time": end_time,
                        "text": text,
                        "emotions": emotions
                    })
            except Exception as e:
                logger.error(f"Error analyzing segment: {e}")
        
        return results

