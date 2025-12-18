"""
AI Client for communicating with llama-server
"""
import asyncio
import aiohttp
import json
import re
from typing import Optional
from models import EmergencyMetrics, UrgencyLevel


class AIClient:
    """Client for llama-server vision model"""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Emergency-focused prompt optimized for small models (SmolVLM500M)
        self.system_prompt = """you will review still frames from traffic or outdoor incidents.

Always follow these rules:
1. PRIORITIZE PEOPLE: Describe every visible person, their injuries, blood, protective gear, trapped posture, or signs of unconsciousness. Treat ANY red/brown stains on skin, clothes, seats, or windows as BLOOD unless you can point to an obvious source like wet mud covering the entire scene or bright decorative paint on a wall. Do not guess "paint" if the stain is on a person.
2. VEHICLE CONTEXT: Note if the person is inside a vehicle, trapped by airbags/seatbelts, or ejected. Mention crumpled metal, broken glass, deployed airbags, or open doors.
3. HAZARDS: Call out fire/flames/smoke, flooding or standing water, structural damage, weapons/violence, or anything else that threatens life.
4. SEVERITY POLICY: If ANY person shows blood, severe injury, or is unconscious/pinned, the danger level must be HIGH or CRITICAL. Fires, heavy smoke, or flooding around people are also HIGH or CRITICAL.

Reply with exactly three sections:
- "DANGER SCAN:" 1-2 sentences describing people, visible injuries (if u detect red mud or paint say it's blood), and immediate threats.
- "HAZARDS:" a comma-separated list (e.g. "fire, smoke, injured_person, trapped_occupant"), or "none" if truly none.
- "DANGER LEVEL:" one of SAFE, LOW, MEDIUM, HIGH, CRITICAL followed by a short justification referencing the most serious observation.

Be decisive; err on the side of caution and never ignore bleeding or unconscious people."""
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """Close the session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def check_health(self) -> bool:
        """Check if llama-server is accessible"""
        try:
            session = await self.get_session()
            async with session.get(f"{self.base_url}/health", timeout=5) as response:
                return response.status == 200
        except Exception as e:
            print(f"Health check failed: {e}")
            return False
    
    async def send_chat_completion(self, instruction: str, image_base64: str, max_tokens: int = 300) -> str:
        """Send request to llama-server chat completions endpoint"""
        session = await self.get_session()
        
        payload = {
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instruction},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_base64}
                        }
                    ]
                }
            ]
        }
        
        try:
            async with session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=30
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Server error: {response.status} - {error_text}")
                
                data = await response.json()
                return data["choices"][0]["message"]["content"]
        
        except asyncio.TimeoutError:
            raise Exception("Request timed out")
        except Exception as e:
            raise Exception(f"API request failed: {str(e)}")
    
    def parse_emergency_response(self, response: str, timestamp: str, frame_number: int) -> EmergencyMetrics:
        """Parse AI response into structured EmergencyMetrics - hazard-based urgency calculation"""
        
        response_lower = response.lower()
        
        # Extract hazards - detect if mentioned in natural language OR in yes/no format
        detected_hazards = []
        
        # Fire detection - look for any mention of fire/flames/burning unless explicitly denied
        if ('fire' in response_lower or 'flame' in response_lower or 'burning' in response_lower or 'blaze' in response_lower):
            # Only skip if explicitly says "no fire" or "fire: no"
            if not re.search(r'(no\s+fire|fire[:\s]*no|without\s+fire)', response_lower):
                detected_hazards.append("fire")
        
        # Smoke detection - any mention of smoke/haze unless denied
        if ('smoke' in response_lower or 'smoking' in response_lower or 'smoky' in response_lower):
            if not re.search(r'(no\s+smoke|smoke[:\s]*no|without\s+smoke)', response_lower):
                detected_hazards.append("smoke")
        
        # Water/flooding - look for water damage, flooding, submerged
        if any(word in response_lower for word in ['flood', 'flooding', 'submerged', 'inundated', 'water damage']):
            if not re.search(r'(no\s+(flood|water)|flood[:\s]*no)', response_lower):
                detected_hazards.append("water")
        
        # Structural damage - broken, collapsed, debris, damaged buildings
        if any(word in response_lower for word in ['collapsed', 'debris', 'rubble', 'damaged building', 'broken structure', 'structural damage', 'crumbled', 'destroyed']):
            if not re.search(r'(no\s+damage|damage[:\s]*no|intact)', response_lower):
                detected_hazards.append("structural_damage")
        
        # Gas leak - gas, chemical, fumes
        if any(word in response_lower for word in ['gas leak', 'gas', 'chemical', 'fumes', 'toxic']):
            if not re.search(r'(no\s+gas|gas[:\s]*no)', response_lower):
                # Only add gas if there's context suggesting danger (not just "gas station")
                if any(context in response_lower for context in ['leak', 'fumes', 'toxic', 'chemical', 'danger']):
                    detected_hazards.append("gas")
        
        # Medical emergency/injuries - injured, hurt, victim, casualty
        if any(
            word in response_lower
            for word in [
                'injured',
                'injury',
                'hurt',
                'victim',
                'casualty',
                'wounded',
                'medical emergency',
                'blood',
                'bloody',
                'bleeding',
                'bloodied',
            ]
        ):
            if not re.search(r'(no\s+injur|injur[yed]*[:\s]*no|uninjured)', response_lower):
                detected_hazards.append("medical_emergency")
        
        # Violence - weapons, assault, attack, aggression
        if any(word in response_lower for word in ['weapon', 'gun', 'knife', 'assault', 'attack', 'violence', 'fighting', 'combat']):
            if not re.search(r'(no\s+(weapon|violence)|weapon[:\s]*no)', response_lower):
                detected_hazards.append("violence")
        
        # Blocked exits - blocked, obstructed, trapped
        if any(word in response_lower for word in ['blocked exit', 'obstructed', 'trapped', 'blocked path']):
            if not re.search(r'(no\s+block|block[:\s]*no|clear)', response_lower):
                detected_hazards.append("blocked_exit")
        
        # NOW calculate urgency based on detected hazards + explicit danger level
        urgency_level = UrgencyLevel.LOW
        urgency_score = 1.5
        
        # Critical hazards automatically set CRITICAL urgency
        critical_hazards = {"fire", "violence", "medical_emergency"}
        if any(h in detected_hazards for h in critical_hazards):
            urgency_level = UrgencyLevel.CRITICAL
            urgency_score = 9.5
        # High-risk hazards
        elif any(h in detected_hazards for h in {"smoke", "structural_damage", "gas"}):
            urgency_level = UrgencyLevel.HIGH
            urgency_score = 7.5
        # Medium-risk hazards
        elif any(h in detected_hazards for h in {"water", "blocked_exit"}):
            urgency_level = UrgencyLevel.MEDIUM
            urgency_score = 4.5
        # No hazards detected - check for explicit danger keywords in response
        else:
            if any(word in response_lower for word in ["critical", "extreme danger", "life threatening", "emergency"]):
                urgency_level = UrgencyLevel.CRITICAL
                urgency_score = 9.5
            elif any(word in response_lower for word in ["high danger", "high risk", "dangerous", "urgent"]):
                urgency_level = UrgencyLevel.HIGH
                urgency_score = 7.5
            elif any(word in response_lower for word in ["medium", "moderate", "caution", "some concern"]):
                urgency_level = UrgencyLevel.MEDIUM
                urgency_score = 4.5
            # Only mark as LOW if explicitly says safe/no danger
            elif any(phrase in response_lower for phrase in ["safe", "no danger", "no emergency", "normal situation"]):
                urgency_level = UrgencyLevel.LOW
                urgency_score = 1.5
        
        # Extract people count - look for numbers
        people_count = None
        people_patterns = [
            r'(\d+)\s+(?:people|person|individual)',
            r'(?:people|person)[:\s]+(\d+)',
            r'see\s+(\d+)',
            r'count[:\s]+(\d+)'
        ]
        for pattern in people_patterns:
            match = re.search(pattern, response_lower)
            if match:
                people_count = int(match.group(1))
                break
        
        # Check if "none" or "no people" mentioned
        if people_count is None:
            if any(phrase in response_lower for phrase in ["no people", "nobody", "none visible", "0 people"]):
                people_count = 0
        
        # Check for injuries - only if explicitly mentioned as yes
        visible_injuries = bool(re.search(r'injur[yed]*[:\s]*(yes|visible|present|detected)', response_lower))
        
        # Extract environmental conditions
        environmental_conditions = "Normal indoor/outdoor conditions"
        if "dark" in response_lower or "low light" in response_lower:
            environmental_conditions = "Low lighting conditions"
        elif "bright" in response_lower or "good light" in response_lower:
            environmental_conditions = "Good lighting"
        elif "smoke" in detected_hazards:
            environmental_conditions = "Poor visibility due to smoke"
        elif "rain" in response_lower or "wet" in response_lower:
            environmental_conditions = "Wet conditions"
        
        # Extract accessibility issues
        accessibility_issues = []
        if "blocked_exit" in detected_hazards:
            accessibility_issues.append("blocked_exit")
        if "debris" in response_lower or "rubble" in response_lower:
            accessibility_issues.append("debris")
        
        # Extract recommended action - look for action phrases
        recommended_action = "Monitor situation. Call emergency services if needed."
        action_sentences = []
        for sentence in response.split('.'):
            if any(keyword in sentence.lower() for keyword in [
                "should", "must", "need to", "evacuate", "call", "contact", 
                "move", "leave", "stay", "avoid", "immediately"
            ]):
                action_sentences.append(sentence.strip())
        
        if action_sentences:
            recommended_action = '. '.join(action_sentences[:2])  # Take first 2 action sentences
        elif urgency_level == UrgencyLevel.CRITICAL:
            recommended_action = "IMMEDIATE ACTION REQUIRED. Evacuate area and call emergency services NOW."
        elif urgency_level == UrgencyLevel.HIGH:
            recommended_action = "Call emergency services immediately. Ensure safety of all individuals."
        elif urgency_level == UrgencyLevel.MEDIUM:
            recommended_action = "Stay alert. Prepare to evacuate if situation worsens. Contact authorities if needed."
        
        # Scene description - first 1-2 sentences
        scene_description = '. '.join(response.split('.')[:2]).strip()
        if len(scene_description) > 250:
            scene_description = scene_description[:247] + "..."
        
        return EmergencyMetrics(
            timestamp=timestamp,
            frame_number=frame_number,
            scene_description=scene_description,
            urgency_level=urgency_level,
            urgency_score=urgency_score,
            detected_hazards=detected_hazards,
            people_count=people_count,
            visible_injuries=visible_injuries,
            environmental_conditions=environmental_conditions,
            accessibility_issues=accessibility_issues,
            recommended_action=recommended_action,
            confidence=0.8,
            raw_response=response
        )
    
    async def analyze_frame(
        self, 
        image_base64: str, 
        timestamp: str = "", 
        frame_number: int = 0
    ) -> EmergencyMetrics:
        """Analyze a frame and return structured emergency metrics"""
        
        instruction = f"""{self.system_prompt}

Analyze this frame and provide a structured emergency assessment."""
        
        response = await self.send_chat_completion(instruction, image_base64)
        
        return self.parse_emergency_response(response, timestamp, frame_number)
