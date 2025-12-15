#!/usr/bin/env python3
"""
API Server to bridge Frontend (Next.js) with CPR Backend
Handles WebSocket communication for real-time video + feedback
This version imports classes from main.py but doesn't use its camera
"""
import os
import cv2
import json
import base64
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
import threading
from datetime import datetime
from flask_cors import CORS
# Import your existing CPR components from main.py
# NOTE: main.py should NOT be running when using this API server
try:
    from main import (
        ImprovedCPRMetrics,
        FatigueDetector,
        AudioMetronome,
        CPRDataLogger,
        get_expert_advice,
        generate_fallback_advice,
        MODEL_PATH
    )
    from ultralytics import YOLO
    print("✅ Successfully imported CPR components from main.py")
except ImportError as e:
    print(f"❌ Failed to import from main.py: {e}")
    print("💡 Make sure main.py is in the same directory")
    exit(1)

load_dotenv()

# Configuration
FLASK_PORT = int(os.getenv("API_SERVER_PORT", 5000))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Initialize Flask + SocketIO
app = Flask(__name__)
CORS(app, origins=["http://localhost:3000"], supports_credentials=True)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global state
class CPRSession:
    def __init__(self):
        self.active = False
        self.model = None
        self.metrics = None
        self.fatigue_detector = None
        self.metronome = None
        self.logger = None
        self.frame_count = 0
        self.last_feedback_time = 0
        self.current_feedback = None
        
    def initialize(self):
        """Initialize CPR components"""
        try:
            print(f"Loading YOLO model from {MODEL_PATH}...")
            self.model = YOLO(MODEL_PATH)
            self.metrics = ImprovedCPRMetrics()
            self.fatigue_detector = FatigueDetector()
            self.metronome = AudioMetronome(target_bpm=110)
            
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            os.makedirs("cpr_logs", exist_ok=True)
            self.logger = CPRDataLogger(f"cpr_logs/session_{session_id}.csv")
            
            print("✅ CPR Session initialized successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to initialize CPR session: {e}")
            return False
    
    def reset(self):
        """Reset session"""
        self.metrics = ImprovedCPRMetrics()
        self.fatigue_detector = FatigueDetector()
        self.frame_count = 0
        self.current_feedback = None

session = CPRSession()

# ====================================================================
# REST API ENDPOINTS
# ====================================================================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "model_loaded": session.model is not None,
        "active_session": session.active
    }), 200

