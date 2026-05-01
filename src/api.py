from fastapi import FastAPI, UploadFile, File, Form
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
DB_FILE = os.path.join(BASE_DIR, "face_db.pkl")
INTRUDER_DIR = os.path.join(BASE_DIR, "output", "intruders")

os.makedirs(INTRUDER_DIR, exist_ok=True)

# =========================
# EMAIL SETTINGS
# =========================
last_email_time = 0
EMAIL_COOLDOWN = 30


# =========================
# FEATURE EXTRACTION (SIMPLE AI)
# =========================
def extract_features(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (100, 100))
    return resized.flatten()


# =========================
# EMAIL FUNCTION
# =========================
def send_email_alert(receiver_email, image_path):

    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")

    if not sender or not password:
        print("❌ Email credentials missing")
        return

    msg = MIMEMultipart()
    msg["Subject"] = "🚨 Intruder Alert"
    msg["From"] = sender
    msg["To"] = receiver_email

    msg.attach(MIMEText("Intruder detected in your AI security system."))

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

    except Exception as e:
        print("❌ Email error:", e)


# =========================
# REGISTER FACE
# =========================
@app.post("/register/")
async def register(
    name: str = Form(...),
    email: str = Form(...),
    file: UploadFile = File(...)
):

    img = await file.read()
    nparr = np.frombuffer(img, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        return {"status": "error", "message": "Invalid image"}

    features = extract_features(image)

    if os.path.exists(DB_FILE):
        with open(DB_FILE, "rb") as f:
            db = pickle.load(f)
    else:
        db = []

    db.append({
        "name": name,
        "email": email,
        "features": features
    })

    with open(DB_FILE, "wb") as f:
        pickle.dump(db, f)

    return {
        "status": "success",
        "message": f"{name} registered successfully"
    }


# =========================
# RECOGNIZE FACE
# =========================
@app.post("/recognize/")
async def recognize(file: UploadFile = File(...)):

    global last_email_time

    # Load DB
    if not os.path.exists(DB_FILE):
        return {"status": "no_db", "faces": ["No database"]}

    with open(DB_FILE, "rb") as f:
        db = pickle.load(f)

    # Read image
    img = await file.read()
    nparr = np.frombuffer(img, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        return {"status": "error", "faces": ["Invalid image"]}

    features = extract_features(image)

    # =========================
    # MATCHING LOGIC
    # =========================
    def distance(a, b):
        return np.linalg.norm(a - b)

    best_name = "Unknown"
    best_score = float("inf")

    for person in db:
        score = distance(features, person["features"])
        if score < best_score:
            best_score = score
            best_name = person["name"]
            best_email = person["email"]

    # =========================
    # THRESHOLD CHECK
    # =========================
    THRESHOLD = 5000

    unknown_detected = False

    if best_score > THRESHOLD:
        best_name = "Unknown"
        unknown_detected = True

        # Save intruder image
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = os.path.join(INTRUDER_DIR, f"intruder_{ts}.jpg")
        cv2.imwrite(path, image)

        # EMAIL (COOLDOWN PROTECTED)
        current_time = time.time()

        if current_time - last_email_time > EMAIL_COOLDOWN:
            admin_email = os.getenv("ADMIN_EMAIL")

            if admin_email:
                send_email_alert(admin_email, path)

            last_email_time = current_time

    # =========================
    # NO FACE CHECK (BASIC)
    # =========================
    if len(features) == 0:
        return {
            "status": "no_face",
            "faces": []
        }

    # =========================
    # FINAL RESPONSE (IMPORTANT)
    # =========================
    return {
        "status": "ok",
        "faces": [best_name]
    }