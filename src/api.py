from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import face_recognition
import pickle
import numpy as np
import os
import cv2
import smtplib
from email.mime.text import MIMEText
import time
from dotenv import load_dotenv

# =========================
# LOAD ENV VARIABLES
# =========================
load_dotenv()

app = FastAPI()

# =========================
# CORS (Frontend Support)
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

# =========================
# EMAIL COOLDOWN
# =========================
last_email_time = 0
EMAIL_COOLDOWN = 30  # seconds

# =========================
# EMAIL FUNCTION
# =========================
def send_email_alert(receiver_email):
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")

    if not sender or not password:
        print("Email credentials missing in .env")
        return

    msg = MIMEText("🚨 Intruder detected!")
    msg["Subject"] = "Security Alert"
    msg["From"] = sender
    msg["To"] = receiver_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver_email, msg.as_string())
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

    nparr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        return {"message": "Invalid image"}

    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    encodings = face_recognition.face_encodings(image)

    if len(encodings) == 0:
        return {"message": "No face detected"}

    new_encoding = encodings[0]

    # Load existing data safely
    if os.path.exists(ENCODINGS_FILE):
        with open(ENCODINGS_FILE, "rb") as f:
            known_encodings, known_names, known_emails = pickle.load(f)
    else:
        known_encodings, known_names, known_emails = [], [], []

    # Save new user
    known_encodings.append(new_encoding)
    known_names.append(name)
    known_emails.append(email)

    with open(ENCODINGS_FILE, "wb") as f:
        pickle.dump((known_encodings, known_names, known_emails), f)

    return {"message": f"{name} registered successfully"}

# =========================
# RECOGNIZE FACE
# =========================
@app.post("/recognize/")
async def recognize_face(file: UploadFile = File(...)):
    global last_email_time

    if not os.path.exists(ENCODINGS_FILE):
        return {"faces": []}

    with open(ENCODINGS_FILE, "rb") as f:
        known_encodings, known_names, known_emails = pickle.load(f)

    contents = await file.read()

    nparr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        return {"faces": ["Invalid image"]}

    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    face_locations = face_recognition.face_locations(image)
    face_encodings = face_recognition.face_encodings(image, face_locations)

    if len(face_encodings) == 0:
        return {"faces": ["No face detected"]}

    face_names = []
    unknown_detected = False

    for face_encoding in face_encodings:

        # No registered faces
        if len(known_encodings) == 0:
            face_names.append("Unknown")
            unknown_detected = True
            continue

        distances = face_recognition.face_distance(known_encodings, face_encoding)

        best_index = np.argmin(distances)
        best_distance = distances[best_index]

        THRESHOLD = 0.45

        if best_distance < THRESHOLD:
            name = known_names[best_index]
        else:
            name = "Unknown"
            unknown_detected = True

        face_names.append(name)

    # =========================
    # EMAIL ALERT (SAFE + CONTROLLED)
    # =========================
    if unknown_detected:
        current_time = time.time()

        if current_time - last_email_time > EMAIL_COOLDOWN:
            if len(known_emails) > 0:
                send_email_alert(known_emails[0])

            last_email_time = current_time

    return {"faces": face_names}