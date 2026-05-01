from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
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

# =========================
# LOAD ENV
# =========================
load_dotenv()

app = FastAPI()

# =========================
# CORS
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# PATHS
# =========================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENCODINGS_FILE = os.path.join(BASE_DIR, "encodings.pkl")
LOG_FILE = os.path.join(BASE_DIR, "logs", "security_log.txt")
INTRUDER_DIR = os.path.join(BASE_DIR, "output", "intruders")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
os.makedirs(INTRUDER_DIR, exist_ok=True)

# =========================
# EMAIL CONTROL
# =========================
last_email_time = 0
EMAIL_COOLDOWN = 30

# =========================
# EMAIL FUNCTION
# =========================
def send_email_alert(receiver_email, image_path):
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")

    if not sender or not password:
        print("Missing email credentials")
        return

    msg = MIMEMultipart()
    msg["Subject"] = "🚨 Intruder Alert!"
    msg["From"] = sender
    msg["To"] = receiver_email

    msg.attach(MIMEText("⚠️ Intruder detected! See attached image."))

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

        print("✅ Email sent!")

    except Exception as e:
        print("Email Error:", e)

# =========================
# REGISTER FACE
# =========================
@app.post("/register/")
async def register_face(
    name: str = Form(...),
    email: str = Form(...),
    file: UploadFile = File(...)
):
    contents = await file.read()

    image = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)

    if image is None:
        return {"status": "error", "message": "Invalid image"}

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    encodings = face_recognition.face_encodings(rgb)

    if not encodings:
        return {"status": "error", "message": "No face detected"}

    encoding = encodings[0]

    if os.path.exists(ENCODINGS_FILE):
        try:
            with open(ENCODINGS_FILE, "rb") as f:
                known_encodings, known_names, known_emails = pickle.load(f)
        except:
            known_encodings, known_names, known_emails = [], [], []
    else:
        known_encodings, known_names, known_emails = [], [], []

    known_encodings.append(encoding)
    known_names.append(name)
    known_emails.append(email)

    with open(ENCODINGS_FILE, "wb") as f:
        pickle.dump((known_encodings, known_names, known_emails), f)

    return {
        "status": "success",
        "message": f"{name} registered successfully"
    }

# =========================
# RECOGNIZE FACE
# =========================
@app.post("/recognize/")
async def recognize_face(file: UploadFile = File(...)):
    global last_email_time

    if not os.path.exists(ENCODINGS_FILE):
        return {"status": "error", "name": "No database"}

    with open(ENCODINGS_FILE, "rb") as f:
        known_encodings, known_names, known_emails = pickle.load(f)

    image = cv2.imdecode(np.frombuffer(await file.read(), np.uint8), cv2.IMREAD_COLOR)

    if image is None:
        return {"status": "error", "name": "Invalid image"}

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    locations = face_recognition.face_locations(rgb)
    encodings = face_recognition.face_encodings(rgb, locations)

    if not encodings:
        return {"status": "no_face", "name": "No face detected"}

    results = []
    unknown_detected = False

    for face_encoding in encodings:

        if len(known_encodings) == 0:
            results.append("Unknown")
            unknown_detected = True
            continue

        distances = face_recognition.face_distance(known_encodings, face_encoding)

        if len(distances) == 0:
            results.append("Unknown")
            unknown_detected = True
            continue

        idx = np.argmin(distances)

        if distances[idx] < 0.45:
            results.append(known_names[idx])
        else:
            results.append("Unknown")
            unknown_detected = True

    # =========================
    # INTRUDER HANDLING
    # =========================
    if unknown_detected:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = os.path.join(INTRUDER_DIR, f"intruder_{timestamp}.jpg")

        cv2.imwrite(path, image)

        try:
            with open(LOG_FILE, "a") as f:
                f.write(f"[{timestamp}] Intruder detected\n")
        except:
            pass

        current_time = time.time()

        if current_time - last_email_time > EMAIL_COOLDOWN:
            if known_emails:
                send_email_alert(known_emails[0], path)
            last_email_time = current_time

    return {
        "status": "success",
        "name": results
    }