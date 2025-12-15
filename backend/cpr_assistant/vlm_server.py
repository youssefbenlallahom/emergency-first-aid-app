#!/usr/bin/env python3
"""
VLM server using University's hosted LLaVA-1.5-7b-hf endpoint
Provides real AI-powered visual analysis of CPR technique
"""
import os
import base64
import requests
import random
from flask import Flask, request, jsonify
from pyngrok import ngrok
from dotenv import load_dotenv

load_dotenv()
NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTHTOKEN")
VLLM_API_KEY = os.getenv("VLLM_API_KEY")
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "https://hosted_vllm")  # Add base URL to .env

if not NGROK_AUTH_TOKEN:
    raise RuntimeError("Missing NGROK_AUTHTOKEN in environment")
if not VLLM_API_KEY:
    print("⚠️  WARNING: No VLLM_API_KEY found - will use fallback mode")
    USE_VLM = False
else:
    USE_VLM = True
    print(f"✅ Using VLM endpoint: {VLLM_BASE_URL}/llava-1.5-7b-hf/v1/chat/completions")

FLASK_PORT = int(os.getenv("FLASK_PORT", 8001))

# ---------- University LLaVA Helper -------------------------------------------
def ask_llava(b64_image: str, prompt: str) -> str:
    """Call university's hosted LLaVA-1.5-7b-hf endpoint"""
    headers = {
        "Authorization": f"Bearer {VLLM_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llava-hf/llava-1.5-7b-hf",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}
                    }
                ]
            }
        ],
        "max_tokens": 50,
        "temperature": 0.7
    }
    
    url = f"{VLLM_BASE_URL}/llava-1.5-7b-hf/v1/chat/completions"
    
    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=20,
        verify=True  # Set to False if SSL issues
    )
    response.raise_for_status()
    
    result = response.json()
    return result["choices"][0]["message"]["content"].strip()

# ---------- CPR Coaching Logic ------------------------------------------------
class ExpertCPRCoach:
    def __init__(self):
        self.advice_history = []

    def _create_prompt(self, scores: dict) -> str:
        """Create contextual prompt based on scores"""
        arm = scores.get('arm_score', 100)
        rate = scores.get('rate_cpm', 110)
        depth = scores.get('depth_score', 100)
        hand_pos = scores.get('hand_position_score', 100)
        
        # Identify main issue
        if arm < 60:
            focus = f"bras pliés (score: {arm}%) - besoin de coudes verrouillés à 180°"
        elif rate < 100:
            focus = f"rythme trop lent à {rate}/min - besoin de 100-120/min"
        elif rate > 120:
            focus = f"rythme trop rapide à {rate}/min - ralentir à 100-120/min"
        elif depth < 70:
            focus = f"profondeur insuffisante (score: {depth}%) - pousser 5-6cm"
        elif hand_pos < 70:
            focus = f"position des mains incorrecte (score: {hand_pos}%)"
        else:
            focus = "technique correcte, maintenez la qualité"
        
        prompt = f"""Tu es un instructeur CPR expert. Analyse cette image de réanimation cardio-pulmonaire.

Problème identifié: {focus}

Donne UNE instruction courte et précise en français (maximum 15 mots) pour corriger ce problème.
Sois direct et actionnable. Ne mentionne pas les scores."""
        
        return prompt

    def _get_fallback_advice(self, scores: dict) -> str:
        """Smart fallback advice in French"""
        arm = scores.get('arm_score', 100)
        rate = scores.get('rate_cpm', 110)
        depth = scores.get('depth_score', 100)
        hand_pos = scores.get('hand_position_score', 100)
        
        # Find worst metric
        if arm < 60:
            options = [
                "Verrouillez vos coudes complètement - bras tendus",
                "Redressez vos bras - utilisez le poids de votre corps",
                "Coudes droits à 180 degrés - ne pliez pas"
            ]
        elif rate < 100:
            options = [
                f"Accélérez à 110 compressions par minute",
                "Plus rapide - comptez à voix haute",
                "Rythme trop lent - suivez le métronome"
            ]
        elif rate > 120:
            options = [
                "Ralentissez à 110 par minute",
                "Trop rapide - chantez 'Staying Alive'",
                "Moins vite - contrôlez le rythme"
            ]
        elif depth < 70:
            options = [
                "Poussez plus fort - 5-6 centimètres minimum",
                "Profondeur insuffisante - enfoncez davantage",
                "Utilisez votre poids pour comprimer plus"
            ]
        elif hand_pos < 70:
            options = [
                "Centrez vos mains sur le sternum",
                "Repositionnez au milieu de la poitrine",
                "Mains trop décalées - ajustez"
            ]
        else:
            options = [
                "Excellente technique - continuez ainsi",
                "Parfait - maintenez cette qualité",
                "Très bonne forme - bras droits, bon rythme"
            ]
        
        # Avoid repetition
        available = [a for a in options if a not in self.advice_history[-2:]]
        if not available:
            available = options
        
        advice = random.choice(available)
        self.advice_history.append(advice)
        if len(self.advice_history) > 6:
            self.advice_history.pop(0)
        
        return advice

    def advise(self, image_b64: str, scores: dict) -> str:
        """Get AI advice with fallback"""
        if not USE_VLM or not image_b64:
            return self._get_fallback_advice(scores)
        
        try:
            prompt = self._create_prompt(scores)
            advice = ask_llava(image_b64, prompt)
            
            # Validate response
            if not advice or len(advice) < 10:
                raise ValueError("Response too short")
            if advice in self.advice_history[-2:]:
                raise ValueError("Duplicate advice")
            
            # Clean up response
            advice = advice.strip().strip('"').strip("'")
            
            self.advice_history.append(advice)
            if len(self.advice_history) > 6:
                self.advice_history.pop(0)
            
            print(f"✅ VLM advice generated: {advice}")
            return advice
            
        except Exception as e:
            print(f"⚠️  VLM error (using fallback): {e}")
            return self._get_fallback_advice(scores)

