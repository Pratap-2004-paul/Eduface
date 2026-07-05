import face_recognition
import os
import pickle
import cv2

print("=" * 50)
print("   ENCODING FACES FROM PHOTOS")
print("=" * 50)

known_encodings = []
known_names = []

# Path to student faces folder
dataset_path = "student_faces"

# Check if folder exists
if not os.path.exists(dataset_path):
    print("ERROR: student_faces folder not found!")
    print("Run train_model.py first to register students.")
    exit()

students = os.listdir(dataset_path)

if len(students) == 0:
    print("No students found in student_faces folder.")
    print("Run train_model.py first.")
    exit()

print(f"\nFound {len(students)} student(s): {students}\n")

for student_name in students:
    student_folder = os.path.join(dataset_path, student_name)

    if not os.path.isdir(student_folder):
        continue

    photos = os.listdir(student_folder)
    print(f"Processing: {student_name} ({len(photos)} photos)")

    for photo_file in photos:
        photo_path = os.path.join(student_folder, photo_file)

        # Load the image
        image = face_recognition.load_image_file(photo_path)

        # Find faces in the image
        encodings = face_recognition.face_encodings(image)

        if len(encodings) == 0:
            print(f"  WARNING: No face found in {photo_file} — skipping")
            continue

        # Save the first face found
        known_encodings.append(encodings[0])
        known_names.append(student_name)
        print(f"  ✓ Encoded: {photo_file}")

# Save all encodings to a file
data = {
    "encodings": known_encodings,
    "names": known_names
}

with open("face_encodings.pkl", "wb") as f:
    pickle.dump(data, f)

print(f"\n SUCCESS!")
print(f"Total face encodings saved: {len(known_encodings)}")
print(f"Saved to: face_encodings.pkl")
print(f"\nNext step: Run app.py to start the web server!")