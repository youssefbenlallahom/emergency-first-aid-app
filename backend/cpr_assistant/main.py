import numpy as np
from ultralytics import YOLO
import math
import time
from collections import deque
import cv2
import requests
import base64
import pyttsx3
import threading
import queue
import os
import csv
from datetime import datetime
import pygame
import urllib3
from dotenv import load_dotenv

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ====================================================================
# CONFIGURATION - USE HTTP
# ====================================================================
load_dotenv()
MODEL_PATH = './best.pt'
NGROK_PUBLIC_URL = os.getenv("NGROK_PUBLIC_URL", "").rstrip("/")
API_ENDPOINT = f"{NGROK_PUBLIC_URL}/analyse"

# Create logs directory
os.makedirs("cpr_logs", exist_ok=True)
SESSION_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = f"cpr_logs/session_{SESSION_ID}.csv"

# ====================================================================
# 1. FIXED CPR METRICS (Division by zero fixed)
# ====================================================================

class ImprovedCPRMetrics:
    def __init__(self):
        self.wrist_history = deque(maxlen=150)
        self.time_history = deque(maxlen=150)
        self.hand_positions = deque(maxlen=150)
        self.compression_count = 0
        self.last_compression_time = 0
        self.in_compression = False
        self.compression_start_y = None
        self.compression_start_time = None
        self.release_start_time = None
        self.rate_display = 0
        self.last_rate_update = time.time()
        self.recoil_scores = deque(maxlen=10)
        self.compression_durations = deque(maxlen=10)
        self.release_durations = deque(maxlen=10)
        self.hand_position_scores = deque(maxlen=30)
        
    def calculate_angle(self, p1, p2, p3):
        try:
            a = np.array(p1)
            b = np.array(p2)
            c = np.array(p3)
            ba = a - b
            bc = c - b
            cosine = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
            cosine = np.clip(cosine, -1.0, 1.0)
            return np.degrees(np.arccos(cosine))
        except:
            return 0
    
    def calculate_arm_score(self, shoulder, elbow, wrist):
        angle = self.calculate_angle(shoulder, elbow, wrist)
        if 160 <= angle <= 175:
            score = 100
        elif 150 <= angle < 160 or 175 < angle <= 185:
            score = 80 - abs(angle - 167.5) * 2
        else:
            score = max(0, 60 - abs(angle - 167.5) * 1.5)
        return round(score), round(angle)
    
    def check_hand_position(self, left_wrist, right_wrist, victim_torso_center, victim_torso_width):
        hand_center_x = (left_wrist[0] + right_wrist[0]) / 2
        hand_center_y = (left_wrist[1] + right_wrist[1]) / 2
        dx = abs(hand_center_x - victim_torso_center[0])
        dy = abs(hand_center_y - victim_torso_center[1])
        horizontal_error = dx / victim_torso_width if victim_torso_width > 0 else 1.0
        
        if horizontal_error < 0.1:
            score = 100
        elif horizontal_error < 0.2:
            score = 80
        elif horizontal_error < 0.3:
            score = 60
        else:
            score = max(0, 40 - horizontal_error * 50)
        self.hand_position_scores.append(score)
        return round(score)
    
    def calculate_depth_score(self, wrist_y, victim_torso_height_px):
        self.wrist_history.append(wrist_y)
        if len(self.wrist_history) < 10:
            return 0, 0, 0
        
        min_y = min(self.wrist_history)
        max_y = max(self.wrist_history)
        depth_px = max_y - min_y
        
        # FIX: Prevent division by zero
        if victim_torso_height_px <= 0:
            return 0, 0, 0
            
        target_min = victim_torso_height_px * 0.15
        target_max = victim_torso_height_px * 0.20
        
        # FIX: Ensure target_max is not zero
        if target_max <= 0:
            return 0, 0, 0
        
        if target_min <= depth_px <= target_max:
            depth_score = 100
        elif depth_px < target_min:
            ratio = depth_px / target_min if target_min > 0 else 0
            depth_score = round(ratio * 70)
        else:
            excess = depth_px - target_max
            # FIX: Prevent division by zero
            if target_max > 0:
                depth_score = max(50, round(100 - (excess / target_max) * 100))
            else:
                depth_score = 50
        
        depth_cm = (depth_px / victim_torso_height_px) * 40 if victim_torso_height_px > 0 else 0
        
        return depth_score, round(depth_px), round(depth_cm, 1)
    
    def calculate_rate_score(self, wrist_y):
        current_time = time.time()
        self.time_history.append(current_time)
        
        if len(self.wrist_history) < 3:
            return 0, 0
        
        prev_y = self.wrist_history[-2]
        curr_y = self.wrist_history[-1]
        
        if not self.in_compression and curr_y > prev_y + 5:
            self.in_compression = True
            self.compression_start_y = prev_y
            self.compression_start_time = current_time
            if self.release_start_time:
                release_duration = current_time - self.release_start_time
                self.release_durations.append(release_duration)
            
        elif self.in_compression and curr_y < prev_y - 5:
            if self.compression_start_y and (wrist_y - self.compression_start_y) > 20:
                self.compression_count += 1
                self.last_compression_time = current_time
                if self.compression_start_time:
                    comp_duration = current_time - self.compression_start_time
                    self.compression_durations.append(comp_duration)
                self.release_start_time = current_time
            self.in_compression = False
            self.compression_start_y = None
        
        time_window = 5.0
        if current_time - self.time_history[0] >= time_window:
            self.rate_display = (self.compression_count / (current_time - self.time_history[0])) * 60
        
        rate = self.rate_display
        if 100 <= rate <= 120:
            rate_score = 100
        elif 90 < rate < 100:
            rate_score = 70 + (rate - 90) * 3
        elif 120 < rate <= 140:
            rate_score = 100 - (rate - 120) * 2
        elif 80 <= rate <= 90:
            rate_score = 50
        else:
            rate_score = max(0, 40 - abs(rate - 110) * 0.5)
        return rate_score, round(rate)
    
    def calculate_recoil_score(self):
        if len(self.wrist_history) < 20:
            return 100
        recent = list(self.wrist_history)[-20:]
        min_recent = min(recent)
        max_recent = max(recent)
        travel = max_recent - min_recent
        
        # FIX: Prevent division issues
        if travel <= 0:
            return 100
            
        last_5 = recent[-5:]
        avg_last_5 = sum(last_5) / 5
        
        if avg_last_5 <= min_recent + (travel * 0.1):
            recoil = 100
        elif avg_last_5 <= min_recent + (travel * 0.3):
            recoil = 70
        else:
            recoil = 40
        self.recoil_scores.append(recoil)
        return round(sum(self.recoil_scores) / len(self.recoil_scores))
    
    def get_compression_release_ratio(self):
        if len(self.compression_durations) < 3 or len(self.release_durations) < 3:
            return 50, 100
        avg_comp = sum(self.compression_durations) / len(self.compression_durations)
        avg_release = sum(self.release_durations) / len(self.release_durations)
        total_time = avg_comp + avg_release
        if total_time == 0:
            return 50, 100
        comp_percent = (avg_comp / total_time) * 100
        deviation = abs(comp_percent - 50)
        if deviation < 5:
            ratio_score = 100
        elif deviation < 10:
            ratio_score = 85
        elif deviation < 15:
            ratio_score = 70
        else:
            ratio_score = max(50, 100 - deviation * 2)
        return round(comp_percent), round(ratio_score)
    
    def get_comprehensive_score(self, rescuer_kps, victim_kps, scale_factor):
        try:
            r_shoulder = rescuer_kps[5] * scale_factor
            r_elbow = rescuer_kps[7] * scale_factor
            r_wrist_left = rescuer_kps[9] * scale_factor
            r_wrist_right = rescuer_kps[10] * scale_factor
            
            # FIX: Better victim detection with fallbacks
            if victim_kps[5, 1] > 0 and victim_kps[11, 1] > 0:
                torso_px = abs(victim_kps[11, 1] - victim_kps[5, 1]) * scale_factor[1]
                torso_center_y = (victim_kps[5, 1] + victim_kps[11, 1]) / 2 * scale_factor[1]
            else:
                torso_px = max(200, scale_factor[1] * 0.4)  # Reasonable default
                torso_center_y = scale_factor[1] / 2
            
            if victim_kps[5, 0] > 0 and victim_kps[6, 0] > 0:
                torso_width = abs(victim_kps[6, 0] - victim_kps[5, 0]) * scale_factor[0]
                torso_center_x = (victim_kps[5, 0] + victim_kps[6, 0]) / 2 * scale_factor[0]
            else:
                torso_width = max(100, scale_factor[0] * 0.3)  # Reasonable default
                torso_center_x = scale_factor[0] / 2
            
            victim_center = (torso_center_x, torso_center_y)
            wrist_y = (r_wrist_left[1] + r_wrist_right[1]) / 2
            
            arm_score, arm_angle = self.calculate_arm_score(r_shoulder, r_elbow, r_wrist_left)
            hand_pos_score = self.check_hand_position(r_wrist_left, r_wrist_right, victim_center, torso_width)
            depth_score, depth_px, depth_cm = self.calculate_depth_score(wrist_y, torso_px)
            rate_score, rate_cpm = self.calculate_rate_score(wrist_y)
            recoil_score = self.calculate_recoil_score()
            comp_ratio, ratio_score = self.get_compression_release_ratio()
            
            overall = (
                arm_score * 0.15 +
                hand_pos_score * 0.10 +
                depth_score * 0.30 +
                rate_score * 0.25 +
                recoil_score * 0.10 +
                ratio_score * 0.10
            )
            
            return {
                'overall': round(overall),
                'arm_score': arm_score,
                'arm_angle': arm_angle,
                'hand_position_score': hand_pos_score,
                'depth_score': depth_score,
                'depth_px': depth_px,
                'depth_cm': depth_cm,
                'rate_score': rate_score,
                'rate_cpm': rate_cpm,
                'recoil_score': recoil_score,
                'compression_ratio': comp_ratio,
                'ratio_score': ratio_score,
                'compression_count': self.compression_count
            }
        except Exception as e:
            print(f"❌ Error calculating scores: {e}")
            # Return safe default scores
            return {
                'overall': 0,
                'arm_score': 0,
                'arm_angle': 0,
                'hand_position_score': 0,
                'depth_score': 0,
                'depth_px': 0,
                'depth_cm': 0,
                'rate_score': 0,
                'rate_cpm': 0,
                'recoil_score': 0,
                'compression_ratio': 50,
                'ratio_score': 100,
                'compression_count': self.compression_count
            }

