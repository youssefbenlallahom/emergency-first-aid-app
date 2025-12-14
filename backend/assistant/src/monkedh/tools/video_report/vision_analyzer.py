"""Vision analysis module for frame-by-frame video analysis."""
import logging
from typing import Dict, Any

from .vision_client import VisionClient

logger = logging.getLogger(__name__)


VISION_PROMPT = """Analyze this image from a surveillance or incident video for emergency response purposes.

Provide a detailed description focusing on:

1. **People**: Count and describe their positions, actions, and state (standing, sitting, on ground, in distress, injured)

2. **Safety hazards**: Presence of smoke, fire, accident indicators, dangerous situations, blood, injuries visible

3. **Emergency indicators**: 
   - Signs of cardiac arrest (person collapsed, unresponsive)
   - Choking incidents
   - Bleeding or wounds
   - Burns or fire-related injuries
   - Breathing difficulties
   - Unconsciousness

4. **Actions**: What people are doing (calling emergency services, helping someone, performing CPR, running, etc.)

5. **Environment**: General context and setting (indoor/outdoor, location type, lighting conditions)

Be specific and factual. If someone appears to be in distress (lying on ground, injured, needing help), explicitly state this with details about their condition and position.

This analysis will be used by medical emergency responders to assess the situation.
"""

VISION_PROMPT_FR = """Analyse cette image d'une vidéo de surveillance ou d'incident pour la réponse aux urgences.

Fournis une description détaillée en te concentrant sur :

1. **Personnes** : Compte et décris leurs positions, actions et état (debout, assis, au sol, en détresse, blessé)

2. **Dangers de sécurité** : Présence de fumée, feu, indicateurs d'accident, situations dangereuses, sang, blessures visibles

3. **Indicateurs d'urgence** :
   - Signes d'arrêt cardiaque (personne effondrée, non réactive)
   - Incidents d'étouffement
   - Saignements ou plaies
   - Brûlures ou blessures liées au feu
   - Difficultés respiratoires
   - Inconscience

4. **Actions** : Ce que font les personnes (appel aux services d'urgence, aide à quelqu'un, pratique du RCP, fuite, etc.)

5. **Environnement** : Contexte général et cadre (intérieur/extérieur, type de lieu, conditions d'éclairage)

Sois spécifique et factuel. Si quelqu'un semble en détresse (au sol, blessé, ayant besoin d'aide), indique-le explicitement avec des détails sur son état et sa position.

Cette analyse sera utilisée par les intervenants d'urgence médicale pour évaluer la situation.
"""


def analyze_frame(
    image_path: str,
    vision_client: VisionClient = None,
    prompt: str = None,
    language: str = "français"
) -> Dict[str, Any]:
    """Analyze a single frame using vision model.
    
    Args:
        image_path: Path to frame image
        vision_client: VisionClient instance (creates new if None)
        prompt: Analysis prompt (uses default if None)
        language: Language for prompt ("français" or "english")
        
    Returns:
        Dict containing frame_path, description, and status
    """
    if vision_client is None:
        vision_client = VisionClient(provider="llava")
    
    if prompt is None:
        prompt = VISION_PROMPT_FR if language == "français" else VISION_PROMPT
    
    logger.info(f"Analyzing frame: {image_path}")
    
    try:
        description = vision_client.analyze_image(image_path, prompt)
        
        result = {
            "frame_path": image_path,
            "description": description,
            "status": "success"
        }
        
        logger.info(f"Analysis complete for: {image_path}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to analyze {image_path}: {e}")
        return {
            "frame_path": image_path,
            "description": f"Error: {str(e)}",
            "status": "error"
        }


def analyze_frames_batch(
    frame_paths: list,
    vision_client: VisionClient = None,
    language: str = "français",
    progress_callback: callable = None
) -> list:
    """Analyze multiple frames.
    
    Args:
        frame_paths: List of paths to frame images
        vision_client: VisionClient instance
        language: Language for analysis
        progress_callback: Optional callback(current, total) for progress updates
        
    Returns:
        List of analysis results
    """
    if vision_client is None:
        vision_client = VisionClient(provider="llava")
    
    results = []
    total = len(frame_paths)
    
    for i, frame_path in enumerate(frame_paths):
        result = analyze_frame(
            frame_path,
            vision_client,
            language=language
        )
        results.append(result)
        
        if progress_callback:
            progress_callback(i + 1, total)
    
    return results
