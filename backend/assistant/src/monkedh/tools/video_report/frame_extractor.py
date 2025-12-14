"""Video frame extraction utility using OpenCV."""
import os
import logging
from pathlib import Path
from typing import List

import cv2

logger = logging.getLogger(__name__)


def extract_frames(
    video_path: str,
    every_n_seconds: float = 2.0,
    output_dir: str = None
) -> List[str]:
    """Extract frames from video at specified interval.
    
    Args:
        video_path: Path to input video file
        every_n_seconds: Extract one frame every N seconds
        output_dir: Directory to save extracted frames (defaults to output/frames)
        
    Returns:
        List of paths to extracted frame images
    """
    logger.info(f"Extracting frames from: {video_path}")
    logger.info(f"Sampling rate: 1 frame every {every_n_seconds} seconds")
    
    # Default output directory
    if output_dir is None:
        output_dir = Path(__file__).parent / "output" / "frames"
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Clear existing frames
    for existing_file in output_path.glob("frame_*.jpg"):
        try:
            existing_file.unlink()
        except Exception:
            pass
    
    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video file: {video_path}")
    
    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    
    logger.info(f"Video properties: {fps:.2f} FPS, {total_frames} frames, {duration:.2f}s duration")
    
    # Calculate frame interval
    frame_interval = int(fps * every_n_seconds)
    if frame_interval < 1:
        frame_interval = 1
    
    frame_paths = []
    frame_count = 0
    saved_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Save frame at interval
            if frame_count % frame_interval == 0:
                timestamp = frame_count / fps
                frame_filename = f"frame_{saved_count:04d}_t{timestamp:.2f}s.jpg"
                frame_path = output_path / frame_filename
                
                cv2.imwrite(str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                frame_paths.append(str(frame_path))
                
                logger.info(f"Saved frame {saved_count + 1}: {frame_filename}")
                saved_count += 1
            
            frame_count += 1
    
    finally:
        cap.release()
    
    logger.info(f"Extraction complete: {saved_count} frames saved to {output_dir}")
    return frame_paths


def get_video_info(video_path: str) -> dict:
    """Get video metadata.
    
    Args:
        video_path: Path to video file
        
    Returns:
        Dict with fps, total_frames, duration, width, height
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video file: {video_path}")
    
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps if fps > 0 else 0
        
        return {
            "fps": fps,
            "total_frames": total_frames,
            "duration": duration,
            "width": width,
            "height": height
        }
    finally:
        cap.release()
