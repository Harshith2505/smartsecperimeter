📋 Project Summary
This project is an Intelligent Autonomous Edge Surveillance System designed to secure a localized perimeter without relying on expensive cloud infrastructure or generating constant false alarms. By integrating deep learning object detection, geometric geofencing, native computer vision verification, and real-time multi-threaded notification pipelines, the system acts as a fully automated security guard.

🏗️ Technical Architecture & Pipeline
The application runs as a continuous processing pipeline, moving through five distinct phases in real time:

[ Camera Stream Input ]
          │
          ▼
[ YOLOv8 Object Detection ] ──(Filters Humans / Targeted Animals)
          │
          ▼
[ Geometric Geofencing ] ──(Checks 4-Point Polygon Bounding Box Coordinates)
          │
          ▼
[ Facial Verification Layer ] ──(HSV Color Histogram Chi-Square Match if Human)
          │
          ├──► [AUTHORIZED] ──► Box turns Blue, Alarms suppressed.
          │
          └──► [UNAUTHORIZED] ─► Spawns Background Worker Thread
                                        │
                                        ▼
                       [ Asynchronous 5-Shot Burst + Email Relay ]
🛠️ Core Functional Components
1. Dynamic Geofencing Matrix
How it works: Users visually map a customized 4-point polygon region of interest (ROI) directly onto the live feed.

The Math: The system samples specific anatomical anchors of a detected entity (feet, torso, head) and runs an OpenCV pointPolygonTest. A threat signature is only validated if these points physically intersect the coordinates of the custom drawn fence.

Control: Pressing the r key live-flushes the coordinate array, allowing instant boundary recalibration without software restarts.

2. Deep Learning Target Isolation (YOLOv8 Nano)
How it works: The system feeds the raw frame matrix into an optimized YOLOv8 model running locally on the CPU.

Target Filtering: To maximize processing efficiency and eliminate false alarm fatigue (like blowing leaves or shadows), the system explicitly filters the detection array to look only for Person (Class 0) or specific domestic/farm animal classes (Classes 15–19).

3. Native Color Histogram Facial Whitelisting
How it works: When a person trips the virtual perimeter, the system instantly crops their face using a Haar Cascade. It converts the cropped region to the HSV color space to minimize lighting interference and calculates a 2D Hue-Saturation color histogram signature.

The Whitelist: At startup, the system scans the local authorized_faces/ directory, builds signature templates for all approved personnel, and dynamically maps them to their filenames.

Mitigation: If the live face yields a correlation similarity score greater than 0.65 against a whitelisted template, the bounding box turns blue, the label prints AUTHORIZED: [NAME], and the alarm logic is safely suppressed.

4. Contactless Gesture Interruption (MediaPipe Hands)
How it works: If the alarm is triggered accidentally, operators can override it without touching a keyboard or control panel.

Mitigation: MediaPipe extracts 21 spatial landmarks from visible hands. If the system detects an "OK" sign gesture (👌)—calculated by checking if the distance between the thumb and index finger tips drops near zero while the remaining fingers remain extended—it instantly trips a threading.Event() signal.

Result: The active audio siren process is immediately killed, and the system enters a 15-second cyan-colored visual mute window before automatically re-arming itself.

5. Multi-Threaded Forensic Notification Burst
How it works: If a target breaches the perimeter and fails the facial verification check, the system immediately offloads the threat response to an isolated background thread worker.

No Video Lag: By running this asynchronously, the main camera loop continues to process video at full frame rate without freezing.

The Output: The background worker appends the event to a local security_logs.csv ledger, sounds a local siren.wav file, and captures a sequential 5-shot flutter burst spaced exactly 0.45 seconds apart straight from the camera hardware. It packages all 5 images into a secure MIME email packet via a TLS gateway and transmits it directly to your inbox before cleaning the temporary files off your disk.

📊 System State UI Cheat Sheet
During your live presentation, guide the evaluators' eyes by noting the system's dynamic coloring:

🟡 Yellow Boundary: System is armed, stable, and actively monitoring.

🔵 Blue Bounding Box: A human stepped inside, but the color histogram whitelisted them as an authorized user. Safe state.

🔴 Red Shaded Overlay: An unauthorized intrusion is occurring! The background worker thread is actively capturing frames and dispatching the email packet.

🟢 Cyan Boundary: The gesture override switch was triggered; the system displays a live visual countdown until it re-arms.
