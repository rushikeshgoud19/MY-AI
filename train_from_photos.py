"""
Train Mizune's face recognition from existing camera photos.
Pass 2: More aggressive — processes MORE photos with relaxed detection to get ~20+ samples.
"""

import cv2
import os
import sys
import numpy as np
from datetime import datetime

SOURCE_DIR = os.path.join("dataset", "camera", "2026-05-07")
OUTPUT_DIR = os.path.join("data", "master_faces")
LEGACY_PATH = os.path.join("data", "master_face.jpg")
TARGET_SAMPLES = 25
BRIGHT_ALPHA = 1.5
BRIGHT_BETA = 30

def main():
    all_files = sorted([
        f for f in os.listdir(SOURCE_DIR)
        if f.lower().endswith(('.jpg', '.jpeg', '.png'))
    ])
    total = len(all_files)
    print(f"Found {total} photos. Target: {TARGET_SAMPLES} face samples.")

    # Check how many samples we already have (from pass 1)
    existing = [f for f in os.listdir(OUTPUT_DIR) if f.startswith("master_") and not f.endswith("_bright.jpg")]
    print(f"Already have {len(existing)} samples from previous run.")

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    )

    # Also try profile face detector for side angles
    profile_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_profileface.xml'
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved = len(existing)
    need = TARGET_SAMPLES - saved

    if need <= 0:
        print(f"Already have {saved} samples. That's enough!")
        return

    print(f"Need {need} more samples. Scanning all {total} photos...")

    # Process every 5th photo (more dense than before)
    step = max(1, total // (need * 3))
    idx = 0
    new_saved = 0

    for filename in all_files[::step]:
        if new_saved >= need:
            break

        filepath = os.path.join(SOURCE_DIR, filename)
        frame = cv2.imread(filepath)
        if frame is None:
            continue

        # Try CLAHE enhancement for dim photos
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean_brightness = float(gray.mean())

        if mean_brightness < 80:
            # Boost dim images
            yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            yuv[:, :, 0] = clahe.apply(yuv[:, :, 0])
            working = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)
            gray = cv2.cvtColor(working, cv2.COLOR_BGR2GRAY)
        else:
            working = frame

        # Try frontal face first (relaxed: scaleFactor=1.1, minNeighbors=2)
        faces = face_cascade.detectMultiScale(gray, 1.1, 2, minSize=(30, 30))

        # If no frontal face, try profile
        if len(faces) == 0:
            faces = profile_cascade.detectMultiScale(gray, 1.1, 2, minSize=(30, 30))
            # Also try flipped for right-side profiles
            if len(faces) == 0:
                flipped = cv2.flip(gray, 1)
                faces_flip = profile_cascade.detectMultiScale(flipped, 1.1, 2, minSize=(30, 30))
                if len(faces_flip) > 0:
                    # Mirror back the coordinates
                    h_img, w_img = gray.shape
                    faces = []
                    for (x, y, w, h) in faces_flip:
                        faces.append((w_img - x - w, y, w, h))
                    faces = np.array(faces)

        if len(faces) == 0:
            continue

        largest = max(faces, key=lambda f: f[2] * f[3])
        (x, y, w, h) = largest

        pad = int(max(w, h) * 0.3)
        y1 = max(0, y - pad)
        y2 = min(working.shape[0], y + h + pad)
        x1 = max(0, x - pad)
        x2 = min(working.shape[1], x + w + pad)
        face_crop = working[y1:y2, x1:x2]

        if face_crop.size == 0:
            continue

        save_name = f"master_{timestamp}_{saved:03d}.jpg"
        cv2.imwrite(os.path.join(OUTPUT_DIR, save_name), face_crop)

        bright = cv2.convertScaleAbs(face_crop, alpha=BRIGHT_ALPHA, beta=BRIGHT_BETA)
        bright_name = f"master_{timestamp}_{saved:03d}_bright.jpg"
        cv2.imwrite(os.path.join(OUTPUT_DIR, bright_name), bright)

        saved += 1
        new_saved += 1
        print(f"  [{saved}/{TARGET_SAMPLES}] {filename} (brightness={mean_brightness:.0f}, face={w}x{h})")

    # Update legacy file
    if new_saved > 0:
        cv2.imwrite(LEGACY_PATH, face_crop)

    all_samples = [f for f in os.listdir(OUTPUT_DIR) if f.startswith("master_") and not f.endswith("_bright.jpg")]
    print(f"\n{'='*50}")
    print(f"TOTAL: {len(all_samples)} master face samples ({len(all_samples)*2} files with bright variants)")
    print(f"New samples added this run: {new_saved}")
    print(f"{'='*50}")
    print("Restart server.py for the new training to take effect.")


if __name__ == "__main__":
    main()
