import os
import cv2
import threading
import time
import logging
from collections import Counter
from typing import Optional, Any
from agents.base_agent import BaseAgent

try:
    from deepface import DeepFace
    HAS_DEEPFACE = True
except ImportError:
    HAS_DEEPFACE = False

try:
    import mediapipe as mp
    HAS_MEDIAPIPE = True
except ImportError:
    HAS_MEDIAPIPE = False


class CameraAgent(BaseAgent):
    def __init__(self, config: dict):
        super().__init__(config)
        # ── Auth state ──
        self.is_master_present = False
        self.current_gesture = None
        self.master_emotion = "neutral"

        # ── Greeting / Warning flags ──
        self.has_greeted = False
        self.has_warned_unauthorized = False
        self.last_greet_time = 0
        self.last_warn_time = 0

        # ── Re-verification tracking ──
        self.reverify_fail_count = 0    # consecutive re-verify failures while authenticated

        # ── "No face" tracker ──
        self.no_face_count = 0

        # ── Callbacks (set by server.py) ──
        self.on_master_greet = None
        self.on_unauthorized_user = None
        self.on_sustained_emotion = None
        self.on_emotion_update = None
        self.on_master_missing = None    # fires when master disappears from camera
        self.has_called_missing = False  # prevent spam

        # ── Continuous emotion tracker ──
        self.emotion_history = []
        self.last_sustained_emotion = None
        self.last_sustained_alert_time = 0

        # ── Internal ──
        self.running = False
        self.thread = None
        self.cap = None
        self.cap_lock = threading.Lock()
        self.master_face_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "data", "master_face.jpg"
        )
        self.temp_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "data", "temp_frame.jpg"
        )

        if not os.path.exists(self.master_face_path):
            self.log("Master face not found. Please run register_master.py")

        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

    # ─── Lifecycle ─────────────────────────────────────────────────────────────
    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._camera_loop, daemon=True)
        self.thread.start()
        self.log("Camera agent background thread started.")

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()

    # ─── Main Loop ─────────────────────────────────────────────────────────────
    def _camera_loop(self):
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(0)

        if not self.cap.isOpened():
            self.log("ERROR: Could not open webcam!")
            return

        # MediaPipe hand tracking (optional)
        self.hands = None
        if HAS_MEDIAPIPE:
            try:
                self.mp_hands = mp.solutions.hands
                self.hands = self.mp_hands.Hands(
                    static_image_mode=False,
                    max_num_hands=2,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5
                )
            except AttributeError:
                self.log("MediaPipe 'solutions' not found. Disabling gestures for now.")

        # ── Warmup: throw away the first 5 seconds of blurry/dark frames ──
        warmup_end = time.time() + 5.0
        while self.running and time.time() < warmup_end:
            with self.cap_lock:
                self.cap.read()
            time.sleep(0.1)
        self.log("Camera warmup complete. Starting authentication.")

        last_auth_time = 0          # for initial auth (every 4s when NOT authenticated)
        last_reverify_time = 0      # for silent re-verify (every 20s when IS authenticated)
        last_emotion_time = 0       # for emotion tracking (every 1.5s)

        while self.running:
            if not self.cap.isOpened():
                time.sleep(1)
                continue

            with self.cap_lock:
                ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            now = time.time()

            # 1. Gesture Recognition
            if self.hands:
                self._detect_gestures(frame)

            # ── AUTHENTICATION STATE MACHINE ──
            if not self.is_master_present:
                # STATE: NOT AUTHENTICATED
                # Try to find and verify master every 4 seconds
                if now - last_auth_time > 4.0:
                    last_auth_time = now
                    self._try_authenticate(frame)

            else:
                # STATE: AUTHENTICATED
                # A) Check face presence & re-verify every 5 seconds
                if now - last_reverify_time > 5.0:
                    last_reverify_time = now
                    self._silent_reverify(frame)

                # B) Track emotion every 1.5 seconds
                if now - last_emotion_time > 1.5:
                    last_emotion_time = now
                    self._track_emotion(frame)

            time.sleep(0.1)  # ~10 FPS

    # ─── Gesture Detection ─────────────────────────────────────────────────────
    def _detect_gestures(self, frame):
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(rgb_frame)
            if results.multi_hand_landmarks:
                self.current_gesture = "hands_detected"
            else:
                self.current_gesture = None
        except Exception:
            self.current_gesture = None

    # ─── Initial Authentication (when NOT authenticated) ───────────────────────
    def _try_authenticate(self, frame):
        """Runs every 4s when is_master_present is False.
        Crops the largest face from the frame and compares to master_face.jpg."""
        if not HAS_DEEPFACE or not os.path.exists(self.master_face_path):
            return

        # Detect faces first
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.2, 3)
        if len(faces) == 0:
            return  # Nobody there

        # Pick the LARGEST face (most likely the person sitting at the desk)
        largest = max(faces, key=lambda f: f[2] * f[3])
        (x, y, w, h) = largest

        # Crop with generous padding (match register_master.py style)
        pad = int(max(w, h) * 0.3)
        y1, y2 = max(0, y - pad), min(frame.shape[0], y + h + pad)
        x1, x2 = max(0, x - pad), min(frame.shape[1], x + w + pad)
        face_crop = frame[y1:y2, x1:x2]

        if face_crop.size == 0:
            return

        try:
            cv2.imwrite(self.temp_path, face_crop)
            result = DeepFace.verify(
                img1_path=self.temp_path,
                img2_path=self.master_face_path,
                enforce_detection=False,
                model_name="VGG-Face",
                threshold=0.30  # Stricter than default 0.40 — prevents friend misidentification
            )
            is_verified = result.get("verified", False)
            distance = result.get("distance", -1)
            self.log(f"Auth check: verified={is_verified}, distance={distance:.3f} (threshold=0.30)")
        except Exception:
            return

        now = time.time()

        if is_verified:
            # ── MASTER FOUND ──
            self.is_master_present = True
            self.no_face_count = 0
            self.reverify_fail_count = 0
            self.has_warned_unauthorized = False

            # Scan emotion FIRST before greeting
            try:
                analysis = DeepFace.analyze(
                    img_path=self.temp_path,
                    actions=['emotion'],
                    enforce_detection=False
                )
                if isinstance(analysis, list):
                    analysis = analysis[0]
                emotion_scores = analysis.get('emotion', {})
                detected = analysis.get('dominant_emotion', 'neutral')
                happy_score = emotion_scores.get('happy', 0)
                if happy_score > 25 and detected != 'happy':
                    detected = 'happy'
                self.master_emotion = detected
            except Exception:
                pass

            self.log(f"Master authenticated. Emotion: {self.master_emotion}")

            # Greet with cooldown (30 seconds)
            if not self.has_greeted or (now - self.last_greet_time > 30):
                self.has_greeted = True
                self.last_greet_time = now
                if self.on_master_greet:
                    self.on_master_greet(self.master_emotion)
        else:
            # ── STRANGER ──
            if not self.has_warned_unauthorized and (now - self.last_warn_time > 60):
                self.has_warned_unauthorized = True
                self.last_warn_time = now
                self.log("WARNING: Unauthorized user detected!")
                if self.on_unauthorized_user:
                    self.on_unauthorized_user()

    # ─── Silent Re-verification (when IS authenticated) ────────────────────────
    def _silent_reverify(self, frame):
        """Runs every 20s while authenticated. Catches friend-swap.
        Crops the largest face and compares to master. Needs 3 consecutive
        failures (60 seconds) before silently locking."""

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.2, 3)

        if len(faces) == 0:
            self.no_face_count += 1
            
            # After 2 checks (10 seconds) with no face — call out for master
            if self.no_face_count >= 2 and not self.has_called_missing:
                self.has_called_missing = True
                self.log("Master is not visible! Calling out...")
                if self.on_master_missing:
                    self.on_master_missing()
            
            # After 24 checks (2 minutes) with no face — fully de-auth
            if self.no_face_count >= 24:
                self.log("Master left for too long. Locking.")
                self._silent_deauth()
            return

        self.no_face_count = 0
        self.has_called_missing = False  # Master is visible again, reset

        if not HAS_DEEPFACE or not os.path.exists(self.master_face_path):
            return

        # Crop the largest face for comparison
        largest = max(faces, key=lambda f: f[2] * f[3])
        (x, y, w, h) = largest
        pad = int(max(w, h) * 0.3)
        y1, y2 = max(0, y - pad), min(frame.shape[0], y + h + pad)
        x1, x2 = max(0, x - pad), min(frame.shape[1], x + w + pad)
        face_crop = frame[y1:y2, x1:x2]

        if face_crop.size == 0:
            return

        try:
            cv2.imwrite(self.temp_path, face_crop)
            result = DeepFace.verify(
                img1_path=self.temp_path,
                img2_path=self.master_face_path,
                enforce_detection=False,
                model_name="VGG-Face",
                threshold=0.30
            )
            is_verified = result.get("verified", False)
        except Exception:
            return

        if is_verified:
            self.reverify_fail_count = 0
        else:
            self.reverify_fail_count += 1
            if self.reverify_fail_count >= 3:
                self.log("Someone else is sitting here. Silently locking.")
                self._silent_deauth()

    def _silent_deauth(self):
        """Silently remove authentication without yelling. The security gate in
        process_command will block any commands from the stranger."""
        self.is_master_present = False
        self.has_greeted = False
        self.has_warned_unauthorized = False
        self.reverify_fail_count = 0
        self.no_face_count = 0
        self.emotion_history.clear()

    # ─── Continuous Emotion Tracking ───────────────────────────────────────────
    def _track_emotion(self, frame):
        """Runs every 1.5 seconds when master is present."""
        if not HAS_DEEPFACE:
            return

        try:
            analysis = DeepFace.analyze(
                img_path=frame,
                actions=['emotion'],
                enforce_detection=False
            )
            if isinstance(analysis, list):
                analysis = analysis[0]

            emotion_scores = analysis.get('emotion', {})
            detected = analysis.get('dominant_emotion', 'neutral')

            # ── Grin detection: if happy score is notable but not dominant ──
            happy_score = emotion_scores.get('happy', 0)
            if happy_score > 25 and detected != 'happy':
                detected = 'happy'  # Treat grins/smirks as happy

        except Exception:
            return

        self.master_emotion = detected
        now = time.time()

        # Notify frontend HUD
        if self.on_emotion_update:
            self.on_emotion_update(detected)

        # Record in history
        self.emotion_history.append((now, detected))

        # Trim history older than 3 minutes
        cutoff = now - 180
        self.emotion_history = [(t, e) for t, e in self.emotion_history if t >= cutoff]

        # ── Sustained emotion check (2+ minutes of same emotion) ──
        two_min_ago = now - 120
        recent = [e for t, e in self.emotion_history if t >= two_min_ago]

        if len(recent) < 40:
            return

        counts = Counter(recent)
        dominant, dominant_count = counts.most_common(1)[0]
        ratio = dominant_count / len(recent)

        if ratio >= 0.70 and dominant != "neutral":
            if dominant != self.last_sustained_emotion or (now - self.last_sustained_alert_time > 300):
                self.last_sustained_emotion = dominant
                self.last_sustained_alert_time = now
                self.log(f"Sustained emotion detected: {dominant} ({ratio*100:.0f}% over 2 min)")
                if self.on_sustained_emotion:
                    self.on_sustained_emotion(dominant)

    # ─── Instant Master Verification (called by process_command) ─────────────
    def verify_master_now(self):
        """Do an INSTANT face check. Returns True only if master is verified RIGHT NOW."""
        if not self.cap or not self.cap.isOpened():
            return self.is_master_present  # Can't check, trust last state
        if not HAS_DEEPFACE or not os.path.exists(self.master_face_path):
            return self.is_master_present

        with self.cap_lock:
            ret, frame = self.cap.read()
        if not ret:
            return self.is_master_present

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.2, 3)
        if len(faces) == 0:
            return False  # Nobody in front of camera

        largest = max(faces, key=lambda f: f[2] * f[3])
        (x, y, w, h) = largest
        pad = int(max(w, h) * 0.3)
        y1, y2 = max(0, y - pad), min(frame.shape[0], y + h + pad)
        x1, x2 = max(0, x - pad), min(frame.shape[1], x + w + pad)
        face_crop = frame[y1:y2, x1:x2]

        if face_crop.size == 0:
            return False

        try:
            cv2.imwrite(self.temp_path, face_crop)
            result = DeepFace.verify(
                img1_path=self.temp_path,
                img2_path=self.master_face_path,
                enforce_detection=False,
                model_name="VGG-Face",
                threshold=0.30
            )
            return result.get("verified", False)
        except Exception:
            return self.is_master_present  # On error, trust last state

    # ─── Capture Frame for Vision Queries ─────────────────────────────────────
    def get_current_frame(self):
        """Capture a single frame from the webcam and return as JPEG bytes."""
        if not self.cap or not self.cap.isOpened():
            return None
        with self.cap_lock:
            ret, frame = self.cap.read()
        if not ret:
            return None
        # Encode to JPEG bytes
        success, buf = cv2.imencode('.jpg', frame)
        if success:
            return buf.tobytes()
        return None

    # ─── Execute (for agent system) ────────────────────────────────────────────
    async def execute(self, task_input: str, context: Optional[dict] = None) -> Any:
        return {
            "is_master_present": self.is_master_present,
            "current_gesture": self.current_gesture,
            "master_emotion": self.master_emotion
        }