# ---------- Flask App ---------------------------------------------------------
coach = ExpertCPRCoach()
app = Flask(__name__)

@app.route("/analyse", methods=["POST"])
def analyse():
    try:
        data = request.get_json(force=True)
        advice = coach.advise(data.get("image_base64", ""), data["scores"])
        print(f"💡 Advice: {advice}")
        return jsonify({"advice": advice})
    except Exception as e:
        print(f"❌ /analyse error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"advice": "Maintenez une bonne technique CPR"})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "model_loaded": True,
        "vlm_enabled": USE_VLM,
        "endpoint": f"{VLLM_BASE_URL}/llava-1.5-7b-hf" if USE_VLM else None
    })

# ---------- Startup -----------------------------------------------------------
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 CPR VLM Coaching Server")
    print("="*60)
    if USE_VLM:
        print(f"✅ University LLaVA-1.5-7b-hf ENABLED")
        print(f"📡 Endpoint: {VLLM_BASE_URL}/llava-1.5-7b-hf")
        print(f"🔑 API Key: {VLLM_API_KEY[:20]}...")
    else:
        print("⚠️  Fallback mode (add VLLM_API_KEY to enable VLM)")
    print("="*60 + "\n")
    
    ngrok.set_auth_token(NGROK_AUTH_TOKEN)
    ngrok.kill()
    tunnel = ngrok.connect(FLASK_PORT, bind_tls=True)
    
    print("\n" + "="*60)
    print("🌐 Ngrok tunnel:", tunnel.public_url)
    print("   ↑↑↑  Add this to .env as NGROK_PUBLIC_URL  ↑↑↑")
    print("="*60 + "\n")
    
    app.run(host="0.0.0.0", port=FLASK_PORT, threaded=True)

