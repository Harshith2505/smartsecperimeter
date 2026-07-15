import cv2
import numpy as np
import time
import threading
import os
import math
from ultralytics import YOLO
import mediapipe as mp

# Import your custom detached email module
from notifier import send_burst_email_alert

# Global Configuration & Signals
WINDOW_NAME = "Smart Security Perimeter"
roi_pts = []
last_alert_time = 0
ALERT_COOLDOWN_SECONDS = 20  # Cooldown long enough to process a full burst and dispatch
alarm_muted = False         
mute_start_time = 0
MUTE_DURATION_SECONDS = 15  

# --- Thread Control Signal ---
stop_alarm_signal = threading.Event()

# Try to import a native audio playing utility based on OS
try:
    if os.name == 'nt':  # Windows
        import winsound
        def play_alarm_sound():
            winsound.PlaySound("siren.wav", winsound.SND_FILENAME | winsound.SND_ASYNC)
            start_play = time.time()
            while time.time() - start_play < 2.5: 
                if stop_alarm_signal.is_set():
                    winsound.PlaySound(None, winsound.SND_PURGE) 
                    break
                time.sleep(0.1)
    else:  # Mac / Linux
        import subprocess
        def play_alarm_sound():
            cmd = "afplay alarm.wav" if os.sys.platform == "darwin" else "aplay alarm.wav"
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            start_play = time.time()
            while time.time() - start_play < 2.5:
                if stop_alarm_signal.is_set():
                    proc.terminate() 
                    break
                time.sleep(0.1)
except Exception:
    def play_alarm_sound():
        if not stop_alarm_signal.is_set():
            print("\a") 

# =========================================================================
# 👤 FAST MATHEMATICAL FACIAL MATCHING ENGINE (NO CV2.FACE DEPENDENCY)
# =========================================================================
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

reference_face_templates = []
known_face_names = []
FACES_DIR = "authorized_faces"

print("🔄 [FACIAL DATABASE] Indexing authorized personnel using Pixel Matrix Matcher...")
if not os.path.exists(FACES_DIR):
    os.makedirs(FACES_DIR)
    print(f"📁 Created '{FACES_DIR}' folder. Drop authorized face pictures here!")

for file_name in os.listdir(FACES_DIR):
    if file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
        path = os.path.join(FACES_DIR, file_name)
        name = ''.join([i for i in os.path.splitext(file_name)[0] if not i.isdigit()]).upper()
        
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
            
        detected_faces = face_cascade.detectMultiScale(img, 1.1, 4)
        for (x, y, w, h) in detected_faces:
            # Crop the face and resize it to a uniform standard matrix size (e.g., 100x100)
            face_slice = cv2.resize(img[y:y+h, x:x+w], (100, 100))
            reference_face_templates.append(face_slice)
            known_face_names.append(name)
            print(f"   └── Trained face matrix template for: {name}")

is_trained = len(reference_face_templates) > 0
if is_trained:
    print(f"✅ Total Whitelisted Profiles Loaded: {len(set(known_face_names))}\n")
else:
    print("⚠️ [FACIAL DATABASE] No whitelisted faces found. System will alert all targets.")

def verify_face_identity(live_face_roi):
    """
    Computes structural closeness via Mean Squared Error (MSE) against whitelisted templates.
    """
    if not is_trained or live_face_roi.size == 0:
        return None
        
    # Standardize the live captured image size to match our database templates
    live_face_resized = cv2.resize(live_face_roi, (100, 100))
    
    best_match_name = None
    lowest_mse = float('inf')
    
    for template, name in zip(reference_face_templates, known_face_names):
        # Calculate Mean Squared Error (MSE) between images
        err = np.sum((live_face_resized.astype("float") - template.astype("float")) ** 2)
        err /= float(live_face_resized.shape[0] * live_face_resized.shape[1])
        
        if err < lowest_mse:
            lowest_mse = err
            best_match_name = name
            
    # MSE threshold (lower means tighter match). 4500-5500 is optimal for light variations
    if lowest_mse < 5000:
        return best_match_name
    return None

