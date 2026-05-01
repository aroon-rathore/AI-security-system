from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import cv2
import pickle
import os
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# STORAGE
# -------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(BASE_DIR, "face_db.pkl")
INTRUDER_DIR = os.path.join(BASE_DIR, "output", "intruders")

os.makedirs(INTRUDER_DIR, exist_ok=True)

# -------------------------
# SIMPLE FACE FEATURE (NO AI LIBRARIES)
# -------------------------
def extract_features(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (100, 100))
    return resized.flatten()

# -------------------------
# REGISTER
# -------------------------
@app.post("/register/")
async def register(name: str = Form(...), email: str = Form(...), file: UploadFile = File(...)):

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

# -------------------------
# RECOGNIZE
# -------------------------
@app.post("/recognize/")
async def recognize(file: UploadFile = File(...)):

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
    best_score = 999

    for person in db:
        score = similarity(features, person["features"])
        if score < best_score:
            best_score = score
            best_match = person["name"]

    # threshold
    if best_score > 5000:
        best_match = "Unknown"

        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = os.path.join(INTRUDER_DIR, f"intruder_{ts}.jpg")
        cv2.imwrite(path, image)

    return {"faces": [best_match]}