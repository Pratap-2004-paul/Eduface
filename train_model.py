import cv2
import os

def capture_faces(student_name):
    # Create folder for this student
    folder_path = f"student_faces/{student_name}"
    os.makedirs(folder_path, exist_ok=True)

    # Open webcam
    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        print("ERROR: Cannot open webcam. Check if your camera is connected.")
        return

    print(f"\n Camera opened for: {student_name}")
    print(" Look at the camera. Press SPACE to capture a photo.")
    print(" You need 5 photos. Press Q to quit early.\n")

    photo_count = 0
    total_photos = 5

    while photo_count < total_photos:
        # Read frame from webcam
        success, frame = camera.read()

        if not success:
            print("Failed to read from camera.")
            break

        # Show counter on screen
        remaining = total_photos - photo_count
        cv2.putText(
            frame,
            f"Student: {student_name}  |  Photos taken: {photo_count}/{total_photos}  |  SPACE=Capture  Q=Quit",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2
        )

        # Show the live camera window
        cv2.imshow("Face Registration - Press SPACE to capture", frame)

        # Wait for key press
        key = cv2.waitKey(1) & 0xFF

        if key == ord(' '):  # SPACE key
            photo_count += 1
            photo_path = f"{folder_path}/photo{photo_count}.jpg"
            cv2.imwrite(photo_path, frame)
            print(f"  Photo {photo_count} saved → {photo_path}")

        elif key == ord('q'):  # Q key to quit
            print("Quitting early...")
            break

    # Clean up
    camera.release()
    cv2.destroyAllWindows()

    print(f"\n Done! {photo_count} photos saved for {student_name}")
    print(f" Folder: {folder_path}\n")


def main():
    print("=" * 50)
    print("   SMART ATTENDANCE - FACE REGISTRATION")
    print("=" * 50)

    while True:
        print("\nOptions:")
        print("  1. Register a new student")
        print("  2. Quit")

        choice = input("\nEnter choice (1 or 2): ").strip()

        if choice == "1":
            name = input("Enter student full name (no spaces, use underscore e.g. Rahul_Singh): ").strip()

            if name == "":
                print("Name cannot be empty. Try again.")
                continue

            capture_faces(name)

            more = input("Register another student? (yes/no): ").strip().lower()
            if more != "yes":
                break

        elif choice == "2":
            break
        else:
            print("Invalid choice. Enter 1 or 2.")

    print("\nFace registration complete!")
    print("Now run: python encode_faces.py")


if __name__ == "__main__":
    main()