# ====================================================================
# 2. FATIGUE DETECTION (UNCHANGED)
# ====================================================================

class FatigueDetector:
    def __init__(self):
        self.score_windows = deque(maxlen=12)
        self.last_window_time = time.time()
        self.current_window_scores = []
        self.fatigue_level = 0
        self.is_fatigued = False
        
    def update(self, overall_score):
        current_time = time.time()
        self.current_window_scores.append(overall_score)
        if current_time - self.last_window_time >= 5.0:
            if self.current_window_scores:
                window_avg = sum(self.current_window_scores) / len(self.current_window_scores)
                self.score_windows.append(window_avg)
                self.current_window_scores = []
                self.last_window_time = current_time
            if len(self.score_windows) >= 6:
                recent_avg = sum(list(self.score_windows)[-3:]) / 3
                older_avg = sum(list(self.score_windows)[-6:-3]) / 3
                decline = older_avg - recent_avg
                if decline > 15:
                    self.fatigue_level = min(100, self.fatigue_level + 20)
                elif decline > 8:
                    self.fatigue_level = min(100, self.fatigue_level + 10)
                else:
                    self.fatigue_level = max(0, self.fatigue_level - 5)
                self.is_fatigued = self.fatigue_level > 50
    
    def get_warning(self):
        if self.fatigue_level > 80:
            return "SEVERE FATIGUE: Consider switching rescuer!"
        elif self.fatigue_level > 50:
            return "FATIGUE DETECTED: Quality declining"
        return None

