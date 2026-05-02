from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import face_recognition
import pickle
import numpy as np
import os
import cv2
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import time
from dotenv import load_dotenv
from datetime import datetime
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent
ENCODINGS_FILE = BASE_DIR / "encodings.pkl"
FRONTEND_DIR = BASE_DIR / "frontend"
LOG_FILE = BASE_DIR / "logs" / "security_log.txt"
INTRUDER_DIR = BASE_DIR / "output" / "intruders"

# Create directories
INTRUDER_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Get admin email from .env (only this email receives alerts)
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
if not ADMIN_EMAIL:
    logger.warning("⚠️ ADMIN_EMAIL not set in .env file! Alerts will not be sent.")

# Serve static files
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    
    @app.get("/")
    async def root():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
    
    @app.get("/style.css")
    async def serve_css():
        return FileResponse(str(FRONTEND_DIR / "style.css"))
    
    @app.get("/script.js")
    async def serve_js():
        return FileResponse(str(FRONTEND_DIR / "script.js"))
    
    @app.get("/alarm.mp3")
    async def serve_alarm():
        return FileResponse(str(FRONTEND_DIR / "alarm.mp3"))

last_email_time = 0
EMAIL_COOLDOWN = 30

def send_intruder_alert(image_path, face_names):
    """Send email alert to admin for intruder only"""
    global last_email_time
    
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    
    if not sender or not password:
        logger.error("Missing email credentials in .env file")
        return False
    
    if not ADMIN_EMAIL:
        logger.error("ADMIN_EMAIL not configured in .env file")
        return False
    
    # Check cooldown to prevent spam
    current_time = time.time()
    if current_time - last_email_time < EMAIL_COOLDOWN:
        logger.info(f"Email cooldown active. Last email sent {current_time - last_email_time:.1f}s ago")
        return False
    
    # Clean password (remove spaces if any)
    password = password.replace(" ", "")
    
    try:
        msg = MIMEMultipart()
        msg["Subject"] = f"🚨 INTRUDER ALERT! - Unknown Person Detected"
        msg["From"] = sender
        msg["To"] = ADMIN_EMAIL
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        body = f"""
╔══════════════════════════════════════════════════════════╗
║              🚨 INTRUDER ALERT! 🚨                       ║
╚══════════════════════════════════════════════════════════╝

Time: {timestamp}
Location: AI Security System

⚠️ An UNKNOWN person has been detected!

Detected Faces: {', '.join(face_names)}

Action Required: Please check the attached image immediately.

--
AI Security System - Automatic Alert
        """
        
        msg.attach(MIMEText(body, "plain"))
        
        # Attach the intruder image
        if os.path.exists(image_path):
            with open(image_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(image_path)}")
                msg.attach(part)
                logger.info(f"📎 Image attached: {os.path.basename(image_path)}")
        
        # Send email using Gmail SMTP
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, ADMIN_EMAIL, msg.as_string())
            last_email_time = current_time
            logger.info(f"✅ Intruder alert sent to admin: {ADMIN_EMAIL}")
            return True
            
    except Exception as e:
        logger.error(f"Email error: {str(e)}")
        return False

