import os
import io
import threading
import sqlite3
import datetime
import json
from flask import Flask, render_template, request, jsonify, send_file, abort
import model  # Import as module to set MODEL_PATH

APP_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(APP_DIR)  # Parent folder: college-project/

# SHARED RESOURCES (accessed by both eduface-1 and Attendance-System2)
DB_PATH = os.path.join(BASE_DIR, "eduface.db")
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
MODEL_PATH = os.path.join(BASE_DIR, "model.pkl")

os.makedirs(DATASET_DIR, exist_ok=True)

# Update model.py to use shared MODEL_PATH
model.MODEL_PATH = MODEL_PATH

TRAIN_STATUS_FILE = os.path.join(APP_DIR, "train_status.json")

app = Flask(__name__, static_folder="static", template_folder="templates")

# ---------- DB helpers ----------
def init_db():
    """Initialize shared database with full schema for facial recognition"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Create tables if they don't exist (same schema as eduface-1)
    c.execute("""CREATE TABLE IF NOT EXISTS students (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    name          TEXT    NOT NULL,
                    email         TEXT    UNIQUE NOT NULL,
                    mobile        TEXT    NOT NULL,
                    dept          TEXT    NOT NULL,
                    rollno        TEXT    DEFAULT '',
                    userid        TEXT    UNIQUE NOT NULL,
                    password_hash TEXT    NOT NULL,
                    photo_url     TEXT    DEFAULT '',
                    face_enrolled INTEGER DEFAULT 0,
                    status        TEXT    DEFAULT 'pending',
                    created_at    TEXT    DEFAULT (datetime('now','localtime'))
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS attendance (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id      INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                    teacher_id      INTEGER,
                    date            TEXT    NOT NULL,
                    time            TEXT    DEFAULT '',
                    dept            TEXT    NOT NULL,
                    subject         TEXT    NOT NULL,
                    present         INTEGER NOT NULL DEFAULT 0,
                    photo_url       TEXT    DEFAULT '',
                    face_recognized INTEGER DEFAULT 0,
                    confidence      REAL    DEFAULT 0.0,
                    created_at      TEXT    DEFAULT (datetime('now','localtime'))
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS teachers (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    name          TEXT    NOT NULL,
                    email         TEXT    UNIQUE NOT NULL,
                    mobile        TEXT    NOT NULL,
                    dept          TEXT    NOT NULL,
                    userid        TEXT    UNIQUE NOT NULL,
                    password_hash TEXT    NOT NULL,
                    photo_url     TEXT    DEFAULT '',
                    status        TEXT    DEFAULT 'pending',
                    created_at    TEXT    DEFAULT (datetime('now','localtime'))
                )""")
    conn.commit()
    conn.close()

init_db()

# ---------- Train status helpers ----------
def write_train_status(status_dict):
    with open(TRAIN_STATUS_FILE, "w") as f:
        json.dump(status_dict, f)

def read_train_status():
    if not os.path.exists(TRAIN_STATUS_FILE):
        return {"running": False, "progress": 0, "message": "Not trained"}
    with open(TRAIN_STATUS_FILE, "r") as f:
        return json.load(f)

# ensure initial train status file exists
write_train_status({"running": False, "progress": 0, "message": "No training yet."})

# ---------- Routes ----------
@app.route("/")
def index():
    return render_template("index.html")

# Dashboard simple API for attendance stats (last 30 days)
@app.route("/attendance_stats")
def attendance_stats():
    import pandas as pd
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT timestamp FROM attendance", conn)
    conn.close()
    if df.empty:
        from datetime import date, timedelta
        days = [(date.today() - datetime.timedelta(days=i)).strftime("%d-%b") for i in range(29, -1, -1)]
        return jsonify({"dates": days, "counts": [0]*30})
    df['date'] = pd.to_datetime(df['timestamp']).dt.date
    last_30 = [ (datetime.date.today() - datetime.timedelta(days=i)) for i in range(29, -1, -1) ]
    counts = [ int(df[df['date'] == d].shape[0]) for d in last_30 ]
    dates = [ d.strftime("%d-%b") for d in last_30 ]
    return jsonify({"dates": dates, "counts": counts})

# -------- Add student (form) --------
@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    if request.method == "GET":
        return render_template("add_student.html")
    # POST: save student metadata and return student_id
    data = request.form
    name = data.get("name","").strip()
    roll = data.get("roll","").strip()
    subject = data.get("subject","").strip()
    sec = data.get("sec","").strip()
    department = data.get("department","").strip()
    if not name:
        return jsonify({"error":"name required"}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.datetime.utcnow().isoformat()
    c.execute("INSERT INTO students (name, roll, subject, section, department, created_at) VALUES (?, ?, ?, ?, ?, ?)",
              (name, roll, subject, sec, department, now))
    sid = c.lastrowid
    conn.commit()
    conn.close()
    # create dataset folder for this student
    os.makedirs(os.path.join(DATASET_DIR, str(sid)), exist_ok=True)
    return jsonify({"student_id": sid})

# -------- Upload face images (after capture) --------
@app.route("/upload_face", methods=["POST"])
def upload_face():
    student_id = request.form.get("student_id")
    if not student_id:
        return jsonify({"error":"student_id required"}), 400
    files = request.files.getlist("images[]")
    saved = 0
    folder = os.path.join(DATASET_DIR, student_id)
    if not os.path.isdir(folder):
        os.makedirs(folder, exist_ok=True)
    for f in files:
        try:
            fname = f"{datetime.datetime.utcnow().timestamp():.6f}_{saved}.jpg"
            path = os.path.join(folder, fname)
            f.save(path)
            saved += 1
        except Exception as e:
            app.logger.error("save error: %s", e)
    return jsonify({"saved": saved})

# -------- Train model (start background thread) --------
@app.route("/train_model", methods=["GET"])
def train_model_route():
    # if already running, respond accordingly
    status = read_train_status()
    if status.get("running"):
        return jsonify({"status":"already_running"}), 202
    # reset status
    write_train_status({"running": True, "progress": 0, "message": "Starting training"})
    # start background thread
    t = threading.Thread(target=model.train_model_background, args=(DATASET_DIR, lambda p,m: write_train_status({"running": True, "progress": p, "message": m})))
    t.daemon = True
    t.start()
    return jsonify({"status":"started"}), 202

# -------- Train progress (polling) --------
@app.route("/train_status", methods=["GET"])
def train_status():
    return jsonify(read_train_status())

# ═══════════════════════════════════════════════════════════════
# API ENDPOINTS FOR EDUFACE-1 INTEGRATION
# ═══════════════════════════════════════════════════════════════

@app.route("/api/train-model", methods=["POST"])
def api_train_model():
    """API endpoint for eduface-1 to trigger model training
    
    Request body (JSON):
      {
        "student_id": 1  // optional: if provided, can log which student triggered training
      }
    
    Response:
      {
        "ok": true,
        "status": "training_started|already_running|error",
        "message": "..."
      }
    """
    try:
        data = request.get_json()
        student_id = data.get("student_id") if data else None
        
        # Check if training is already running
        status = read_train_status()
        if status.get("running"):
            return jsonify({
                "ok": False,
                "status": "already_running",
                "message": "Model training already in progress"
            }), 202  # Accepted but already processing
        
        # Start training
        write_train_status({
            "running": True,
            "progress": 0,
            "message": f"Starting training (triggered by student_id={student_id})" if student_id else "Starting training"
        })
        
        # Start background thread
        def training_callback(progress, message):
            write_train_status({"running": progress < 100, "progress": progress, "message": message})
            # When training completes (progress == 100), update face_enrolled flag in database
            if progress >= 100:
                try:
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute("UPDATE students SET face_enrolled=1 WHERE id=?", (student_id,))
                    conn.commit()
                    conn.close()
                    app.logger.info(f"Updated face_enrolled=1 for student_id={student_id}")
                except Exception as e:
                    app.logger.error(f"Error updating face_enrolled: {str(e)}")
        
        t = threading.Thread(
            target=model.train_model_background,
            args=(DATASET_DIR, training_callback)
        )
        t.daemon = True
        t.start()
        
        return jsonify({
            "ok": True,
            "status": "training_started",
            "message": f"Model training started for student_id={student_id}" if student_id else "Model training started",
            "student_id": student_id
        }), 202  # Accepted - training in background
    
    except Exception as e:
        app.logger.error(f"Error in api_train_model: {str(e)}")
        return jsonify({
            "ok": False,
            "status": "error",
            "message": str(e)
        }), 500

@app.route("/api/train-status", methods=["GET"])
def api_train_status():
    """API endpoint for eduface-1 to check training status
    
    Response:
      {
        "running": true|false,
        "progress": 0-100,
        "message": "..."
      }
    """
    return jsonify(read_train_status())

# -------- Mark attendance page --------
@app.route("/mark_attendance", methods=["GET"])
def mark_attendance_page():
    return render_template("mark_attendance.html")

# -------- Recognize face endpoint (POST image) --------
@app.route("/recognize_face", methods=["POST"])
def recognize_face():
    if "image" not in request.files:
        return jsonify({"recognized": False, "error":"no image"}), 400
    img_file = request.files["image"]
    try:
        emb = model.extract_embedding_for_image(img_file.stream)
        if emb is None:
            app.logger.info("Face detection failed - no face detected in image")
            return jsonify({"recognized": False, "error":"face_not_detected"}), 200
        # attempt prediction
        clf = model.load_model_if_exists()
        if clf is None:
            app.logger.warning("Model not trained yet")
            return jsonify({"recognized": False, "error":"model_not_trained"}), 200
        pred_label, conf = model.predict_with_model(clf, emb)
        # lower threshold for RandomForest (0.35 instead of 0.5)
        CONFIDENCE_THRESHOLD = 0.35
        if conf < CONFIDENCE_THRESHOLD:
            app.logger.info(f"Low confidence: {conf:.2f} (threshold: {CONFIDENCE_THRESHOLD})")
            return jsonify({"recognized": False, "confidence": float(conf), "error":"low_confidence"}), 200
        # find student name
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT name FROM students WHERE id=?", (int(pred_label),))
        row = c.fetchone()
        name = row[0] if row else "Unknown"
        # save attendance record with timestamp
        ts = datetime.datetime.utcnow().isoformat()
        c.execute("INSERT INTO attendance (student_id, name, timestamp) VALUES (?, ?, ?)", (int(pred_label), name, ts))
        conn.commit()
        conn.close()
        app.logger.info(f"Attendance recorded: {name} (ID: {pred_label}, conf: {conf:.2f})")
        return jsonify({"recognized": True, "student_id": int(pred_label), "name": name, "confidence": float(conf)}), 200
    except Exception as e:
        app.logger.exception("recognize error")
        return jsonify({"recognized": False, "error": str(e)}), 500

# -------- Attendance records & filters --------
@app.route("/attendance_record", methods=["GET"])
def attendance_record():
    period = request.args.get("period", "all")  # all, daily, weekly, monthly
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    q = """SELECT a.id, s.name, s.roll, s.department, s.subject, s.section, a.timestamp, a.student_id
             FROM attendance a 
             LEFT JOIN students s ON a.student_id = s.id"""
    params = ()
    if period == "daily":
        today = datetime.date.today().isoformat()
        q += " WHERE date(a.timestamp) = ?"
        params = (today,)
    elif period == "weekly":
        start = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        q += " WHERE date(a.timestamp) >= ?"
        params = (start,)
    elif period == "monthly":
        start = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
        q += " WHERE date(a.timestamp) >= ?"
        params = (start,)
    q += " ORDER BY a.timestamp DESC"
    c.execute(q, params)
    rows = c.fetchall()
    conn.close()
    
    # Deduplicate: keep only the latest record per student
    seen_students = {}
    unique_rows = []
    for row in rows:
        student_id = row[7]  # student_id is at index 7
        if student_id not in seen_students:
            seen_students[student_id] = True
            unique_rows.append(row[:7])  # Return only first 7 columns (exclude student_id)
    
    return render_template("attendance_record.html", records=unique_rows, period=period)

# -------- CSV download --------
@app.route("/download_csv", methods=["GET"])
def download_csv():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, student_id, name, timestamp FROM attendance ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()
    output = io.StringIO()
    output.write("id,student_id,name,timestamp\n")
    for r in rows:
        output.write(f'{r[0]},{r[1]},{r[2]},{r[3]}\n')
    mem = io.BytesIO()
    mem.write(output.getvalue().encode("utf-8"))
    mem.seek(0)
    return send_file(mem, as_attachment=True, download_name="attendance.csv", mimetype="text/csv")

# -------- Diagnostic endpoint --------
@app.route("/diagnosis", methods=["GET"])
def diagnosis():
    """Check system status and provide troubleshooting info"""
    import os
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM students")
    student_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM attendance")
    attendance_count = c.fetchone()[0]
    conn.close()
    
    # Check model
    model_exists = os.path.exists(MODEL_PATH)
    
    # Check dataset
    dataset_dirs = []
    if os.path.isdir(DATASET_DIR):
        dataset_dirs = [d for d in os.listdir(DATASET_DIR) if os.path.isdir(os.path.join(DATASET_DIR, d))]
    
    # Check faces per student
    faces_per_student = {}
    for sid in dataset_dirs:
        folder = os.path.join(DATASET_DIR, sid)
        files = [f for f in os.listdir(folder) if f.lower().endswith((".jpg",".jpeg",".png"))]
        faces_per_student[sid] = len(files)
    
    return jsonify({
        "system_status": {
            "students_registered": student_count,
            "attendance_records": attendance_count,
            "model_trained": model_exists,
            "dataset_students": len(dataset_dirs),
            "faces_per_student": faces_per_student
        },
        "recommendations": generate_recommendations(student_count, model_exists, dataset_dirs, faces_per_student),
        "next_steps": get_next_steps(student_count, model_exists)
    })

def generate_recommendations(student_count, model_trained, dataset_dirs, faces_per_student):
    """Generate recommendations based on current status"""
    recs = []
    
    if student_count == 0:
        recs.append("No students registered! Go to Add Student first.")
    
    if len(dataset_dirs) == 0:
        recs.append("No face images collected! Add faces for students.")
    elif len(dataset_dirs) < student_count:
        recs.append(f"Only {len(dataset_dirs)}/{student_count} students have faces. Collect more.")
    
    for sid, count in faces_per_student.items():
        if count < 5:
            recs.append(f"Student {sid} has only {count} face images. Collect at least 5-10.")
    
    if not model_trained and len(dataset_dirs) > 0:
        recs.append("Model not trained! Click Train Model on dashboard.")
    elif not model_trained:
        recs.append("Cannot train model - no face data exists.")
    
    if model_trained and len(recs) == 0:
        recs.append("System ready! You can now mark attendance.")
    
    return recs

def get_next_steps(student_count, model_trained):
    """Get actionable next steps"""
    if student_count == 0:
        return [
            "1. Go to Add Student page",
            "2. Enter student name, roll, department",
            "3. Click Add Student to get ID"
        ]
    elif not model_trained:
        return [
            "1. For each student, go to Mark Attendance",
            "2. Capture 5-10 clear face images",
            "3. Go to Dashboard and click Train Model",
            "4. Wait for training to complete"
        ]
    else:
        return [
            "1. Go to Mark Attendance",
            "2. Click Start to use camera",
            "3. Your faces will be recognized automatically",
            "4. Check View Records to see attendance"
        ]

# -------- Students API for listing/editing --------
@app.route("/students", methods=["GET"])
def students_list():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, roll, subject, section, department, created_at FROM students ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    data = [ {"id":r[0],"name":r[1],"roll":r[2],"subject":r[3],"section":r[4],"department":r[5],"created_at":r[6]} for r in rows ]
    return jsonify({"students": data})

@app.route("/students/<int:sid>", methods=["DELETE"])
def delete_student(sid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM students WHERE id=?", (sid,))
    c.execute("DELETE FROM attendance WHERE student_id=?", (sid,))
    conn.commit()
    conn.close()
    # also delete dataset folder
    folder = os.path.join(DATASET_DIR, str(sid))
    if os.path.isdir(folder):
        import shutil
        shutil.rmtree(folder, ignore_errors=True)
    return jsonify({"deleted": True})

# -------- Delete attendance record --------
@app.route("/delete_attendance/<int:record_id>", methods=["DELETE"])
def delete_attendance(record_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM attendance WHERE id=?", (record_id,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": True})

# ═══════════════════════════════════════════════════════════════
# HEALTH CHECK ENDPOINT
# ═══════════════════════════════════════════════════════════════
@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint - used by eduface-1 to verify service is running"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        student_count = c.execute("SELECT COUNT(*) FROM students WHERE face_enrolled=1").fetchone()[0]
        conn.close()
        return jsonify({
            "ok": True,
            "service": "Attendance-System2 ML Engine",
            "port": 5100,
            "model_status": "ready" if os.path.exists(MODEL_PATH) else "not_trained",
            "students_trained": student_count
        })
    except Exception as e:
        conn.close()
        return jsonify({"ok": False, "error": str(e)}), 500

# ────────────────────────────────────────────────────────────────
# RUN (Port 5100 - ML Engine)
# ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 70)
    print("🤖 Attendance-System2 ML Engine")
    print("=" * 70)
    print(f"📁 Dataset: {DATASET_DIR}")
    print(f"💾 Database: {DB_PATH}")
    print(f"🔧 Model: {MODEL_PATH}")
    print("=" * 70)
    print("🚀 Starting on Port 5100...")
    print("=" * 70)
    app.run(host='0.0.0.0', port=5100, debug=True)