# Targeted Entity Profiles (0: Person, 15: Cat, 16: Dog, 17: Horse, 18: Sheep, 19: Cow)
TARGET_CLASSES = {0, 15, 16, 17, 18, 19}

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(min_detection_confidence=0.6, min_tracking_confidence=0.5, max_num_hands=2)
mp_draw = mp.solutions.drawing_utils

def check_ok_gesture(hand_landmarks):
    lm = hand_landmarks.landmark
    dx = lm[4].x - lm[8].x
    dy = lm[4].y - lm[8].y
    tip_distance = math.sqrt(dx**2 + dy**2)
    
    middle_extended = lm[12].y < lm[10].y
    ring_extended = lm[16].y < lm[14].y
    pinky_extended = lm[20].y < lm[18].y
    
    if tip_distance < 0.045 and middle_extended and ring_extended and pinky_extended:
        return True
    return False

def draw_roi(event, x, y, flags, param):
    global roi_pts
    if event == cv2.EVENT_LBUTTONDOWN:
        if len(roi_pts) >= 4:
            roi_pts = []
        roi_pts.append((x, y))

# --- Continuous Flutter Shot Burst Worker ---
def async_alert_worker(target_label, timestamp_str, initial_frame, camera_capture):
    try:
        log_file = "security_logs.csv"
        file_exists = os.path.isfile(log_file)
        
        with open(log_file, mode="a", encoding="utf-8") as f:
            if not file_exists:
                f.write("Timestamp,Target,Status\n")
            f.write(f"{timestamp_str},{target_label},BREACH\n")
        
        print(f"📁 [LOGGED] Threat profile saved for [{target_label}]")
        print("📸 [BURST] Starting continuous 5-shot flutter sequence (0.45s gap)...")
        
        image_paths = []
        p1 = f"burst_1.jpg"
        cv2.imwrite(p1, initial_frame)
        image_paths.append(p1)
        
        for i in range(2, 6):
            time.sleep(0.45)
            ret, burst_frame = camera_capture.read()
            if ret:
                p_current = f"burst_{i}.jpg"
                cv2.imwrite(p_current, burst_frame)
                image_paths.append(p_current)
        
        send_burst_email_alert(target_label, timestamp_str, image_paths)
        
        if not stop_alarm_signal.is_set():
            play_alarm_sound()
            
    except Exception as e:
        print(f"Error handling burst alert tasks: {e}")

# System Initialization
model = YOLO("yolov8n.pt")
cap = cv2.VideoCapture(0)

cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
cv2.setMouseCallback(WINDOW_NAME, draw_roi)

print("\n--- PERIMETER MONITORING ARMED ---")
print("Controls: \n -> Click 4 points on screen to map boundary.")
print(" -> Press 'r' to reset boundary live.")
print(" -> Press 'q' to quit execution.")
print(" -> Show OK sign (👌) to terminate sound and mute alerts instantly.\n")

