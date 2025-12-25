import os
import sys
import cv2
import pickle
import face_recognition

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils import draw_face_box

# Automatically find the base folder of the project
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Define absolute paths for important folders and files
UNKNOWN_FACES_DIR = os.path.join(BASE_DIR, "data", "unknown_faces")   # Folder that contains unknown face images
ENCODINGS_FILE = os.path.join(BASE_DIR, "encodings.pk1")              # File that stores known face encodings
OUTPUT_DIR = os.path.join(BASE_DIR, "output", "results")              # Folder to save recognized face images


def recognize_faces():
    print("Loading known face encodings...")

    if not os.path.exists(ENCODINGS_FILE):
        print(f"Encodings file not found: {ENCODINGS_FILE}")
        return

    with open(ENCODINGS_FILE, "rb") as f:
        known_encodings, known_names = pickle.load(f)

    print("Encodings loaded successfully!\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.exists(UNKNOWN_FACES_DIR):
        print(f"Unknown faces folder not found: {UNKNOWN_FACES_DIR}")
        return

    for filename in os.listdir(UNKNOWN_FACES_DIR):
        # Only process image files with .jpg extension
        if not filename.lower().endswith(".jpg"):
            continue

        print(f"Analyzing {filename}...")

        image_path = os.path.join(UNKNOWN_FACES_DIR, filename)
        image = face_recognition.load_image_file(image_path)

        # Detect all face locations in the image
        face_locations = face_recognition.face_locations(image)

        # Get encodings for each detected face
        face_encodings = face_recognition.face_encodings(image, face_locations)

        # Convert image color format from RGB (used by face_recognition)
        # to BGR (used by OpenCV)
        image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        # Compare each detected face with known faces
        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            # Compare current face with all known encodings
            matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=0.5)
            name = "Unknown" 

            # If a match is found, use the name of the first matching face
            if True in matches:
                first_match_index = matches.index(True)
                name = known_names[first_match_index]

            # Draw a box and label on the image
            draw_face_box(image_bgr, (top, right, bottom, left), name)

        # Save the processed image with boxes and names into the "results" folder
        output_path = os.path.join(OUTPUT_DIR, filename)
        cv2.imwrite(output_path, image_bgr)
        print(f"Result saved: {output_path}\n")

    print("Recognition complete! All results saved in:", OUTPUT_DIR)


# This ensures that the code runs only if this file is executed directly
if __name__ == "__main__":
    recognize_faces()
