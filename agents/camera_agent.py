import os
import cv2
import threading
import time
import logging
import numpy as np
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

        # ── Performance cache ──
        self._last_dim_check_time = 0
        self._last_dim_result = False
        self._dim_log_time = 0           # throttle log spam
        self.last_verified_time = 0       # when background loop last confirmed master

        # ── Internal ──
        self.running = False
        self.thread = None
        self.cap = None
        self.cap_lock = threading.Lock()
        self.master_face_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "data", "master_face.jpg"
        )
        self.master_faces_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "data", "master_faces"
        )
        self.temp_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "data", "temp_frame.jpg"
        )
        self.master_face_paths = self._load_master_face_paths()
        if not self.master_face_paths:
            self.log("Master face not found. Please run register_master.py")

        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

    def _load_master_face_paths(self):
        paths = []
        if os.path.isdir(self.master_faces_dir):
            for name in sorted(os.listdir(self.master_faces_dir)):
                if name.lower().endswith(('.jpg', '.jpeg', '.png')):
                    paths.append(os.path.join(self.master_faces_dir, name))
        if os.path.exists(self.master_face_path):
            paths.append(self.master_face_path)
        return paths

    def _verify_against_master(self) -> tuple[bool, float]:
        if not self.master_face_paths:
            self.master_face_paths = self._load_master_face_paths()
        best_distance = 9.0
        for path in self.master_face_paths:
            try:
                result = DeepFace.verify(
                    img1_path=self.temp_path,
                    img2_path=path,
                    enforce_detection=False,
                    model_name="Facenet",
                    threshold=0.40
                )
                distance = result.get("distance", 9.0)
                best_distance = min(best_distance, distance)
                if result.get("verified", False):
                    return True, best_distance
            except Exception:
                continue
        return False, best_distance

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
        last_reverify_time = 0      # for silent re-verify (every 30s when IS authenticated)
        last_emotion_time = 0       # for emotion tracking (every 2s)

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
                # A) Check face presence & re-verify every 30 seconds
                if now - last_reverify_time > 30.0:
                    last_reverify_time = now
                    self._silent_reverify(frame)

                # B) Track emotion every 2 seconds
                if now - last_emotion_time > 2.0:
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

    def _enhance_low_light(self, frame):
        """Improve visibility in dim light using CLAHE + gamma adjustment."""
        try:
            yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV)
            y_channel = yuv[:, :, 0]
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            yuv[:, :, 0] = clahe.apply(y_channel)
            enhanced = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)

            gamma = 1.3
            inv_gamma = 1.0 / gamma
            table = (np.power((np.arange(256) / 255.0), inv_gamma) * 255).astype("uint8")
            enhanced = cv2.LUT(enhanced, table)
            return enhanced
        except Exception:
            return frame

    def _is_dim(self, frame, threshold=80):
        """Return True if the frame's average brightness is below `threshold`.
        Result is cached for 10 seconds to avoid redundant computation."""
        now = time.time()
        if now - self._last_dim_check_time < 10.0:
            return self._last_dim_result
        try:
            yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV)
            mean_brightness = float(yuv[:, :, 0].mean())
            self._last_dim_result = mean_brightness < threshold
            self._last_dim_check_time = now
            return self._last_dim_result
        except Exception:
            return False

    def _prepare_frame(self, frame):
        """Return an enhanced copy when lighting is dim, otherwise the raw frame."""
        if self._is_dim(frame):
            now = time.time()
            # Throttle log: only once per 30 seconds
            if now - self._dim_log_time > 30.0:
                self.log("Low light detected — applying CLAHE + gamma boost.")
                self._dim_log_time = now
            return self._enhance_low_light(frame)
        return frame

    # ─── Initial Authentication (when NOT authenticated) ───────────────────────
    def _try_authenticate(self, frame):
        """Runs every 4s when is_master_present is False.
        Crops the largest face from the frame and compares to master_face.jpg.
        Uses CLAHE-boosted frame in dim lighting for reliable detection."""
        if not HAS_DEEPFACE or not self.master_face_paths:
            return

        # Use enhanced frame if dim, raw frame otherwise
        working = self._prepare_frame(frame)

        # Detect faces on the (possibly boosted) frame
        gray = cv2.cvtColor(working, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.2, 3)
        if len(faces) == 0:
            return  # Nobody there

        # Pick the LARGEST face (most likely the person sitting at the desk)
        largest = max(faces, key=lambda f: f[2] * f[3])
        (x, y, w, h) = largest

        # Crop with generous padding (match register_master.py style)
        pad = int(max(w, h) * 0.3)
        y1, y2 = max(0, y - pad), min(working.shape[0], y + h + pad)
        x1, x2 = max(0, x - pad), min(working.shape[1], x + w + pad)
        face_crop = working[y1:y2, x1:x2]

        if face_crop.size == 0:
            return

        try:
            cv2.imwrite(self.temp_path, face_crop)
            is_verified, distance = self._verify_against_master()
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

            # Scan emotion FIRST before greeting (use boosted crop already saved)
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

            self.last_verified_time = time.time()  # Track for fast verify_master_now
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
        """Runs every 30s while authenticated. Catches friend-swap.
        Crops the largest face and compares to master. Needs 3 consecutive
        failures before silently locking.
        Uses CLAHE-boosted frame in dim lighting."""

        # Use enhanced frame if dim, raw frame otherwise
        working = self._prepare_frame(frame)

        gray = cv2.cvtColor(working, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.2, 3)

        if len(faces) == 0:
            self.no_face_count += 1
            
            # After 4 checks (~2 minutes) with no face — call out for master
            if self.no_face_count >= 4 and not self.has_called_missing:
                self.has_called_missing = True
                self.log("Master is not visible! Calling out...")
                if self.on_master_missing:
                    self.on_master_missing()
            
            # After 10 checks (~5 minutes) with no face — fully de-auth
            if self.no_face_count >= 10:
                self.log("Master left for too long. Locking.")
                self._silent_deauth()
            return

        self.no_face_count = 0
        self.has_called_missing = False  # Master is visible again, reset

        if not HAS_DEEPFACE or not self.master_face_paths:
            return

        # Crop the largest face for comparison (from boosted frame)
        largest = max(faces, key=lambda f: f[2] * f[3])
        (x, y, w, h) = largest
        pad = int(max(w, h) * 0.3)
        y1, y2 = max(0, y - pad), min(working.shape[0], y + h + pad)
        x1, x2 = max(0, x - pad), min(working.shape[1], x + w + pad)
        face_crop = working[y1:y2, x1:x2]

        if face_crop.size == 0:
            return

        try:
            cv2.imwrite(self.temp_path, face_crop)
            is_verified, _ = self._verify_against_master()
        except Exception:
            return

        if is_verified:
            self.reverify_fail_count = 0
            self.last_verified_time = time.time()  # Track for fast verify_master_now
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
        """Runs every 1.5 seconds when master is present.
        Uses CLAHE-boosted frame in dim lighting for reliable emotion reads."""
        if not HAS_DEEPFACE:
            return

        # Use enhanced frame if dim, raw frame otherwise
        working = self._prepare_frame(frame)

        try:
            analysis = DeepFace.analyze(
                img_path=working,
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
        """Fast master check. If the background loop verified master recently
        (within 35 seconds), trust that result to avoid blocking the command.
        Otherwise fall back to a full LIVE check.
        Uses CLAHE-boosted frame in dim lighting."""
        # FAST PATH: trust background loop if verified recently (within 35s)
        if self.is_master_present and (time.time() - self.last_verified_time < 35.0):
            return True

        if not self.cap or not self.cap.isOpened():
            return self.is_master_present  # Can't check, trust last state
        if not HAS_DEEPFACE or not self.master_face_paths:
            return self.is_master_present

        with self.cap_lock:
            ret, frame = self.cap.read()
        if not ret:
            return self.is_master_present

        # Use enhanced frame if dim, raw frame otherwise
        working = self._prepare_frame(frame)

        gray = cv2.cvtColor(working, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.2, 3)
        if len(faces) == 0:
            return False  # Nobody in front of camera

        largest = max(faces, key=lambda f: f[2] * f[3])
        (x, y, w, h) = largest
        pad = int(max(w, h) * 0.3)
        y1, y2 = max(0, y - pad), min(working.shape[0], y + h + pad)
        x1, x2 = max(0, x - pad), min(working.shape[1], x + w + pad)
        face_crop = working[y1:y2, x1:x2]

        if face_crop.size == 0:
            return False

        try:
            cv2.imwrite(self.temp_path, face_crop)
            is_verified, _ = self._verify_against_master()
            if is_verified:
                self.last_verified_time = time.time()
            return is_verified
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