fps_start_time = time.time()
fps_counter = 0

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    if alarm_muted:
        if time.time() - mute_start_time > MUTE_DURATION_SECONDS:
            alarm_muted = False
            stop_alarm_signal.clear() 
            print("🔊 [SYSTEM RE-ARMED] Perimeter monitoring is active.")

    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # 1. Process Hand Gestures
    hand_results = hands.process(rgb_frame)
    if hand_results.multi_hand_landmarks:
        for hand_lms in hand_results.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame, hand_lms, mp_hands.HAND_CONNECTIONS)
            if check_ok_gesture(hand_lms):
                stop_alarm_signal.set() 
                if not alarm_muted:
                    alarm_muted = True
                    mute_start_time = time.time()
                    print(f"🔕 [INSTANT KILL] Gesture received. Stopping active audio stream.")

    # 2. Run Object Predictions
    results = model.predict(frame, conf=0.4, verbose=False)

    # 3. Process Geofencing Boundary Collision
    if len(roi_pts) < 4:
        for pt in roi_pts:
            cv2.circle(frame, pt, 6, (0, 255, 0), -1)
    elif len(roi_pts) == 4:
        pts_array = np.array(roi_pts, np.int32).reshape((-1, 1, 2))
        
        if alarm_muted:
            zone_color = (0, 255, 255) 
            countdown_left = int(MUTE_DURATION_SECONDS - (time.time() - mute_start_time))
            zone_label = f"ALARM MUTED ({max(0, countdown_left)}s)"
        else:
            zone_color = (255, 255, 0) 
            zone_label = "ZONE ARMED"
            
        is_breached = False
        breach_name = "Target"

        boxes_object = results[0].boxes
        if boxes_object is not None and len(boxes_object) > 0:
            boxes = boxes_object.xyxy.cpu().numpy()
            classes = boxes_object.cls.int().cpu().numpy()

            for box, cls in zip(boxes, classes):
                if cls not in TARGET_CLASSES:
                    continue
                
                x1, y1, x2, y2 = map(int, box)
                check_points = [
                    (int((x1 + x2) / 2), y2),
                    (int((x1 + x2) / 2), int((y1 + y2) / 2)),
                    (int((x1 + x2) / 2), y1 + 15)
                ]
                
                inside_zone = False
                for pt in check_points:
                    if cv2.pointPolygonTest(pts_array, pt, False) >= 0:
                        inside_zone = True
                        break
                
                label_text = "Person" if cls == 0 else f"Animal_{cls}"
                
                # --- NEW RE-ENGINEERED FACIAL RECOGNITION MATCHING ---
                if inside_zone and cls == 0 and is_trained:
                    crop_y1, crop_y2 = max(0, y1), min(frame.shape[0], y2)
                    crop_x1, crop_x2 = max(0, x1), min(frame.shape[1], x2)
                    person_crop = gray_frame[crop_y1:crop_y2, crop_x1:crop_x2]
                    
                    if person_crop.size > 0:
                        detected_faces = face_cascade.detectMultiScale(person_crop, 1.1, 4)
                        for (fx, fy, fw, fh) in detected_faces:
                            face_roi = person_crop[fy:fy+fh, fx:fx+fw]
                            
                            matched_name = verify_face_identity(face_roi)
                            if matched_name:
                                label_text = f"AUTHORIZED: {matched_name}"
                                inside_zone = False # Suppress alarm pipelines

                box_color = (255, 0, 0) if "AUTHORIZED" in label_text else (0, 255, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
                cv2.putText(frame, label_text, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)

                if inside_zone:
                    is_breached = True
                    breach_name = label_text
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)

        # --- ALPHA TRANSPARENT OVERLAY BLOCK ---
        overlay = frame.copy()
        if is_breached and not alarm_muted:
            zone_color = (0, 0, 255) 
            zone_label = f"⚠️ INTRUSION: {breach_name.upper()} DETECTED!"
            cv2.fillPoly(overlay, [pts_array], (0, 0, 255))
        else:
            poly_color = (255, 255, 0) if not alarm_muted else (0, 255, 255)
            cv2.fillPoly(overlay, [pts_array], poly_color)
            
        cv2.addWeighted(overlay, 0.22, frame, 0.78, 0, frame)

        if is_breached and not alarm_muted:
            current_time = time.time()
            if current_time - last_alert_time > ALERT_COOLDOWN_SECONDS:
                last_alert_time = current_time
                timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")
                
                stop_alarm_signal.clear()
                frame_snapshot = frame.copy()
                
                alert_thread = threading.Thread(
                    target=async_alert_worker, 
                    args=(breach_name, timestamp_str, frame_snapshot, cap),
                    daemon=True
                )
                alert_thread.start()

        cv2.polylines(frame, [pts_array], isClosed=True, color=zone_color, thickness=3)
        cv2.putText(frame, zone_label, (roi_pts[0][0], roi_pts[0][1] - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, zone_color, 2)

    # --- REAL-TIME DIAGNOSTICS: FPS CALCULATOR ---
    fps_counter += 1
    elapsed_time = time.time() - fps_start_time
    if elapsed_time > 1.0:
        current_fps = fps_counter / elapsed_time
        fps_start_time = time.time()
        fps_counter = 0
        
    cv2.putText(frame, f"FPS: {current_fps:.1f}" if 'current_fps' in locals() else "FPS: --", 
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    cv2.imshow(WINDOW_NAME, frame)
    
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('r'):  
        roi_pts = []
        print("🔄 [SYSTEM] Perimeter coordinates wiped. Redraw your 4 points.")

cap.release()
cv2.destroyAllWindows()