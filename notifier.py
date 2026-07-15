import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

# ==========================================
# GMAIL SMTP SETUP CONFIGURATION
# ==========================================
SENDER_EMAIL = "cvproject1430@gmail.com"          
SENDER_APP_PASSWORD = "wuae lqxt grlm cknd"   
RECEIVER_EMAIL = "dineshbhayal1510@gmail.com"      

def send_burst_email_alert(target_label, timestamp_str, image_paths):
    """
    Connects to Google SMTP Gateway and sends a structured alert email
    containing a burst sequence of evidence photos attached together.
    """
    if SENDER_EMAIL == "your_email@gmail.com":
        print("⚠️ [NOTIFIER] Email skipped: SENDER_EMAIL not configured.")
        return False

    try:
        subject = f"🚨 UNKNOWN INTRUSION: 5-Shot Burst Alert ({target_label.upper()})"
        body = (
            f"Caution!\n\n"
            f"An UNAUTHORIZED perimeter breach was detected by the smart security system.\n"
            f"Details:\n"
            f" - Target Profile: {target_label}\n"
            f" - Breach Time: {timestamp_str}\n"
            f" - Action: Captured 5 sequential flutter shots spaced 0.45s apart.\n\n"
            f"Please review all 5 attached sequential evidence frames of the unknown subject below."
        )
        
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        # --- ATTACH ALL CAPTURED IMAGES IN A SINGLE MAIL ---
        for img_path in image_paths:
            if os.path.exists(img_path):
                with open(img_path, 'rb') as f:
                    img_data = f.read()
                image_attachment = MIMEImage(img_data, name=os.path.basename(img_path))
                msg.attach(image_attachment)
        
        # Establish secure connection to Google's TLS mail gateway
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()  
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
            
        print(f"📧 [EMAIL SENT] Burst intrusion sequence successfully dispatched to {RECEIVER_EMAIL}")
        return True
        
    except Exception as e:
        print(f"❌ [EMAIL ERROR] Failed to dispatch email burst alert: {e}")
        return False
        
    finally:
        # Cleanup all temporary image files from the disk
        for img_path in image_paths:
            if os.path.exists(img_path):
                
                os.remove(img_path)