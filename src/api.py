from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import os
import cv2
import time
import pickle
from datetime import datetime
from deepface import DeepFace

from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# =========================
# INIT
# =========================
load_dotenv()
app = FastAPI()

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
DB_FILE = os.path.join(BASE_DIR, "face_db.pkl")
LOG_FILE = os.path.join(BASE_DIR, "logs", "security_log.txt")
INTRUDER_DIR = os.path.join(BASE_DIR, "output", "intruders")

os.makedirs(INTRUDER_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# =========================
# EMAIL
# =========================
last_email_time = 0
EMAIL_COOLDOWN = 30


def send_email(receiver, image_path):
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")

    msg = MIMEMultipart()
    msg["Subject"] = "🚨 Intruder Alert"
    msg["From"] = sender
    msg["To"] = receiver

    msg.attach(MIMEText("Intruder detected! See attached image."))

    try:
        with open(image_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())

        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(image_path)}")
        msg.attach(part)

        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())
        server.quit()

        print("Email sent")

    except Exception as e:
        print("Email error:", e)


# =========================
# REGISTER FACE
# =========================
@app.post("/register/")
async def register(name: str = Form(...), email: str = Form(...), file: UploadFile = File(...)):

    img_bytes = await file.read()
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return {"status": "error", "message": "Invalid image"}

    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    try:
        embedding = DeepFace.represent(rgb, model_name="VGG-Face")[0]["embedding"]
    except:
        return {"status": "error", "message": "No face detected"}

    if os.path.exists(DB_FILE):
        with open(DB_FILE, "rb") as f:
            db = pickle.load(f)
    else:
        db = []

    db.append({
        "name": name,
        "email": email,
        "embedding": embedding
    })

    with open(DB_FILE, "wb") as f:
        pickle.dump(db, f)

    return {"status": "success", "message": f"{name} registered"}


# =========================
# RECOGNIZE FACE
# =========================
@app.post("/recognize/")
async def recognize(file: UploadFile = File(...)):

    global last_email_time

    if not os.path.exists(DB_FILE):
        return {"status": "error", "name": "No database"}

    with open(DB_FILE, "rb") as f:
        db = pickle.load(f)

    img_bytes = await file.read()
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    try:
        result = DeepFace.represent(rgb, model_name="VGG-Face")[0]["embedding"]
    except:
        return {"status": "no_face", "name": "No face detected"}

    def cosine(a, b):
        a = np.array(a)
        b = np.array(b)
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    best_match = "Unknown"
    best_score = -1
    email = None

    for person in db:
        score = cosine(result, person["embedding"])

        if score > best_score:
            best_score = score
            best_match = person["name"]
            email = person["email"]

    unknown = best_score < 0.6

    if unknown:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = os.path.join(INTRUDER_DIR, f"intruder_{ts}.jpg")
        cv2.imwrite(path, img)

        if time.time() - last_email_time > EMAIL_COOLDOWN:
            send_email(email if email else "", path)
            last_email_time = time.time()

        return {"status": "unknown", "name": "Unknown"}

    return {"status": "success", "name": best_match}