from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import cv2
import pickle
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
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

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")  # IMPORTANT

# =========================
# SIMPLE FEATURE EXTRACTION
# =========================
def extract_features(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (80, 80))
    return resized.flatten()

# =========================
# EMAIL FUNCTION
# =========================
def send_email_alert(image_path):
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not ADMIN_EMAIL:
        print("❌ Missing email credentials")
        return

    msg = MIMEMultipart()
    msg["Subject"] = "🚨 Intruder Alert"
    msg["From"] = EMAIL_SENDER
    msg["To"] = ADMIN_EMAIL

    body = MIMEText("Intruder detected in AI Security System.")
    msg.attach(body)

    # attach image
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
    except Exception as e:
        print("Attachment error:", e)
        return

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, ADMIN_EMAIL, msg.as_string())
        server.quit()
        print("✅ Email sent")
    except Exception as e:
        print("❌ Email error:", e)

# =========================
# REGISTER
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
        return {"message": "Invalid image"}

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

    return {"message": f"{name} registered successfully"}

# =========================
# RECOGNIZE
# =========================
@app.post("/recognize/")
async def recognize(file: UploadFile = File(...)):

    global last_email_time

    if not os.path.exists(DB_FILE):
        return {"faces": ["No database"]}

    with open(DB_FILE, "rb") as f:
        db = pickle.load(f)

    img = await file.read()
    nparr = np.frombuffer(img, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        return {"faces": ["Invalid image"]}

    features = extract_features(image)

    def similarity(a, b):
        return np.linalg.norm(a - b)

    best_match = "Unknown"
    best_score = float("inf")

    # =========================
    # MATCHING LOGIC (FIXED)
    # =========================
    for person in db:
        score = similarity(features, person["features"])
        if score < best_score:
            best_score = score
            best_match = person["name"]

    # =========================
    # THRESHOLD (FIXED STABILITY)
    # =========================
    THRESHOLD = 6500  # improved stability

    if best_score > THRESHOLD:
        best_match = "Unknown"

        # save intruder image
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = os.path.join(INTRUDER_DIR, f"intruder_{ts}.jpg")
        cv2.imwrite(path, image)

        print("🚨 Intruder detected")

        # =========================
        # EMAIL (COOLDOWN)
        # =========================
        import time
        current_time = time.time()

        if current_time - last_email_time > EMAIL_COOLDOWN:
            send_email_alert(path)
            last_email_time = current_time

    elif best_score == float("inf"):
        best_match = "No face detected"

    return {"faces": [best_match]}