# ====================================================================
# 3. AUDIO METRONOME (UNCHANGED)
# ====================================================================

class AudioMetronome:
    def __init__(self, target_bpm=110):
        pygame.mixer.init(frequency=22050, size=-16, channels=1)
        self.target_bpm = target_bpm
        self.interval = 60.0 / target_bpm
        self.last_beat_time = 0
        self.enabled = True
        self.beat_sound = self._generate_beep()
        
    def _generate_beep(self):
        sample_rate = 22050
        duration = 0.1
        frequency = 800
        samples = int(sample_rate * duration)
        wave = np.sin(2 * np.pi * frequency * np.linspace(0, duration, samples))
        envelope = np.linspace(1, 0, samples)
        wave = wave * envelope
        wave = (wave * 32767).astype(np.int16)
        stereo_wave = np.column_stack((wave, wave))
        return pygame.sndarray.make_sound(stereo_wave)
    
    def update(self):
        if not self.enabled:
            return
        current_time = time.time()
        if current_time - self.last_beat_time >= self.interval:
            try:
                self.beat_sound.play()
                self.last_beat_time = current_time
            except:
                pass
    
    def toggle(self):
        self.enabled = not self.enabled
        return self.enabled

# ====================================================================
# 4. DATA LOGGING (UNCHANGED)
# ====================================================================

