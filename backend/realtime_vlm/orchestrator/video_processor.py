"""
Video processing utilities
"""
import cv2
import base64
import numpy as np
from typing import AsyncGenerator, Dict, Any
import asyncio
from datetime import timedelta


class VideoProcessor:
    """Process video files and extract frames"""
    
    def __init__(self, video_path: str):
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)
        
        if not self.cap.isOpened():
            raise Exception(f"Could not open video file: {video_path}")
        
        # Get video properties
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration = self.total_frames / self.fps if self.fps > 0 else 0
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    def get_video_info(self) -> Dict[str, Any]:
        """Get video metadata"""
        return {
            "fps": self.fps,
            "total_frames": self.total_frames,
            "duration_seconds": self.duration,
            "width": self.width,
            "height": self.height,
            "duration_formatted": str(timedelta(seconds=int(self.duration)))
        }
    
    def frame_to_base64(self, frame: np.ndarray, quality: int = 80) -> str:
        """Convert frame to base64 JPEG"""
        # Encode frame as JPEG
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        _, buffer = cv2.imencode('.jpg', frame, encode_param)
        
        # Convert to base64
        jpg_as_text = base64.b64encode(buffer).decode('utf-8')
        return f"data:image/jpeg;base64,{jpg_as_text}"
    
    async def extract_frames(
        self, 
        interval_seconds: float = 1.0,
        max_frames: int = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Extract frames at specified intervals
        
        Args:
            interval_seconds: Time interval between frames
            max_frames: Maximum number of frames to extract (None for all)
        
        Yields:
            Dict with frame data including base64 image, timestamp, and frame number
        """
        if self.fps <= 0:
            raise Exception("Invalid FPS value")
        
        # Calculate frame interval
        frame_interval = max(1, int(self.fps * interval_seconds))
        
        frame_count = 0
        extracted_count = 0
        
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Reset to beginning
        
        while True:
            ret, frame = self.cap.read()
            
            if not ret:
                break
            
            # Process frame at intervals
            if frame_count % frame_interval == 0:
                # Calculate timestamp
                timestamp_seconds = frame_count / self.fps
                timestamp = str(timedelta(seconds=int(timestamp_seconds)))
                
                # Convert to base64
                image_base64 = self.frame_to_base64(frame)
                
                yield {
                    "frame_number": frame_count,
                    "timestamp": timestamp,
                    "timestamp_seconds": timestamp_seconds,
                    "image_base64": image_base64
                }
                
                extracted_count += 1
                
                if max_frames and extracted_count >= max_frames:
                    break
                
                # Small delay to prevent overwhelming the system
                await asyncio.sleep(0.01)
            
            frame_count += 1
    
    def extract_frame_at(self, frame_number: int) -> Dict[str, Any]:
        """Extract a specific frame by number"""
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = self.cap.read()
        
        if not ret:
            raise Exception(f"Could not read frame {frame_number}")
        
        timestamp_seconds = frame_number / self.fps
        timestamp = str(timedelta(seconds=int(timestamp_seconds)))
        
        return {
            "frame_number": frame_number,
            "timestamp": timestamp,
            "timestamp_seconds": timestamp_seconds,
            "image_base64": self.frame_to_base64(frame)
        }
    
    def release(self):
        """Release video capture resources"""
        if self.cap:
            self.cap.release()
    
    def __del__(self):
        self.release()
