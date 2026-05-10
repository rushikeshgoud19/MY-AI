import cv2
import os
import time
from datetime import datetime

def register_master():
    print("Initializing camera...")
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return
        
    # Use Haar Cascade for face detection (built into OpenCV, no dlib needed)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    print("Camera started. Look at the camera.")
    print("Press 's' to capture multiple samples and register Master.")
    print("Press 'q' to quit without saving.")

    sample_count = 12
    capture_interval = 0.5
    bright_alpha = 1.5
    bright_beta = 30
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame.")
            break
            
        display_frame = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        
        for (x, y, w, h) in faces:
            cv2.rectangle(display_frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
            
        cv2.putText(display_frame, "Press 's' to capture samples", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(display_frame, "Press 'q' to Quit", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        cv2.imshow("Register Master Face", display_frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            print("Operation cancelled.")
            break
        elif key == ord('s'):
            if len(faces) == 0:
                print("No face detected! Please ensure your face is clearly visible in the blue box.")
                continue
            elif len(faces) > 1:
                print("Multiple faces detected! Please ensure only YOU are in the frame.")
                continue

            data_dir = "data"
            faces_dir = os.path.join(data_dir, "master_faces")
            os.makedirs(faces_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            print(f"Capturing {sample_count} samples...")
            captured = 0
            for i in range(sample_count):
                ret, frame = cap.read()
                if not ret:
                    continue

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.3, 5)
                if len(faces) != 1:
                    time.sleep(capture_interval)
                    continue

                (x, y, w, h) = faces[0]
                pad = 20
                y1 = max(0, y - pad)
                y2 = min(frame.shape[0], y + h + pad)
                x1 = max(0, x - pad)
                x2 = min(frame.shape[1], x + w + pad)
                face_crop = frame[y1:y2, x1:x2]
                if face_crop.size == 0:
                    time.sleep(capture_interval)
                    continue

                base_name = f"master_{timestamp}_{captured:02d}.jpg"
                save_path = os.path.join(faces_dir, base_name)
                cv2.imwrite(save_path, face_crop)

                # Save a brighter variant for dim lighting
                bright = cv2.convertScaleAbs(face_crop, alpha=bright_alpha, beta=bright_beta)
                bright_path = os.path.join(faces_dir, f"master_{timestamp}_{captured:02d}_bright.jpg")
                cv2.imwrite(bright_path, bright)

                captured += 1
                time.sleep(capture_interval)

            if captured == 0:
                print("No valid samples captured. Try again with better lighting.")
                continue

            # Keep a legacy copy for compatibility
            legacy_path = os.path.join(data_dir, "master_face.jpg")
            try:
                cv2.imwrite(legacy_path, face_crop)
            except Exception:
                pass

            print(f"Success! Captured {captured} samples in {faces_dir}")
            cv2.putText(display_frame, "MASTER REGISTERED", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow("Register Master Face", display_frame)
            cv2.waitKey(1500)
            break
            
    cap.release()
    cv2.destroyAllWindows()
    
if __name__ == "__main__":
    register_master()
