# Smart Attendance System

A web-based attendance management system using Face Recognition AI.

## Features
- Face recognition attendance via webcam, photo, and video upload
- Role-based panels for Admin, Teacher, and Student
- Real-time chat between teachers and students
- Department-wise attendance management
- CSV export with pivot table format

## Tech Stack
- Python 3.11
- Flask + Flask-SocketIO
- face_recognition library
- SQLite database
- HTML, CSS, JavaScript

## Setup Instructions


### 2. Create virtual environment
python -m venv venv
venv\Scripts\activate

### 3. Install dependencies
pip install -r requirements.txt

### 4. Initialize database
python add_departments.py

### 5. Run the server
python app.py

### 6. Open browser
http://127.0.0.1:5000

## Default Admin Login
Email    : admin@attendance.com
Password : admin123

## Project Structure
attendance_system/
├── app.py              # Flask server + SocketIO
├── database.py         # All database operations
├── requirements.txt    # Python dependencies
├── templates/          # HTML pages
│   ├── admin/          # Admin panel pages
│   ├── teacher/        # Teacher panel pages
│   └── student/        # Student panel pages
└── static/             # CSS files