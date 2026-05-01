from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import cv2
import pickle
import os
import smtplib
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv
import face_recognition
from typing import List, Dict
import hashlib

load_dotenv()

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(BASE_DIR, "face_db.pkl")
INTRUDER_DIR = os.path.join(BASE_DIR, "output", "intruders")
os.makedirs(INTRUDER_DIR, exist_ok=True)

# Settings
last_email_time = 0
EMAIL_COOLDOWN = 30
THRESHOLD = 0.6  # For face_recognition distance (lower = stricter)

# Load face cascade for detection
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def extract_face_embedding(image):
    """Extract face embedding using face_recognition library"""
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb)
    
    if not face_locations:
        return None, None
    
    face_encodings = face_recognition.face_encodings(rgb, face_locations)
    return face_encodings[0] if face_encodings else None, face_locations[0]

def send_email_alert(receiver_email: str, image_path: str):
    """Send email alert with intruder image"""
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    
    if not sender or not password:
        print("❌ Email credentials missing")
        return
    
    msg = MIMEMultipart()
    msg["Subject"] = f"🚨 Intruder Alert - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    msg["From"] = sender
    msg["To"] = receiver_email
    
    body = f"""
    Intruder detected in your AI security system.
    Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    
    Please check the attached image.
    """
    msg.attach(MIMEText(body))
    
    try:
        with open(image_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename={os.path.basename(image_path)}"
        )
        msg.attach(part)
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver_email, msg.as_string())
        
        print("✅ Email sent successfully")
        return True
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False

@app.post("/register/")
async def register(
    name: str = Form(...),
    email: str = Form(...),
    file: UploadFile = File(...)
):
    """Register a new face in the database"""
    try:
        # Validate inputs
        if not name or not email:
            return {"status": "error", "message": "Name and email required"}
        
        # Read and decode image
        img_bytes = await file.read()
        nparr = np.frombuffer(img_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            return {"status": "error", "message": "Invalid image"}
        
        # Extract face embedding
        face_embedding, face_location = extract_face_embedding(image)
        
        if face_embedding is None:
            return {"status": "error", "message": "No face detected in image"}
        
        # Check if face already exists (optional)
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "rb") as f:
                db = pickle.load(f)
        else:
            db = []
        
        # Save to database
        db.append({
            "name": name,
            "email": email,
            "features": face_embedding,
            "registered_at": datetime.now().isoformat()
        })
        
        with open(DB_FILE, "wb") as f:
            pickle.dump(db, f)
        
        return {
            "status": "success",
            "message": f"{name} registered successfully",
            "face_location": face_location.tolist()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/recognize/")
async def recognize(file: UploadFile = File(...)):
    """Recognize a face from uploaded image"""
    global last_email_time
    
    try:
        # Load database
        if not os.path.exists(DB_FILE):
            return {"status": "no_db", "faces": [], "message": "No registered faces"}
        
        with open(DB_FILE, "rb") as f:
            db = pickle.load(f)
        
        # Read image
        img_bytes = await file.read()
        nparr = np.frombuffer(img_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            return {"status": "error", "message": "Invalid image", "faces": []}
        
        # Detect faces
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        
        if len(faces) == 0:
            return {"status": "no_face", "faces": [], "message": "No face detected"}
        
        # Extract face embedding
        face_embedding, face_location = extract_face_embedding(image)
        
        if face_embedding is None:
            return {"status": "error", "message": "Could not extract face features", "faces": []}
        
        # Match against database
        best_match = "Unknown"
        best_distance = float("inf")
        best_email = None
        
        for person in db:
            distance = np.linalg.norm(face_embedding - person["features"])
            if distance < best_distance:
                best_distance = distance
                best_match = person["name"]
                best_email = person.get("email")
        
        # Apply threshold
        if best_distance > THRESHOLD:
            best_match = "Unknown"
            
            # Save intruder image
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            intruder_path = os.path.join(INTRUDER_DIR, f"intruder_{timestamp}.jpg")
            cv2.imwrite(intruder_path, image)
            
            # Send email alert (with cooldown)
            current_time = time.time()
            if current_time - last_email_time > EMAIL_COOLDOWN:
                admin_email = os.getenv("ADMIN_EMAIL")
                if admin_email:
                    send_email_alert(admin_email, intruder_path)
                last_email_time = current_time
        
        return {
            "status": "ok",
            "faces": [best_match],
            "confidence": float(1 - best_distance) if best_match != "Unknown" else 0,
            "num_faces_detected": len(faces)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats/")
async def get_stats():
    """Get database statistics"""
    if not os.path.exists(DB_FILE):
        return {"total_registered": 0, "intruders": len(os.listdir(INTRUDER_DIR))}
    
    with open(DB_FILE, "rb") as f:
        db = pickle.load(f)
    
    return {
        "total_registered": len(db),
        "intruders": len(os.listdir(INTRUDER_DIR)),
        "registered_users": [{"name": p["name"], "email": p["email"]} for p in db]
    }