import cv2

def draw_face_box(image, face_location, name):
    """Draws a rectangle (box) and name label around a detected face in the image."""
    try:
        top, right, bottom, left = face_location

        color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)

        cv2.rectangle(image, (left, top), (right, bottom), color, 2)

        cv2.rectangle(image, (left, bottom - 25), (right, bottom), color, cv2.FILLED)

        cv2.putText(image, name, (left + 6, bottom - 6),
                    cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1)
    except Exception as e:
        print(f"Error in draw_face_box: {e}")