@app.post("/register/")
async def register_face(
    name: str = Form(...), 
    email: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        logger.info(f"Registering user: {name}")
        
        # Read image
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            return JSONResponse(status_code=400, content={"message": "Invalid image file"})
        
        # Convert to RGB for face_recognition
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Get face encodings
        face_locations = face_recognition.face_locations(rgb_image)
        face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
        
        if not face_encodings:
            return JSONResponse(status_code=400, content={"message": "No face detected in the image! Please upload a clear face photo."})
        
        # Convert numpy array to list for storage
        new_encoding = face_encodings[0].tolist()
        
        # Load existing data
        known_encodings = []
        known_names = []
        known_emails = []
        
        if ENCODINGS_FILE.exists():
            try:
                with open(ENCODINGS_FILE, "rb") as f:
                    data = pickle.load(f)
                    if isinstance(data, dict):
                        known_encodings = data.get("encodings", [])
                        known_names = data.get("names", [])
                        known_emails = data.get("emails", [])
                    else:
                        known_encodings, known_names, known_emails = data
            except Exception as e:
                logger.error(f"Error loading: {e}")
        
        # Check if name exists
        if name in known_names:
            idx = known_names.index(name)
            known_encodings[idx] = new_encoding
            known_emails[idx] = email
            logger.info(f"Updated existing user: {name}")
            message = f"✅ {name}'s face updated successfully!"
        else:
            known_encodings.append(new_encoding)
            known_names.append(name)
            known_emails.append(email)
            logger.info(f"Added new user: {name}")
            message = f"✅ {name} registered successfully!"
        
        # Save data
        data = {
            "encodings": known_encodings,
            "names": known_names,
            "emails": known_emails
        }
        with open(ENCODINGS_FILE, "wb") as f:
            pickle.dump(data, f)
        
        return {"message": message}
        
    except Exception as e:
        logger.error(f"Register error: {str(e)}")
        return JSONResponse(status_code=500, content={"message": f"Error: {str(e)}"})

@app.post("/recognize/")
async def recognize_face(file: UploadFile = File(...)):
    try:
        # Read image
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            return {"faces": [], "message": "Invalid image"}
        
        # Convert to RGB
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Load known faces
        known_encodings = []
        known_names = []
        known_emails = []
        
        if ENCODINGS_FILE.exists():
            with open(ENCODINGS_FILE, "rb") as f:
                data = pickle.load(f)
                if isinstance(data, dict):
                    known_encodings = data.get("encodings", [])
                    known_names = data.get("names", [])
                    known_emails = data.get("emails", [])
                else:
                    known_encodings, known_names, known_emails = data
        
        # Convert stored lists back to numpy arrays
        known_encodings_np = []
        for enc in known_encodings:
            if isinstance(enc, list):
                known_encodings_np.append(np.array(enc))
            else:
                known_encodings_np.append(enc)
        
        # Detect faces
        face_locations = face_recognition.face_locations(rgb_image)
        face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
        
        # Case 1: No face detected
        if not face_encodings:
            logger.info("📭 No face detected in frame")
            return {"faces": [], "message": "No face detected", "unknown": False}
        
        face_names = []
        unknown_detected = False
        
        # Match each detected face
        for face_encoding in face_encodings:
            if len(known_encodings_np) == 0:
                # No registered users at all
                name = "Unknown"
                unknown_detected = True
            else:
                # Calculate distances to all known faces
                distances = face_recognition.face_distance(known_encodings_np, face_encoding)
                best_index = np.argmin(distances)
                best_distance = float(distances[best_index])
                
                # Threshold for matching (0.5 is good balance)
                if best_distance < 0.5:
                    name = known_names[best_index]
                    logger.info(f"✅ Recognized: {name} (confidence: {1-best_distance:.1%})")
                else:
                    name = "Unknown"
                    unknown_detected = True
                    logger.info(f"❌ Unknown face detected (best match: {best_distance:.3f})")
            
            face_names.append(name)
        
        # Case 2: Unknown/Intruder detected - Save image and send email
        if unknown_detected:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"intruder_{timestamp}.jpg"
            filepath = INTRUDER_DIR / filename
            
            # Save the intruder image
            cv2.imwrite(str(filepath), image)
            logger.info(f"📸 Intruder image saved: {filename}")
            
            # Log to security log
            try:
                with open(LOG_FILE, "a") as f:
                    f.write(f"[{timestamp}] 🚨 INTRUDER DETECTED - Faces: {', '.join(face_names)} - Image: {filename}\n")
                logger.info(f"📝 Security log updated")
            except Exception as e:
                logger.error(f"Log error: {e}")
            
            # Send email alert to admin
            logger.info(f"📧 Sending intruder alert to admin: {ADMIN_EMAIL}")
            send_intruder_alert(str(filepath), face_names)
            
            return {
                "faces": face_names,
                "count": len(face_names),
                "unknown": True,
                "message": "🚨 INTRUDER ALERT! Unknown person detected."
            }
        
        # Case 3: Registered person detected - NO image saved, NO email
        else:
            logger.info(f"✅ Registered person(s) detected: {', '.join(face_names)} - No action taken")
            return {
                "faces": face_names,
                "count": len(face_names),
                "unknown": False,
                "message": f"✅ Welcome {', '.join(face_names)}!"
            }
        
    except Exception as e:
        logger.error(f"Recognize error: {str(e)}")
        return {"faces": [], "error": str(e), "unknown": False}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "encodings_exists": ENCODINGS_FILE.exists(),
        "frontend_exists": FRONTEND_DIR.exists(),
        "admin_email_configured": bool(ADMIN_EMAIL),
        "admin_email": ADMIN_EMAIL if ADMIN_EMAIL else "Not configured",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/admin-status")
async def admin_status():
    """Check if admin email is configured"""
    if ADMIN_EMAIL:
        return {"configured": True, "email": ADMIN_EMAIL}
    else:
        return {"configured": False, "message": "Admin email not configured in .env file"}

@app.get("/users")
async def get_users():
    """Get list of all registered users"""
    if not ENCODINGS_FILE.exists():
        return {"users": [], "count": 0}
    try:
        with open(ENCODINGS_FILE, "rb") as f:
            data = pickle.load(f)
        
        if isinstance(data, dict):
            users = [{"name": name, "email": email} for name, email in zip(data.get("names", []), data.get("emails", []))]
        else:
            users = [{"name": name, "email": email} for name, email in zip(data[0], data[1])]
        
        return {"users": users, "count": len(users)}
    except Exception as e:
        return {"users": [], "error": str(e), "count": 0}

@app.delete("/clear-intruders")
async def clear_intruders(secret_key: str):
    """Clear all intruder images (admin only)"""
    SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "admin123")
    
    if secret_key != SECRET_KEY:
        return JSONResponse(status_code=403, content={"message": "Unauthorized"})
    
    try:
        # Delete all files in intruder directory
        for file in INTRUDER_DIR.glob("*.jpg"):
            file.unlink()
        return {"message": f"Cleared {len(list(INTRUDER_DIR.glob('*.jpg')))} intruder images"}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)