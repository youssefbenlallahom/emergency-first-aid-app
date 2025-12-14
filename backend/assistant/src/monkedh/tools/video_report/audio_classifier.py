"""
Audio Classification Module for Video Report
Detects sound categories and segments in audio
"""

import logging
import numpy as np
from typing import Dict, List, Any, Optional
import warnings

logger = logging.getLogger(__name__)
warnings.filterwarnings('ignore')


class SimpleAudioClassifier:
    """
    Lightweight audio classifier for sound detection
    Segments audio and provides classification metadata
    """
    
    def __init__(self):
        """Initialize the audio classifier"""
        self.device = None
        self.model = None
        self.feature_extractor = None
        self._load_model()
    
    def _load_model(self):
        """Load AST model for audio classification - with graceful fallback"""
        try:
            import torch
            from transformers import ASTForAudioClassification, AutoFeatureExtractor
            
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            model_name = "MIT/ast-finetuned-audioset-10-10-0.4593"
            
            logger.info(f"Loading audio classification model on {self.device}...")
            self.model = ASTForAudioClassification.from_pretrained(model_name)
            self.feature_extractor = AutoFeatureExtractor.from_pretrained(model_name)
            self.model.to(self.device)
            self.model.eval()
            logger.info("✓ Audio classification model loaded")
            
        except Exception as e:
            logger.warning(f"Could not load ML model: {e}. Using fallback analysis.")
            self.model = None
    
    def segment_audio(self, audio: np.ndarray, sr: int = 16000, 
                     segment_length: float = 1.0) -> List[tuple]:
        """
        Segment audio into chunks for classification
        
        Args:
            audio: Audio samples
            sr: Sample rate
            segment_length: Length of each segment in seconds
            
        Returns:
            List of (start_sample, end_sample, start_time, end_time) tuples
        """
        segment_samples = int(segment_length * sr)
        segments = []
        
        for start in range(0, len(audio), segment_samples):
            end = min(start + segment_samples, len(audio))
            start_time = start / sr
            end_time = end / sr
            segments.append((start, end, start_time, end_time))
        
        return segments
    
    def _classify_with_model(self, audio_segment: np.ndarray, sr: int = 16000) -> Dict[str, float]:
        """Use actual ML model for classification"""
        try:
            import torch
            
            with torch.no_grad():
                inputs = self.feature_extractor(
                    audio_segment,
                    sampling_rate=sr,
                    return_tensors="pt"
                )
                
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                outputs = self.model(**inputs)
                logits = outputs.logits
                
                probs = torch.nn.functional.softmax(logits, dim=-1)
                top_probs, top_indices = torch.topk(probs, 5)
                
                predictions = {}
                for prob, idx in zip(top_probs[0], top_indices[0]):
                    label = self.model.config.id2label[int(idx)]
                    predictions[label] = float(prob)
                
                return predictions
        except Exception as e:
            logger.error(f"Model classification error: {e}")
            return {}
    
    def _classify_fallback(self, audio_segment: np.ndarray) -> str:
        """Simple fallback classification based on audio properties"""
        try:
            # Check for silence
            rms = np.sqrt(np.mean(audio_segment**2))
            if rms < 0.01:
                return "silence"
            
            # Check for high frequency content (voice)
            fft = np.abs(np.fft.fft(audio_segment))
            freq_centroid = np.average(np.arange(len(fft)), weights=fft)
            if freq_centroid > 500:
                return "speech"
            else:
                return "audio"
        except:
            return "audio"
    
    def classify_segment(self, audio_segment: np.ndarray, sr: int = 16000) -> str:
        """
        Classify a single audio segment
        
        Args:
            audio_segment: Audio chunk
            sr: Sample rate
            
        Returns:
            Classification label
        """
        if self.model is not None:
            predictions = self._classify_with_model(audio_segment, sr)
            if predictions:
                top_pred = max(predictions.items(), key=lambda x: x[1])
                return top_pred[0]
        
        # Fallback to simple analysis
        return self._classify_fallback(audio_segment)
    
    def classify_audio(self, audio: np.ndarray, sr: int = 16000) -> Dict[str, Any]:
        """
        Classify entire audio file
        
        Args:
            audio: Audio samples
            sr: Sample rate
            
        Returns:
            Dictionary with classification results and segments
        """
        # Segment audio
        segments = self.segment_audio(audio, sr)
        results = []
        categories = {}
        
        logger.info(f"Classifying {len(segments)} audio segments...")
        
        # Classify each segment
        for i, (start, end, start_time, end_time) in enumerate(segments):
            segment = audio[start:end]
            category = self.classify_segment(segment, sr)
            
            confidence = 0.8 if self.model else 0.6  # Lower confidence for fallback
            
            results.append({
                "start_time": start_time,
                "end_time": end_time,
                "category": category,
                "confidence": confidence
            })
            
            # Aggregate categories
            if category not in categories:
                categories[category] = 0
            categories[category] += 1
        
        # Sort by frequency
        top_categories = dict(sorted(
            categories.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5])
        
        # Check for speech
        has_speech = any("speech" in cat.lower() or "voice" in cat.lower() 
                        for cat in categories.keys())
        
        logger.info(f"✓ Classification complete: {len(results)} segments, categories: {list(top_categories.keys())}")
        
        return {
            "segments": results,
            "top_categories": top_categories,
            "has_speech": has_speech,
            "speech_confidence": 0.7 if has_speech else 0.0
        }