# ---------- CPR Coaching Logic ------------------------------------------------
class ExpertCPRCoach:
    def __init__(self):
        self.advice_history = []

    def _create_prompt(self, scores: dict) -> str:
        """Create contextual prompt based on scores"""
        arm = scores.get('arm_score', 100)
        rate = scores.get('rate_cpm', 110)
        depth = scores.get('depth_score', 100)
        hand_pos = scores.get('hand_position_score', 100)
        
        # Identify main issue
        if arm < 60:
            focus = f"bras pliés (score: {arm}%) - besoin de coudes verrouillés à 180°"
        elif rate < 100:
            focus = f"rythme trop lent à {rate}/min - besoin de 100-120/min"
        elif rate > 120:
            focus = f"rythme trop rapide à {rate}/min - ralentir à 100-120/min"
        elif depth < 70:
            focus = f"profondeur insuffisante (score: {depth}%) - pousser 5-6cm"
        elif hand_pos < 70:
            focus = f"position des mains incorrecte (score: {hand_pos}%)"
        else:
            focus = "technique correcte, maintenez la qualité"
        
        prompt = f"""Tu es un instructeur CPR expert. Analyse cette image de réanimation cardio-pulmonaire.

Problème identifié: {focus}

Donne UNE instruction courte et précise en français (maximum 15 mots) pour corriger ce problème.
Sois direct et actionnable. Ne mentionne pas les scores."""
        
        return prompt

    def _get_fallback_advice(self, scores: dict) -> str:
        """Smart fallback advice in French"""
        arm = scores.get('arm_score', 100)
        rate = scores.get('rate_cpm', 110)
        depth = scores.get('depth_score', 100)
        hand_pos = scores.get('hand_position_score', 100)
        
        # Find worst metric
        if arm < 60:
            options = [
                "Verrouillez vos coudes complètement - bras tendus",
                "Redressez vos bras - utilisez le poids de votre corps",
                "Coudes droits à 180 degrés - ne pliez pas"
            ]
        elif rate < 100:
            options = [
                f"Accélérez à 110 compressions par minute",
                "Plus rapide - comptez à voix haute",
                "Rythme trop lent - suivez le métronome"
            ]
        elif rate > 120:
            options = [
                "Ralentissez à 110 par minute",
                "Trop rapide - chantez 'Staying Alive'",
                "Moins vite - contrôlez le rythme"
            ]
        elif depth < 70:
            options = [
                "Poussez plus fort - 5-6 centimètres minimum",
                "Profondeur insuffisante - enfoncez davantage",
                "Utilisez votre poids pour comprimer plus"
            ]
        elif hand_pos < 70:
            options = [
                "Centrez vos mains sur le sternum",
                "Repositionnez au milieu de la poitrine",
                "Mains trop décalées - ajustez"
            ]
        else:
            options = [
                "Excellente technique - continuez ainsi",
                "Parfait - maintenez cette qualité",
                "Très bonne forme - bras droits, bon rythme"
            ]
        
        # Avoid repetition
        available = [a for a in options if a not in self.advice_history[-2:]]
        if not available:
            available = options
        
        advice = random.choice(available)
        self.advice_history.append(advice)
        if len(self.advice_history) > 6:
            self.advice_history.pop(0)
        
        return advice

    def advise(self, image_b64: str, scores: dict) -> str:
        """Get AI advice with fallback"""
        if not USE_VLM or not image_b64:
            return self._get_fallback_advice(scores)
        
        try:
            prompt = self._create_prompt(scores)
            advice = ask_gpt4_vision(image_b64, prompt)
            
            # Validate response
            if not advice or len(advice) < 10:
                raise ValueError("Response too short")
            if advice in self.advice_history[-2:]:
                raise ValueError("Duplicate advice")
            
            # Clean up response
            advice = advice.strip().strip('"').strip("'")
            
            self.advice_history.append(advice)
            if len(self.advice_history) > 6:
                self.advice_history.pop(0)
            
            print(f"✅ VLM advice generated: {advice}")
            return advice
            
        except Exception as e:
            print(f"⚠️  VLM error (using fallback): {e}")
            return self._get_fallback_advice(scores)

# ---------- Flask App ---------------------------------------------------------
coach = ExpertCPRCoach()
app = Flask(__name__)

@app.route("/analyse", methods=["POST"])
def analyse():
    try:
        data = request.get_json(force=True)
        advice = coach.advise(data.get("image_base64", ""), data["scores"])
        print(f"💡 Advice: {advice}")
        return jsonify({"advice": advice})
    except Exception as e:
        print(f"❌ /analyse error: {e}")
        return jsonify({"advice": "Maintenez une bonne technique CPR"})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "model_loaded": True,
        "vlm_enabled": USE_VLM
    })

# ---------- Startup -----------------------------------------------------------
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 CPR VLM Coaching Server")
    print("="*60)
    if USE_VLM:
        print("✅ OpenAI GPT-4 Vision ENABLED")
    else:
        print("⚠️  Fallback mode (add OPENAI_API_KEY to enable VLM)")
    print("="*60 + "\n")
    
    ngrok.set_auth_token(NGROK_AUTH_TOKEN)
    ngrok.kill()
    tunnel = ngrok.connect(FLASK_PORT, bind_tls=True)
    
    print("\n" + "="*60)
    print("🌐 Ngrok tunnel:", tunnel.public_url)
    print("   ↑↑↑  Add this to .env as NGROK_PUBLIC_URL  ↑↑↑")
    print("="*60 + "\n")
    
    app.run(host="0.0.0.0", port=FLASK_PORT, threaded=True)