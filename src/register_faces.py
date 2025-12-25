import os
import face_recognition
import pickle


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

KNOWN_FACES_DIR = os.path.join(BASE_DIR, "data", "known_faces")
ENCODINGS_FILE = os.path.join(BASE_DIR, "encodings.pk1")

print("Looking for known faces in:", KNOWN_FACES_DIR)

def register_known_faces():
    # These two lists will store encodings and names of known people
    known_encodings = []
    known_names = []

    print("Scanning known faces for registration...\n")

    # Check if the known faces directory exists before proceeding
    if not os.path.exists(KNOWN_FACES_DIR):
        print(f"Folder not found: {KNOWN_FACES_DIR}")
        return  # Stop the program if the folder doesn’t exist

    # Loop through each person's folder (e.g., /data/known_faces/arijit_singh)
    for person_name in os.listdir(KNOWN_FACES_DIR):
        person_folder = os.path.join(KNOWN_FACES_DIR, person_name)
        if not os.path.isdir(person_folder):
            continue  # Skip if it’s not a folder

        print(f"Processing: {person_name}")

        # Go through every JPG image inside the person's folder
        for filename in os.listdir(person_folder):
            if filename.lower().endswith(".jpg"):
                # Full path to the image file
                image_path = os.path.join(person_folder, filename)

                # Load image and extract face encodings
                image = face_recognition.load_image_file(image_path)
                encodings = face_recognition.face_encodings(image)

                # If a face is found, save the encoding and person name
                if len(encodings) > 0:
                    known_encodings.append(encodings[0])  # First face found
                    known_names.append(person_name)       # Folder name as person name
                else:
                    # Warn if no face was detected in the photo
                    print(f"No face detected in {filename}, skipping...")

    # Save both encodings and names together in a single .pk1 (pickle) file
    with open(ENCODINGS_FILE, "wb") as f:
        pickle.dump((known_encodings, known_names), f)

    print(f"\n Registration completed! Saved encodings to {ENCODINGS_FILE}")


if __name__ == "__main__":
    register_known_faces()
