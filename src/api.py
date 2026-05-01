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
from deepface import DeepFace
from typing import List, Dict
import hashlib
import tempfile

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
THRESHOLD = 0.6  # For face matching (lower = stricter)

def extract_face_embedding(image):
    """Extract face embedding using DeepFace"""
    try:
        # Save image temporarily
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
            cv2.imwrite(tmp_file.name, image)
            tmp_path = tmp_file.name
        
        # Extract face embedding
        embedding = DeepFace.represent(
            img_path=tmp_path,
            model_name='Facenet',  # Good balance of accuracy and speed
            enforce_detection=True,
            detector_backend='opencv'
        )
        
        # Clean up
        os.unlink(tmp_path)
        
        if embedding and len(embedding) > 0:
            return np.array(embedding[0]['embedding']), True
        return None, False
    except Exception as e:
        print(f"Face extraction error: {e}")
        return None, False

def detect_faces(image):
    """Detect faces using OpenCV cascade"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    return faces

def send_email_alert(receiver_email: str, image_path: str):
    """Send email alert with intruder image"""
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    
    if not sender or not password:
        print("❌ Email credentials missing")
        return False
    
    msg = MIMEMultipart()
    msg["Subject"] = f"🚨 Intruder Alert - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    msg["From"] = sender
    msg["To"] = receiver_email
    
    body = f"""
    🚨 ALERT: Intruder Detected!
    
    Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    
    An unknown person has been detected by your AI Security System.
    Please check the attached image immediately.
    
    System: AI Security System v2.0
    """
    msg.attach(MIMEText(body, "plain"))
    
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
        
        # Validate email format
        import re
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return {"status": "error", "message": "Invalid email format"}
        
        # Read and decode image
        img_bytes = await file.read()
        nparr = np.frombuffer(img_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            return {"status": "error", "message": "Invalid image"}
        
        # Check if face is present
        faces = detect_faces(image)
        if len(faces) == 0:
            return {"status": "error", "message": "No face detected in image. Please upload a clear face photo."}
        
        # Extract face embedding
        face_embedding, success = extract_face_embedding(image)
        
        if not success or face_embedding is None:
            return {"status": "error", "message": "Could not extract face features. Please try another image."}
        
        # Load existing database
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "rb") as f:
                db = pickle.load(f)
        else:
            db = []
        
        # Check for duplicate name
        for person in db:
            if person["name"].lower() == name.lower():
                return {"status": "error", "message": f"User '{name}' already exists"}
        
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
            "message": f"✅ {name} registered successfully!",
            "total_users": len(db)
        }
    
    except Exception as e:
        print(f"Registration error: {e}")
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
        
        if len(db) == 0:
            return {"status": "no_db", "faces": [], "message": "Database is empty"}
        
        # Read image
        img_bytes = await file.read()
        nparr = np.frombuffer(img_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            return {"status": "error", "message": "Invalid image", "faces": []}
        
        # Detect faces
        faces = detect_faces(image)
        
        if len(faces) == 0:
            return {"status": "no_face", "faces": [], "message": "No face detected"}
        
        # Extract face embedding
        face_embedding, success = extract_face_embedding(image)
        
        if not success or face_embedding is None:
            return {"status": "error", "message": "Could not extract face features", "faces": []}
        
        # Match against database
        best_match = "Unknown"
        best_distance = float("inf")
        best_confidence = 0
        
        for person in db:
            # Calculate Euclidean distance
            distance = np.linalg.norm(face_embedding - person["features"])
            confidence = max(0, 1 - (distance / 1.5))  # Convert to confidence score
            
            if distance < best_distance:
                best_distance = distance
                best_match = person["name"]
                best_confidence = confidence
        
        # Apply threshold
        if best_confidence < THRESHOLD:
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
                "faces": ["Unknown"],
                "confidence": float(best_confidence),
                "num_faces_detected": len(faces),
                "message": "🚨 Intruder detected!"
            }
        else:
            return {
                "status": "ok",
                "faces": [best_match],
                "confidence": float(best_confidence),
                "num_faces_detected": len(faces),
                "message": f"✅ Welcome {best_match}!"
            }
    
    except Exception as e:
        print(f"Recognition error: {e}")
        return {"status": "error", "message": str(e), "faces": []}

@app.get("/stats/")
async def get_stats():
    """Get database statistics"""
    try:
        intruder_count = len([f for f in os.listdir(INTRUDER_DIR) if f.endswith('.jpg')]) if os.path.exists(INTRUDER_DIR) else 0
        
        if not os.path.exists(DB_FILE):
            return {
                "total_registered": 0, 
                "intruders": intruder_count,
                "registered_users": []
            }
        
        with open(DB_FILE, "rb") as f:
            db = pickle.load(f)
        
        return {
            "total_registered": len(db),
            "intruders": intruder_count,
            "registered_users": [{"name": p["name"], "email": p["email"]} for p in db]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database_exists": os.path.exists(DB_FILE)
    }