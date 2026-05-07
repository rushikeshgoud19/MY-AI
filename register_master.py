import cv2
import os

def register_master():
    print("Initializing camera...")
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return
        
    # Use Haar Cascade for face detection (built into OpenCV, no dlib needed)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    print("Camera started. Look at the camera.")
    print("Press 's' to take a picture and save it as Master.")
    print("Press 'q' to quit without saving.")
    
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
            
        cv2.putText(display_frame, "Press 's' to Save face", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
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
                
            print("Processing image...")
            # Extract the face
            (x, y, w, h) = faces[0]
            # Add some padding around the face
            pad = 20
            y1 = max(0, y - pad)
            y2 = min(frame.shape[0], y + h + pad)
            x1 = max(0, x - pad)
            x2 = min(frame.shape[1], x + w + pad)
            
            master_face = frame[y1:y2, x1:x2]
            
            # Save the face image
            data_dir = "data"
            os.makedirs(data_dir, exist_ok=True)
            save_path = os.path.join(data_dir, "master_face.jpg")
            
            cv2.imwrite(save_path, master_face)
            print(f"Success! Master's face has been registered and saved to {save_path}")
            
            # Show success message
            cv2.putText(display_frame, "MASTER REGISTERED", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow("Register Master Face", display_frame)
            cv2.waitKey(2000)
            break
            
    cap.release()
    cv2.destroyAllWindows()
    
if __name__ == "__main__":
    register_master()