@app.route('/api/cpr/initialize', methods=['POST'])
def initialize_session():
    """Initialize CPR monitoring session"""
    try:
        if session.initialize():
            return jsonify({
                "success": True,
                "message": "CPR session initialized"
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": "Failed to initialize"
            }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/cpr/start', methods=['POST'])
def start_cpr():
    """Start CPR monitoring"""
    try:
        if not session.model:
            session.initialize()
        
        session.active = True
        session.reset()
        
        return jsonify({
            "success": True,
            "message": "CPR monitoring started"
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/cpr/stop', methods=['POST'])
def stop_cpr():
    """Stop CPR monitoring"""
    try:
        session.active = False
        
        return jsonify({
            "success": True,
            "message": "CPR monitoring stopped",
            "stats": {
                "total_compressions": session.metrics.compression_count if session.metrics else 0,
                "total_frames": session.frame_count
            }
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/cpr/reset', methods=['POST'])
def reset_cpr():
    """Reset CPR session"""
    try:
        session.reset()
        return jsonify({
            "success": True,
            "message": "Session reset"
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ====================================================================
# WEBSOCKET HANDLERS
# ====================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print(f"🔌 Client connected: {request.sid}")
    emit('connection_status', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print(f"🔌 Client disconnected: {request.sid}")

@socketio.on('video_frame')
def handle_video_frame(data):
    """
    Process video frame from frontend
    Expected data format: {
        "frame": "base64_encoded_image",
        "timestamp": timestamp
    }
    """
    if not session.active or not session.model:
        emit('error', {'message': 'Session not active'})
        return
    
    try:
        # Decode base64 frame
        frame_data = data.get('frame', '').split(',')[1] if ',' in data.get('frame', '') else data.get('frame', '')
        frame_bytes = base64.b64decode(frame_data)
        frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
        frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
        
        if frame is None:
            emit('error', {'message': 'Invalid frame'})
            return
        
        session.frame_count += 1
        
        # Run YOLO detection
        results = session.model(frame, verbose=False)
        
        # Process results
        response_data = {
            'frame_number': session.frame_count,
            'timestamp': data.get('timestamp'),
            'detection': False,
            'scores': None,
            'feedback': None,
            'fatigue_warning': None
        }
        
        # Check if we have valid detections (rescuer + victim)
        if (len(results) > 0 and 
            len(results[0].keypoints.xyn) >= 2 and 
            results[0].keypoints.xyn[0].shape[0] > 0):
            
            r = results[0]
            rescuer_kps = r.keypoints.xyn[0].cpu().numpy()
            victim_kps = r.keypoints.xyn[1].cpu().numpy()
            
            frame_height, frame_width = frame.shape[:2]
            
            # Calculate CPR scores using your existing metrics
            scores = session.metrics.get_comprehensive_score(
                rescuer_kps=rescuer_kps,
                victim_kps=victim_kps,
                scale_factor=(frame_width, frame_height)
            )
            
            # Update fatigue detection
            session.fatigue_detector.update(scores['overall'])
            fatigue_warning = session.fatigue_detector.get_warning()
            
            # Get VLM feedback (every 10 seconds if score is low)
            current_time = datetime.now().timestamp()
            if current_time - session.last_feedback_time > 10 and scores['overall'] < 75:
                # Request VLM advice in background thread
                threading.Thread(
                    target=get_vlm_feedback_async,
                    args=(frame, scores),
                    daemon=True
                ).start()
                session.last_feedback_time = current_time
            
            # Prepare response with all data
            response_data.update({
                'detection': True,
                'scores': {
                    'overall': scores['overall'],
                    'arm_score': scores['arm_score'],
                    'arm_angle': scores['arm_angle'],
                    'hand_position_score': scores['hand_position_score'],
                    'depth_score': scores['depth_score'],
                    'depth_cm': scores['depth_cm'],
                    'rate_score': scores['rate_score'],
                    'rate_cpm': scores['rate_cpm'],
                    'recoil_score': scores['recoil_score'],
                    'compression_count': scores['compression_count']
                },
                'feedback': {
                    'depth': 'correct' if scores['depth_score'] >= 80 else 'incorrect' if scores['depth_score'] < 70 else 'neutral',
                    'rate': 'correct' if scores['rate_score'] >= 80 else 'incorrect' if scores['rate_score'] < 70 else 'neutral',
                    'position': 'correct' if scores['hand_position_score'] >= 80 else 'incorrect' if scores['hand_position_score'] < 70 else 'neutral'
                },
                'vlm_advice': session.current_feedback,
                'fatigue_warning': fatigue_warning,
                'keypoints': {
                    'rescuer': rescuer_kps.tolist(),
                    'victim': victim_kps.tolist()
                }
            })
            
            # Log data every 10 frames
            if session.frame_count % 10 == 0:
                session.logger.log_frame(
                    session.frame_count,
                    scores,
                    session.fatigue_detector.fatigue_level,
                    session.current_feedback
                )
        
        # Send response to frontend
        emit('cpr_analysis', response_data)
        
    except Exception as e:
        print(f"❌ Error processing frame: {e}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': str(e)})

def get_vlm_feedback_async(frame, scores):
    """Get VLM feedback in background thread"""
    try:
        # Try to get VLM advice using function from main.py
        advice = get_expert_advice(frame, scores)
        
        if not advice:
            # Use fallback from main.py
            advice = generate_fallback_advice(scores)
        
        session.current_feedback = advice
        
        # Emit to all connected clients
        socketio.emit('vlm_feedback', {
            'advice': advice,
            'timestamp': datetime.now().timestamp()
        })
        
        print(f"💡 VLM Advice: {advice}")
        
    except Exception as e:
        print(f"❌ VLM feedback error: {e}")
@app.route('/api/cpr/process-frame', methods=['POST'])
def process_frame():
    """Process a single frame from the frontend"""
    if not session.active or not session.model:
        return jsonify({'error': 'Session not active'}), 400
    
    try:
        data = request.get_json()
        frame_data = data.get('frame', '').split(',')[1] if ',' in data.get('frame', '') else data.get('frame', '')
        frame_bytes = base64.b64decode(frame_data)
        frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
        frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
        
        if frame is None:
            return jsonify({'error': 'Invalid frame'}), 400
        
        session.frame_count += 1
        
        # Run YOLO detection
        results = session.model(frame, verbose=False)
        
        response_data = {
            'detection': False,
            'scores': None,
            'feedback': None,
            'fatigue_warning': None,
            'vlm_advice': None
        }
        
        if (len(results) > 0 and 
            len(results[0].keypoints.xyn) >= 2 and 
            results[0].keypoints.xyn[0].shape[0] > 0):
            
            r = results[0]
            rescuer_kps = r.keypoints.xyn[0].cpu().numpy()
            victim_kps = r.keypoints.xyn[1].cpu().numpy()
            
            frame_height, frame_width = frame.shape[:2]
            
            scores = session.metrics.get_comprehensive_score(
                rescuer_kps=rescuer_kps,
                victim_kps=victim_kps,
                scale_factor=(frame_width, frame_height)
            )
            
            session.fatigue_detector.update(scores['overall'])
            fatigue_warning = session.fatigue_detector.get_warning()
            
            current_time = datetime.now().timestamp()
            if current_time - session.last_feedback_time > 10 and scores['overall'] < 75:
                threading.Thread(
                    target=get_vlm_feedback_async,
                    args=(frame, scores),
                    daemon=True
                ).start()
                session.last_feedback_time = current_time
            
            response_data.update({
                'detection': True,
                'scores': {
                    'overall': scores['overall'],
                    'arm_score': scores['arm_score'],
                    'arm_angle': scores['arm_angle'],
                    'hand_position_score': scores['hand_position_score'],
                    'depth_score': scores['depth_score'],
                    'depth_cm': scores['depth_cm'],
                    'rate_score': scores['rate_score'],
                    'rate_cpm': scores['rate_cpm'],
                    'recoil_score': scores['recoil_score'],
                    'compression_count': scores['compression_count']
                },
                'feedback': {
                    'depth': 'correct' if scores['depth_score'] >= 80 else 'incorrect' if scores['depth_score'] < 70 else 'neutral',
                    'rate': 'correct' if scores['rate_score'] >= 80 else 'incorrect' if scores['rate_score'] < 70 else 'neutral',
                    'position': 'correct' if scores['hand_position_score'] >= 80 else 'incorrect' if scores['hand_position_score'] < 70 else 'neutral'
                },
                'vlm_advice': session.current_feedback,
                'fatigue_warning': fatigue_warning
            })
        
        return jsonify(response_data), 200
        
    except Exception as e:
        print(f"❌ Error processing frame: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
@socketio.on('request_feedback')
def handle_manual_feedback_request():
    """Handle manual feedback request from frontend"""
    if session.current_feedback:
        emit('vlm_feedback', {
            'advice': session.current_feedback,
            'timestamp': datetime.now().timestamp()
        })
    else:
        emit('vlm_feedback', {
            'advice': "Maintenez une bonne technique CPR",
            'timestamp': datetime.now().timestamp()
        })

@socketio.on('toggle_metronome')
def handle_toggle_metronome(data):
    """Toggle metronome on/off"""
    if session.metronome:
        enabled = session.metronome.toggle()
        emit('metronome_status', {'enabled': enabled})

# ====================================================================
# STARTUP
# ====================================================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 CPR API Server Starting...")
    print("="*60)
    print(f"📡 Frontend URL: {FRONTEND_URL}")
    print(f"🔌 WebSocket endpoint: ws://localhost:{FLASK_PORT}")
    print(f"🌐 HTTP endpoint: http://localhost:{FLASK_PORT}")
    print("\n⚠️  IMPORTANT: Do NOT run main.py when using this server!")
    print("   The frontend browser will provide the camera feed.")
    print("="*60 + "\n")
    
    # Initialize session on startup
    session.initialize()
    
    # Run server
    socketio.run(app, host='0.0.0.0', port=FLASK_PORT, debug=True, allow_unsafe_werkzeug=True)