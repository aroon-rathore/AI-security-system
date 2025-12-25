🧠 Face Recognition Project (Python + OpenCV + dlib)

This project detects and recognizes human faces in images using a pretrained deep learning model from face_recognition.
It identifies faces that are registered in the system and labels unknown ones accordingly.

📂 Project Structure
image_recognition/
│
├── data/
│   ├── known_faces/      # Folder of known persons (each person has a subfolder)
│   └── unknown_faces/    # Folder of test/group photos
│
├── output/
│   └── results/          # Recognized faces are saved here
│
├── src/
│   ├── register_faces.py # Register and encode known faces
│   ├── recognize_faces.py# Detect and recognize new faces
│   └── utils.py          # Helper for drawing rectangles
│
├── encodings.pkl         # Stores known face encodings
├── requirements.txt
└── README.md

⚙️ Setup Instructions

1️⃣ Create virtual environment

python -m venv venv
venv\Scripts\activate       # for Windows


2️⃣ Install dependencies

pip install -r requirements.txt


3️⃣ Register known faces
Put your known faces (e.g. arijit_singh/, salman_khan/) inside
data/known_faces/, then run:

python src/register_faces.py


4️⃣ Recognize new images
Place test images in data/unknown_faces/, then run:

python src/recognize_faces.py


5️⃣ Check results
Recognized images with boxes and labels will appear in:

output/results/

🎯 Features

Uses pretrained deep learning model for face recognition

Detects multiple faces in one photo

Labels known people (green box)

Labels unknown people (red box)

Automatically saves output images

🧠 How It Works (Concept)

Register known faces → Extract and store encodings

Recognize unknown images → Compare encodings

Draw boxes → Green for known(with name), Red for unknown