class CPRDataLogger:
    def __init__(self, filename):
        self.filename = filename
        self.fieldnames = [
            'timestamp', 'frame_number', 'overall_score',
            'arm_score', 'arm_angle', 'hand_position_score',
            'depth_score', 'depth_cm', 'rate_score', 'rate_cpm',
            'recoil_score', 'compression_ratio', 'ratio_score',
            'compression_count', 'fatigue_level', 'feedback_given'
        ]
        with open(self.filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            writer.writeheader()
        print(f"📊 Logging session data to: {self.filename}")
    
    def log_frame(self, frame_num, scores, fatigue_level, feedback_text=None):
        try:
            with open(self.filename, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writerow({
                    'timestamp': datetime.now().isoformat(),
                    'frame_number': frame_num,
                    'overall_score': scores['overall'],
                    'arm_score': scores['arm_score'],
                    'arm_angle': scores['arm_angle'],
                    'hand_position_score': scores['hand_position_score'],
                    'depth_score': scores['depth_score'],
                    'depth_cm': scores['depth_cm'],
                    'rate_score': scores['rate_score'],
                    'rate_cpm': scores['rate_cpm'],
                    'recoil_score': scores['recoil_score'],
                    'compression_ratio': scores['compression_ratio'],
                    'ratio_score': scores['ratio_score'],
                    'compression_count': scores['compression_count'],
                    'fatigue_level': fatigue_level,
                    'feedback_given': feedback_text or ''
                })
        except Exception as e:
            print(f"❌ Logging error: {e}")

# ====================================================================
# 5. VLM COACHING (UNCHANGED)
# ====================================================================

class CPRCoachingPrompts:
    def __init__(self):
        self.last_focus = None
        self.feedback_history = []
        
    def create_focused_prompt(self, scores):
        metrics = [
            (scores.get('arm_score', 100), 'arm'),
            (scores.get('rate_score', 100), 'rate'),
            (scores.get('depth_score', 100), 'depth'),
            (scores.get('recoil_score', 100), 'recoil'),
            (scores.get('hand_position_score', 100), 'hand_position'),
            (scores.get('ratio_score', 100), 'ratio')
        ]
        metrics.sort(key=lambda x: x[0])
        worst_score, worst_metric = metrics[0]
        if worst_metric == self.last_focus and len(metrics) > 1:
            worst_metric = metrics[1][1]
        self.last_focus = worst_metric
        
        prompts = {
            'arm': "<image>\nUSER: Arms need straightening. One instruction:\nASSISTANT:",
            'rate': f"<image>\nUSER: Rate is {scores.get('rate_cpm')}. Fix it. One tip:\nASSISTANT:",
            'depth': f"<image>\nUSER: Depth is {scores.get('depth_cm')}cm. Correct it:\nASSISTANT:",
            'recoil': "<image>\nUSER: Not allowing full recoil. Fix:\nASSISTANT:",
            'hand_position': "<image>\nUSER: Hands off-center. Correct position:\nASSISTANT:",
            'ratio': "<image>\nUSER: Compression timing wrong. Fix:\nASSISTANT:"
        }
        return prompts.get(worst_metric, ""), worst_metric
    
    def get_fallback_advice(self, scores, focus_area):
        fallbacks = {
            'arm': "Lock your elbows straight",
            'rate': "Speed up to 100-120 per minute" if scores.get('rate_cpm', 0) < 100 else "Slow down your compressions",
            'depth': "Push deeper, at least 5 centimeters" if scores.get('depth_cm', 0) < 4.5 else "Reduce compression depth slightly",
            'recoil': "Let chest fully recoil between pushes",
            'hand_position': "Center your hands on the sternum",
            'ratio': "Equal time pushing and releasing"
        }
        return fallbacks.get(focus_area, "Maintain technique")

# ====================================================================
# 6. FEEDBACK MANAGER (UNCHANGED)
# ====================================================================

class AdaptiveFeedbackManager:
    def __init__(self):
        self.last_feedback_time = 0
        self.min_cooldown = 10
        self.max_cooldown = 30
        self.score_history = deque(maxlen=30)
        self.consecutive_poor_frames = 0
        self.feedback_count = 0
        self.last_feedback_text = ""
        self.last_focus_area = None
        
    def should_request_feedback(self, overall_score):
        current_time = time.time()
        time_since_last = current_time - self.last_feedback_time
        self.score_history.append(overall_score)
        
        if overall_score < 70:
            self.consecutive_poor_frames += 1
        else:
            self.consecutive_poor_frames = max(0, self.consecutive_poor_frames - 2)
        
        if overall_score < 50 and time_since_last > 5:
            return True, "critical"
        if time_since_last < self.min_cooldown:
            return False, "cooldown"
        if time_since_last > self.max_cooldown:
            return True, "periodic"
        if self.consecutive_poor_frames >= 20 and overall_score < 70:
            return True, "sustained_poor"
        return False, "good"
    
    def record_feedback(self, feedback_text, focus_area):
        self.last_feedback_time = time.time()
        self.last_feedback_text = feedback_text
        self.last_focus_area = focus_area
        self.feedback_count += 1
        self.consecutive_poor_frames = 0

# ====================================================================
# 7. TTS ENGINE (UNCHANGED)
# ====================================================================

class RobustTTS:
    def __init__(self):
        self.speech_queue = queue.Queue()
        self.is_speaking = False
        self.last_spoken = ""
        self.worker_thread = threading.Thread(target=self._process_speech_queue, daemon=True)
        self.worker_thread.start()
    
    def _create_engine(self):
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 160)
            engine.setProperty('volume', 0.9)
            return engine
        except:
            return None
    
    def _process_speech_queue(self):
        while True:
            try:
                text = self.speech_queue.get(timeout=1)
                if text and text != self.last_spoken:
                    self.is_speaking = True
                    engine = self._create_engine()
                    if engine:
                        engine.say(text)
                        engine.runAndWait()
                        engine.stop()
                        del engine
                    self.last_spoken = text
                    self.is_speaking = False
                self.speech_queue.task_done()
            except queue.Empty:
                continue
            except:
                self.is_speaking = False
    
    def speak(self, text):
        if text and len(text) >= 5 and text != self.last_spoken:
            self.speech_queue.put(text)
            return True
        return False

# ====================================================================
# 8. ROBUST VLM API CLIENT (FIXED)
# ====================================================================

def get_expert_advice(frame, scores):
    try:
        success, encoded_image = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if not success:
            print("❌ Failed to encode image")
            return None
        
        jpg_as_text = base64.b64encode(encoded_image).decode('utf-8')
        payload = {"image_base64": jpg_as_text, "scores": scores}
        
        # Use HTTP with longer timeout
        response = requests.post(
            API_ENDPOINT, 
            json=payload, 
            timeout=20,  # Increased timeout
            verify=False
        )
        
        if response.status_code == 200:
            advice = response.json().get("advice", "")
            return advice.strip()
        else:
            print(f"❌ VLM HTTP error: {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        print("❌ VLM timeout - server taking too long")
        return None
    except requests.exceptions.ConnectionError:
        print("❌ VLM connection error - check ngrok tunnel")
        return None
    except Exception as e:
        print(f"❌ VLM unexpected error: {e}")
        return None

def generate_fallback_advice(scores):
    """Generate intelligent fallback advice when VLM fails"""
    if scores.get('rate_score', 100) < 70:
        rate = scores.get('rate_cpm', 0)
        if rate < 100:
            return "Speed up compressions to 100-120 per minute"
        else:
            return "Slow down compressions to 100-120 per minute"
    elif scores.get('depth_score', 100) < 70:
        return "Push deeper for adequate chest compression"
    elif scores.get('arm_score', 100) < 70:
        return "Keep arms straight for effective compressions"
    elif scores.get('recoil_score', 100) < 70:
        return "Allow full chest recoil between compressions"
    elif scores.get('hand_position_score', 100) < 70:
        return "Center hands on sternum for proper compression"
    else:
        return "Maintain good CPR technique"

def test_vlm_connection():
    """Test if VLM server is accessible"""
    try:
        response = requests.get(f"{NGROK_PUBLIC_URL}/health", timeout=10, verify=False)
        if response.status_code == 200:
            print("✅ VLM Server is connected and healthy!")
            return True
        else:
            print(f"❌ VLM Server responded with error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to VLM Server: {e}")
        print("💡 Make sure your Colab VLM server is running")
        return False

# ====================================================================
# 9. MULTI-PERSON DETECTION (UNCHANGED)
# ====================================================================

class MultiPersonTracker:
    def __init__(self):
        self.active_rescuers = {}
        self.switch_cooldown = 5.0
        self.last_switch_time = 0
        
    def update_rescuers(self, detections):
        current_time = time.time()
        if len(detections) > 0:
            if len(detections) > 1 and (current_time - self.last_switch_time) > 120:
                return True, "Consider switching rescuer to prevent fatigue"
        return False, None

# ====================================================================
# 10. UI OVERLAY (UNCHANGED)
# ====================================================================

def draw_comprehensive_overlay(frame, scores, fatigue_warning, metronome_enabled, feedback_text=None):
    h, w = frame.shape[:2]
    overlay = frame.copy()
    
    # Main score panel (Top Left)
    panel_w, panel_h = 320, 280
    cv2.rectangle(overlay, (10, 10), (panel_w, panel_h), (0, 0, 0), -1)
    cv2.rectangle(overlay, (10, 10), (panel_w, panel_h), (255, 255, 255), 2)
    
    overall = scores['overall']
    if overall >= 80:
        score_color = (0, 255, 0)
    elif overall >= 60:
        score_color = (0, 255, 255)
    else:
        score_color = (0, 0, 255)
    
    cv2.putText(overlay, f"CPR QUALITY: {overall}%", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, score_color, 2)
    
    # Individual metrics
    y_offset = 70
    metrics = [
        (f"Arms: {scores['arm_score']}% ({scores['arm_angle']}deg)", scores['arm_score']),
        (f"Hand Pos: {scores['hand_position_score']}%", scores['hand_position_score']),
        (f"Depth: {scores['depth_score']}% ({scores['depth_cm']}cm)", scores['depth_score']),
        (f"Rate: {scores['rate_score']}% ({scores['rate_cpm']}/min)", scores['rate_score']),
        (f"Recoil: {scores['recoil_score']}%", scores['recoil_score']),
        (f"Timing: {scores['ratio_score']}% ({scores['compression_ratio']}%)", scores['ratio_score'])
    ]
    
    for text, score in metrics:
        color = (0, 255, 0) if score >= 80 else (0, 255, 255) if score >= 60 else (0, 0, 255)
        cv2.putText(overlay, text, (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        y_offset += 30
    
    cv2.putText(overlay, f"Compressions: {scores['compression_count']}", (20, y_offset),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    # Feedback panel (Bottom)
    if feedback_text:
        feedback_h = 100
        cv2.rectangle(overlay, (10, h - feedback_h - 10), (w - 10, h - 10), (40, 40, 40), -1)
        cv2.rectangle(overlay, (10, h - feedback_h - 10), (w - 10, h - 10), (0, 255, 255), 2)
        
        words = feedback_text.split()
        lines = []
        current_line = []
        for word in words:
            test_line = ' '.join(current_line + [word])
            (text_w, _), _ = cv2.getTextSize(test_line, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            if text_w < w - 40:
                current_line.append(word)
            else:
                lines.append(' '.join(current_line))
                current_line = [word]
        if current_line:
            lines.append(' '.join(current_line))
        
        y_pos = h - feedback_h + 30
        for line in lines[:2]:
            cv2.putText(overlay, line, (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            y_pos += 35
    
    # Fatigue warning (Top Right)
    if fatigue_warning:
        warning_w = 400
        cv2.rectangle(overlay, (w - warning_w - 10, 10), (w - 10, 80), (0, 0, 128), -1)
        cv2.rectangle(overlay, (w - warning_w - 10, 10), (w - 10, 80), (0, 0, 255), 3)
        cv2.putText(overlay, "FATIGUE ALERT!", (w - warning_w, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.putText(overlay, fatigue_warning, (w - warning_w, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    # Status indicators (Top Right Corner)
    status_y = 100 if fatigue_warning else 20
    metronome_color = (0, 255, 0) if metronome_enabled else (128, 128, 128)
    cv2.circle(overlay, (w - 30, status_y), 10, metronome_color, -1)
    cv2.putText(overlay, "BEAT", (w - 80, status_y + 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, metronome_color, 1)
    
    # Blend overlay
    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)
    return frame

# ====================================================================
# 11. MAIN APPLICATION (FIXED)
# ====================================================================

def main():
    # Initialize components
    print("🚀 Initializing Advanced CPR Assessment System...")
    
    try:
        model = YOLO(MODEL_PATH)
        print(f"✅ YOLO model loaded from {MODEL_PATH}")
    except Exception as e:
        print(f"❌ Failed to load YOLO model: {e}")
        return
    
    # Test VLM connection
    vlm_connected = test_vlm_connection()
    if not vlm_connected:
        print("🚨 Running in fallback mode - VLM feedback will use local advice")
    
    cpr_metrics = ImprovedCPRMetrics()
    fatigue_detector = FatigueDetector()
    metronome = AudioMetronome(target_bpm=110)
    data_logger = CPRDataLogger(LOG_FILE)
    coach = CPRCoachingPrompts()
    feedback_mgr = AdaptiveFeedbackManager()
    tts_engine = RobustTTS()
    multi_tracker = MultiPersonTracker()
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Cannot open webcam")
        return
    
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print("✅ System ready!")
    print(f"📷 Resolution: {frame_width}x{frame_height}")
    print(f"🌐 Using ngrok URL: {NGROK_PUBLIC_URL}")
    print("💡 Controls:")
    print("   'q' - Quit")
    print("   'm' - Toggle metronome")
    print("   'space' - Manual feedback request")
    print("   'r' - Reset session")
    
    frame_count = 0
    start_time = time.time()
    current_feedback = None
    last_frame_for_vlm = None
    vlm_thread = None
    vlm_result_queue = queue.Queue()
    
    def vlm_worker(frame, scores, result_queue):
        """Worker thread for VLM API calls"""
        try:
            print("🔄 Calling VLM for expert advice...")
            advice = get_expert_advice(frame, scores)
            if advice:
                print(f"✅ VLM Advice: {advice}")
                result_queue.put(advice)
            else:
                # Provide fallback advice
                fallback_advice = generate_fallback_advice(scores)
                print(f"🔄 Using fallback advice: {fallback_advice}")
                result_queue.put(fallback_advice)
        except Exception as e:
            print(f"❌ VLM worker error: {e}")
            fallback_advice = generate_fallback_advice(scores)
            result_queue.put(fallback_advice)
    
    try:
        while True:
            success, frame = cap.read()
            if not success:
                print("❌ Failed to read frame")
                break
            
            frame_count += 1
            frame = cv2.flip(frame, 1)
            
            # Update metronome
            metronome.update()
            
            # Run YOLO detection
            results = model(frame, verbose=False)
            
            # Check for VLM results
            try:
                new_feedback = vlm_result_queue.get_nowait()
                if new_feedback:
                    current_feedback = new_feedback
                    feedback_mgr.record_feedback(new_feedback, coach.last_focus)
                    tts_engine.speak(new_feedback)
                    print(f"🎤 Speaking: {new_feedback}")
            except queue.Empty:
                pass
            
            # Process detections with error handling
            try:
                if (len(results) > 0 and 
                    len(results[0].keypoints.xyn) >= 2 and 
                    results[0].keypoints.xyn[0].shape[0] > 0):
                    
                    r = results[0]
                    rescuer_kps = r.keypoints.xyn[0].cpu().numpy()
                    victim_kps = r.keypoints.xyn[1].cpu().numpy()
                    
                    # Calculate scores
                    scores = cpr_metrics.get_comprehensive_score(
                        rescuer_kps=rescuer_kps,
                        victim_kps=victim_kps,
                        scale_factor=(frame_width, frame_height)
                    )
                    
                    # Update fatigue detection
                    fatigue_detector.update(scores['overall'])
                    fatigue_warning = fatigue_detector.get_warning()
                    
                    # Check if feedback should be requested
                    should_request, reason = feedback_mgr.should_request_feedback(scores['overall'])
                    
                    if should_request and (vlm_thread is None or not vlm_thread.is_alive()):
                        print(f"🔍 Requesting VLM feedback (reason: {reason})")
                        last_frame_for_vlm = frame.copy()
                        vlm_thread = threading.Thread(
                            target=vlm_worker,
                            args=(last_frame_for_vlm, scores, vlm_result_queue),
                            daemon=True
                        )
                        vlm_thread.start()
                    
                    # Log data every 10 frames
                    if frame_count % 10 == 0:
                        data_logger.log_frame(
                            frame_count,
                            scores,
                            fatigue_detector.fatigue_level,
                            current_feedback if frame_count % 100 == 0 else None
                        )
                    
                    # Draw overlays
                    frame = draw_comprehensive_overlay(
                        frame,
                        scores,
                        fatigue_warning,
                        metronome.enabled,
                        current_feedback
                    )
                    
                    # Draw keypoints
                    for i, (person_kps, color) in enumerate([(rescuer_kps, (0, 255, 0)), 
                                                              (victim_kps, (255, 0, 0))]):
                        for kp in person_kps:
                            if kp[0] > 0 and kp[1] > 0:
                                x, y = int(kp[0] * frame_width), int(kp[1] * frame_height)
                                cv2.circle(frame, (x, y), 4, color, -1)
                
                else:
                    # No detection
                    cv2.putText(frame, "No CPR Activity Detected", (50, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
                    
            except Exception as e:
                print(f"❌ Error processing detection: {e}")
                cv2.putText(frame, "System Error - Restart Required", (50, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            # FPS counter
            elapsed = time.time() - start_time
            fps = frame_count / elapsed if elapsed > 0 else 0
            cv2.putText(frame, f"FPS: {fps:.1f}", (frame_width - 120, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Display
            cv2.imshow('Advanced CPR Assessment System', frame)
            
            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                print("🛑 Quitting...")
                break
            elif key == ord('m'):
                enabled = metronome.toggle()
                status = "ON" if enabled else "OFF"
                print(f"🎵 Metronome: {status}")
            elif key == ord(' '):
                if vlm_thread is None or not vlm_thread.is_alive():
                    print("🔍 Manual feedback request")
                    if 'scores' in locals():
                        last_frame_for_vlm = frame.copy()
                        vlm_thread = threading.Thread(
                            target=vlm_worker,
                            args=(last_frame_for_vlm, scores, vlm_result_queue),
                            daemon=True
                        )
                        vlm_thread.start()
            elif key == ord('r'):
                print("🔄 Resetting session...")
                cpr_metrics = ImprovedCPRMetrics()
                fatigue_detector = FatigueDetector()
                current_feedback = None
                frame_count = 0
                start_time = time.time()
    
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    
    finally:
        # Cleanup
        cap.release()
        cv2.destroyAllWindows()
        pygame.mixer.quit()
        
        # Print session summary
        print("\n" + "="*50)
        print("📊 SESSION SUMMARY")
        print("="*50)
        print(f"Duration: {int(time.time() - start_time)}s")
        print(f"Total Frames: {frame_count}")
        print(f"Total Compressions: {cpr_metrics.compression_count}")
        print(f"Feedback Events: {feedback_mgr.feedback_count}")
        print(f"Log File: {LOG_FILE}")
        print("="*50)

if __name__ == "__main__":
    main()