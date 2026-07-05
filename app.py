from flask import (
    Flask, request, jsonify,
    render_template, send_file,
    session, redirect, url_for, flash
)
from flask_cors import CORS
import face_recognition
import numpy as np
import pickle
import base64
import io
import csv
import os
import cv2
import tempfile
from PIL import Image
from datetime import date
from functools import wraps
from flask_socketio import SocketIO, emit, join_room, leave_room
from database import (
    save_group_message,
    get_group_messages,
    save_private_message,
    get_private_messages,
    mark_messages_read,
    get_unread_count,
    get_chat_contacts
)

from database import (
    init_db,
    get_all_departments,
    register_user,
    login_user,
    get_user_by_id,
    get_pending_users,
    get_all_users,
    update_user_status,
    delete_user,
    create_department,
    delete_department,
    get_students_by_dept,
    mark_attendance,
    get_attendance_by_dept,
    delete_attendance_record,
    get_student_attendance,
    get_student_attendance_stats,
    save_face_data,
    get_face_data,
    get_all_face_data_for_dept
)

# ── App setup ──────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = "smartattendance_secret_key_2024"
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="eventlet"
)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB max upload
CORS(app)

# ── Face encodings (global — loaded at startup) ────────────
ENCODINGS_FILE = "face_encodings.pkl"

def load_encodings():
    if not os.path.exists(ENCODINGS_FILE):
        return [], []
    with open(ENCODINGS_FILE, "rb") as f:
        data = pickle.load(f)
    print(f"✓ Loaded {len(data['names'])} face encodings.")
    return data["encodings"], data["names"]

known_encodings, known_names = load_encodings()

def load_dept_encodings(dept_id):
    """
    Load ALL encodings for ALL students in a department.
    Each student may have multiple encodings (one per photo).
    Returns (encodings_list, names_list, ids_list)
    """
    dept_faces     = get_all_face_data_for_dept(dept_id)
    dept_encodings = []
    dept_names     = []
    dept_ids       = []

    for face in dept_faces:
        path = face["encoding_path"]
        if not os.path.exists(path):
            continue
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)

            # Handle both old format (single encoding)
            # and new format (list of encodings)
            if isinstance(data, list):
                encodings = data
            else:
                encodings = [data]

            for enc in encodings:
                dept_encodings.append(enc)
                dept_names.append(face["full_name"])
                dept_ids.append(face["user_id"])

        except Exception as e:
            print(f"Error loading encoding {path}: {e}")
            continue

    print(f"Loaded {len(dept_encodings)} total encodings "
          f"for {len(dept_faces)} students in dept {dept_id}")
    return dept_encodings, dept_names, dept_ids


# ── Auth decorators ────────────────────────────────────────

def login_required(f):
    """Redirect to login if not logged in."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    """Allow only specific roles."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login_page"))
            if session.get("role") not in roles:
                return redirect(url_for("login_page"))
            return f(*args, **kwargs)
        return decorated
    return decorator


# ══════════════════════════════════════════════
#  AUTH ROUTES
# ══════════════════════════════════════════════

@app.route("/")
def home():
    """Show landing page if not logged in, else redirect to dashboard."""
    if "user_id" in session:
        role = session.get("role")
        if role == "admin":
            return redirect(url_for("admin_dashboard"))
        elif role == "teacher":
            return redirect(url_for("teacher_dashboard"))
        elif role == "student":
            return redirect(url_for("student_dashboard"))
    return render_template("home.html")


# ══════════════════════════════════════════════
#  LOGIN ROUTES — separate per role
# ══════════════════════════════════════════════

@app.route("/login")
def login_page():
    """Role selection page."""
    if "user_id" in session:
        return redirect(url_for("home"))
    return render_template("login_select.html")


@app.route("/login/admin", methods=["GET", "POST"])
def login_admin():
    """Admin login page."""
    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "GET":
        return render_template("login_admin.html")

    email    = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    if not email or not password:
        return render_template("login_admin.html",
            error="Please enter both email and password.",
            prefill_email=email)

    user, message = login_user(email, password)

    if not user:
        return render_template("login_admin.html",
            error=message,
            prefill_email=email)

    if user["role"] != "admin":
        return render_template("login_admin.html",
            error="This account is not an admin account. "
                  "Please use the correct login page.",
            prefill_email=email)

    # Save session
    session["user_id"]   = user["id"]
    session["full_name"] = user["full_name"]
    session["role"]      = user["role"]
    session["dept_id"]   = user["dept_id"]
    session["dept_name"] = user["dept_name"]

    return redirect(url_for("admin_dashboard"))


@app.route("/login/teacher", methods=["GET", "POST"])
def login_teacher():
    """Teacher login page."""
    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "GET":
        return render_template("login_teacher.html")

    email    = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    if not email or not password:
        return render_template("login_teacher.html",
            error="Please enter both email and password.",
            prefill_email=email)

    user, message = login_user(email, password)

    if not user:
        return render_template("login_teacher.html",
            error=message,
            prefill_email=email)

    if user["role"] != "teacher":
        return render_template("login_teacher.html",
            error="This account is not a teacher account. "
                  "Please use the correct login page.",
            prefill_email=email)

    # Save session
    session["user_id"]   = user["id"]
    session["full_name"] = user["full_name"]
    session["role"]      = user["role"]
    session["dept_id"]   = user["dept_id"]
    session["dept_name"] = user["dept_name"]

    return redirect(url_for("teacher_dashboard"))


@app.route("/login/student", methods=["GET", "POST"])
def login_student():
    """Student login page."""
    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "GET":
        return render_template("login_student.html")

    email    = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    if not email or not password:
        return render_template("login_student.html",
            error="Please enter both email and password.",
            prefill_email=email)

    user, message = login_user(email, password)

    if not user:
        return render_template("login_student.html",
            error=message,
            prefill_email=email)

    if user["role"] != "student":
        return render_template("login_student.html",
            error="This account is not a student account. "
                  "Please use the correct login page.",
            prefill_email=email)

    # Save session
    session["user_id"]   = user["id"]
    session["full_name"] = user["full_name"]
    session["role"]      = user["role"]
    session["dept_id"]   = user["dept_id"]
    session["dept_name"] = user["dept_name"]

    return redirect(url_for("student_dashboard"))


@app.route("/register", methods=["GET", "POST"])
def register_page():
    if "user_id" in session:
        return redirect(url_for("home"))

    departments = get_all_departments()

    if request.method == "GET":
        return render_template(
        "register.html",
        departments=departments,
        prefill=None,
        role="teacher",
        error=None,
        success=None,
        pending=False
    )

    # POST — process registration
    full_name        = request.form.get("full_name", "").strip()
    email            = request.form.get("email", "").strip().lower()
    password         = request.form.get("password", "").strip()
    confirm_password = request.form.get("confirm_password", "").strip()
    role             = request.form.get("role", "student").strip()
    department_id    = request.form.get("department_id", "").strip()

    # Validation
    prefill = {
        "full_name":   full_name,
        "email":       email,
        "dept_id":     int(department_id) if department_id else None
    }

    if not all([full_name, email, password, department_id]):
        return render_template("register.html",
            error="All fields are required.",
            departments=departments,
            prefill=prefill,
            role=role)

    if password != confirm_password:
        return render_template("register.html",
            error="Passwords do not match.",
            departments=departments,
            prefill=prefill,
            role=role)

    if len(password) < 6:
        return render_template("register.html",
            error="Password must be at least 6 characters.",
            departments=departments,
            prefill=prefill,
            role=role)

    if role not in ["teacher", "student"]:
        return render_template("register.html",
            error="Invalid role selected.",
            departments=departments,
            prefill=prefill,
            role=role)

    success, message = register_user(
        full_name, email, password, role, int(department_id)
    )

    if not success:
        return render_template("register.html",
            error=message,
            departments=departments,
            prefill=prefill,
            role=role)

    # Registration successful — show pending notice
    return render_template(
    "register.html",
    departments=departments,
    prefill=None,
    role=role,
    error=None,
    success="Account created! Waiting for admin approval.",
    pending=True
)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


# ══════════════════════════════════════════════
#  ADMIN ROUTES
# ══════════════════════════════════════════════

@app.route("/admin/dashboard")
@role_required("admin")
def admin_dashboard():
    user = get_user_by_id(session["user_id"])

    if not user:
        session.clear()
        return redirect(url_for("login_page"))
    all_teachers  = get_all_users("teacher")
    all_students  = get_all_users("student")
    pending_users = get_pending_users()
    departments   = get_all_departments()

    stats = {
        "teachers":    len(all_teachers),
        "students":    len(all_students),
        "pending":     len(pending_users),
        "departments": len(departments)
    }

    recent_users = get_all_users()[:8]

    return render_template("admin/dashboard.html",
        user          = user,
        stats         = stats,
        pending_users = pending_users,
        pending_count = len(pending_users),
        recent_users  = recent_users
    )


@app.route("/admin/pending")
@role_required("admin")
def admin_pending():
    user          = get_user_by_id(session["user_id"])
    pending_users = get_pending_users()
    message       = request.args.get("message")
    message_type  = request.args.get("type", "success")

    return render_template("admin/pending.html",
        user          = user,
        users         = pending_users,
        pending_count = len(pending_users),
        message       = message,
        message_type  = message_type
    )


@app.route("/admin/approve/<int:user_id>", methods=["POST"])
@role_required("admin")
def admin_approve(user_id):
    update_user_status(user_id, "approved")
    return redirect(url_for("admin_pending",
        message="User approved successfully.",
        type="success"))


@app.route("/admin/reject/<int:user_id>", methods=["POST"])
@role_required("admin")
def admin_reject(user_id):
    update_user_status(user_id, "rejected")
    return redirect(url_for("admin_pending",
        message="User rejected.",
        type="error"))


@app.route("/admin/delete/<int:user_id>", methods=["POST"])
@role_required("admin")
def admin_delete_user(user_id):
    delete_user(user_id)
    return redirect(url_for("admin_users",
        message="User deleted.",
        type="success"))

@app.route("/admin/edit/<int:user_id>", methods=["GET", "POST"])
@role_required("admin")
def admin_edit_user(user_id):
    """Admin edits teacher or student details."""
    admin       = get_user_by_id(session["user_id"])
    user        = get_user_by_id(user_id)
    departments = get_all_departments()

    if not user:
        return redirect(url_for("admin_users",
            message="User not found.", type="error"))

    if request.method == "GET":
        return render_template("admin/edit_user.html",
            admin       = admin,
            user        = user,
            departments = departments,
            error       = None,
            success     = None
        )

    # ── POST — save changes ────────────────────
    full_name     = request.form.get("full_name","").strip()
    email         = request.form.get("email","").strip().lower()
    department_id = request.form.get("department_id","").strip()
    status        = request.form.get("status","").strip()
    new_password  = request.form.get("new_password","").strip()

    if not all([full_name, email, department_id, status]):
        return render_template("admin/edit_user.html",
            admin       = admin,
            user        = user,
            departments = departments,
            error       = "All fields are required.",
            success     = None
        )

    from database import update_user_details
    ok, msg = update_user_details(
        user_id, full_name, email,
        int(department_id), status,
        new_password if new_password else None
    )

    if not ok:
        return render_template("admin/edit_user.html",
            admin       = admin,
            user        = user,
            departments = departments,
            error       = msg,
            success     = None
        )

    # Refresh user data after update
    user = get_user_by_id(user_id)
    return render_template("admin/edit_user.html",
        admin       = admin,
        user        = user,
        departments = departments,
        error       = None,
        success     = f"{user['full_name']} updated successfully."
    )


@app.route("/admin/users")
@role_required("admin")
def admin_users():
    user         = get_user_by_id(session["user_id"])
    role_filter  = request.args.get("role", None)
    message      = request.args.get("message")
    message_type = request.args.get("type", "success")
    users        = get_all_users(role_filter)

    # Add face registration info for students
    from database import get_face_data as gfd
    for u in users:
        if u["role"] == "student":
            u["face_registered"] = gfd(u["id"]) is not None
        else:
            u["face_registered"] = None

    # Face stats per dept for admin overview
    from database import get_all_face_stats
    face_stats = get_all_face_stats()

    return render_template("admin/users.html",
        user         = user,
        users        = users,
        role_filter  = role_filter,
        message      = message,
        message_type = message_type,
        face_stats   = face_stats
    )


@app.route("/admin/departments")
@role_required("admin")
def admin_departments():
    user        = get_user_by_id(session["user_id"])
    departments = get_all_departments()
    message     = request.args.get("message")
    message_type= request.args.get("type", "success")

    return render_template("admin/departments.html",
        user         = user,
        departments  = departments,
        message      = message,
        message_type = message_type
    )


@app.route("/admin/departments/add", methods=["POST"])
@role_required("admin")
def admin_add_department():
    name = request.form.get("name", "").strip()
    if not name:
        return redirect(url_for("admin_departments",
            message="Department name cannot be empty.",
            type="error"))

    success, result = create_department(name)
    if success:
        return redirect(url_for("admin_departments",
            message=f"Department '{name}' created.",
            type="success"))
    else:
        return redirect(url_for("admin_departments",
            message=result,
            type="error"))


@app.route("/admin/departments/delete/<int:dept_id>",
           methods=["POST"])
@role_required("admin")
def admin_delete_department(dept_id):
    delete_department(dept_id)
    return redirect(url_for("admin_departments",
        message="Department deleted.",
        type="success"))


# ══════════════════════════════════════════════
#  TEACHER ROUTES
# ══════════════════════════════════════════════

@app.route("/teacher/dashboard")
@role_required("teacher")
def teacher_dashboard():
    user = get_user_by_id(session["user_id"])

    if not user:
        session.clear()
        return redirect(url_for("login_page"))
    dept_id = user["dept_id"]
    today   = date.today().strftime("%Y-%m-%d")

    students      = get_students_by_dept(dept_id)
    today_records = get_attendance_by_dept(dept_id, today)
    all_records   = get_attendance_by_dept(dept_id)

    # Build set of student IDs present today
    import sqlite3 as _sq
    conn = _sq.connect("attendance.db")
    c    = conn.cursor()
    c.execute(
        "SELECT student_id FROM attendance "
        "WHERE date=? AND department_id=?",
        (today, dept_id)
    )
    present_id_set = {r[0] for r in c.fetchall()}
    conn.close()

    stats = {
        "total_students": len(students),
        "today_present":  len(today_records),
        "today_absent":   max(
            0, len(students) - len(today_records)
        ),
        "total_records":  len(all_records)
    }

    return render_template("teacher/dashboard.html",
        user              = user,
        stats             = stats,
        students          = students,
        today_records     = today_records,
        all_records       = all_records,
        today_present_ids = present_id_set,
        unread_count      = get_unread_count(user["id"])
    )

@app.route("/teacher/students")
@role_required("teacher")
def teacher_students():
    user    = get_user_by_id(session["user_id"])
    dept_id = user["dept_id"]
    students= get_students_by_dept(dept_id)

    from database import get_student_attendance_stats
    for s in students:
        stats = get_student_attendance_stats(s["id"])
        s["present_days"]   = stats["present"]
        s["percentage"]     = stats["percentage"]
        s["face_registered"] = get_face_data(s["id"]) is not None

    return render_template("teacher/students.html",
        user     = user,
        students = students
    )


@app.route("/teacher/attendance")
@role_required("teacher")
def teacher_attendance():
    user    = get_user_by_id(session["user_id"])
    dept_id = user["dept_id"]
    today   = date.today().strftime("%Y-%m-%d")

    today_records = get_attendance_by_dept(dept_id, today)
    all_records   = get_attendance_by_dept(dept_id)

    return render_template("teacher/attendance.html",
        user          = user,
        today_records = today_records,
        all_records   = all_records,
        today_count   = len(today_records)
    )


@app.route("/teacher/recognize", methods=["POST"])
@role_required("teacher")
def teacher_recognize():
    """Face recognition from webcam for teacher's dept."""
    try:
        data    = request.get_json()
        dept_id = data.get("dept_id") or session.get("dept_id")

        if not data or "image" not in data:
            return jsonify({"success": False,
                            "message": "No image received."})

        # Decode image
        image_data = data["image"]
        if "," in image_data:
            image_data = image_data.split(",")[1]

        image_bytes = base64.b64decode(image_data)
        pil_image   = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        np_image    = np.array(pil_image)

        # Load ALL encodings for this dept
        dept_encodings, dept_names, dept_ids = \
            load_dept_encodings(dept_id)

        if not dept_encodings:
            return jsonify({
                "success": False,
                "message": "No registered faces in your "
                           "department. Ask students to "
                           "register their faces first."
            })

        # Find faces
        face_locations  = face_recognition.face_locations(np_image)
        face_encodings_list = face_recognition.face_encodings(
            np_image, face_locations
        )

        if not face_encodings_list:
            return jsonify({
                "success": False,
                "message": "No face detected. "
                           "Look directly at camera."
            })

        results = []
        for face_enc in face_encodings_list:
            matches   = face_recognition.compare_faces(
                dept_encodings, face_enc, tolerance=0.5
            )
            distances = face_recognition.face_distance(
                dept_encodings, face_enc
            )

            name       = "Unknown"
            student_id = None

            if len(distances) > 0:
                best = int(np.argmin(distances))
                if matches[best]:
                    name       = dept_names[best]
                    student_id = dept_ids[best]

            if name != "Unknown" and student_id:
                ok, msg = mark_attendance(
                    student_id, dept_id, session["user_id"]
                )
                results.append({
                    "name":    name,
                    "success": ok,
                    "message": f"{name} — {msg}"
                })
            else:
                results.append({
                    "name":    "Unknown",
                    "success": False,
                    "message": "Face not recognized in your department."
                })

        return jsonify({
            "success":     True,
            "faces_found": len(face_encodings_list),
            "results":     results
        })

    except Exception as e:
        return jsonify({"success": False,
                        "message": f"Error: {str(e)}"}), 500


@app.route("/teacher/process-video", methods=["POST"])
@role_required("teacher")
def teacher_process_video():
    """Video upload face recognition for teacher's dept."""
    try:
        dept_id = request.form.get("dept_id") or session.get("dept_id")
        dept_id = int(dept_id)

        if "video" not in request.files:
            return jsonify({"success": False,
                            "message": "No video file."})

        video_file = request.files["video"]
        suffix = os.path.splitext(video_file.filename)[1]

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=suffix
        ) as tmp:
            video_file.save(tmp.name)
            tmp_path = tmp.name

        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            os.unlink(tmp_path)
            return jsonify({"success": False,
                            "message": "Cannot open video."})

        fps          = cap.get(cv2.CAP_PROP_FPS) or 25
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_sec = int(total_frames / fps)
        sample_every = int(fps)

        # Load ALL encodings for this dept
        dept_encodings, dept_names, dept_ids = \
            load_dept_encodings(dept_id)

        results_by_student = {}
        frame_index        = 0
        processed_frames   = 0

        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_index % sample_every == 0:
                ts        = int(frame_index / fps)
                processed_frames += 1
                rgb       = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                locs      = face_recognition.face_locations(rgb)
                encs      = face_recognition.face_encodings(rgb, locs)

                for enc in encs:
                    matches   = face_recognition.compare_faces(
                        dept_encodings, enc, tolerance=0.5
                    )
                    distances = face_recognition.face_distance(
                        dept_encodings, enc
                    )
                    name = "Unknown"
                    sid  = None
                    if len(distances) > 0:
                        best = int(np.argmin(distances))
                        if matches[best]:
                            name = dept_names[best]
                            sid  = dept_ids[best]

                    if name != "Unknown":
                        if name not in results_by_student:
                            results_by_student[name] = {
                                "timestamps": [],
                                "student_id": sid
                            }
                        results_by_student[name]["timestamps"].append(ts)

            frame_index += 1

        cap.release()
        os.unlink(tmp_path)

        attendance_results = []
        for sname, sdata in results_by_student.items():
            ok, msg = mark_attendance(
                sdata["student_id"], dept_id, session["user_id"]
            )
            attendance_results.append({
                "name":       sname,
                "marked":     ok,
                "message":    msg,
                "seen_count": len(sdata["timestamps"]),
                "seen_at":    sdata["timestamps"]
            })

        return jsonify({
            "success":        True,
            "video_duration": duration_sec,
            "frames_checked": processed_frames,
            "students_found": len(results_by_student),
            "results":        attendance_results
        })

    except Exception as e:
        return jsonify({"success": False,
                        "message": str(e)}), 500


@app.route("/teacher/today-count")
@role_required("teacher")
def teacher_today_count():
    dept_id = request.args.get(
        "dept_id", session.get("dept_id")
    )
    today   = date.today().strftime("%Y-%m-%d")
    records = get_attendance_by_dept(int(dept_id), today)
    return jsonify({"success": True, "count": len(records)})


@app.route("/teacher/today-records")
@role_required("teacher")
def teacher_today_records():
    dept_id = request.args.get(
        "dept_id", session.get("dept_id")
    )
    today   = date.today().strftime("%Y-%m-%d")
    records = get_attendance_by_dept(int(dept_id), today)
    return jsonify({"success": True, "records": records})

@app.route("/teacher/photo-attendance")
@role_required("teacher")
def teacher_photo_attendance():
    user    = get_user_by_id(session["user_id"])
    dept_id = user["dept_id"]
    today   = date.today().strftime("%Y-%m-%d")
    today_records = get_attendance_by_dept(dept_id, today)
    all_records   = get_attendance_by_dept(dept_id)
    return render_template("teacher/photo_attendance.html",
        user          = user,
        today_records = today_records,
        all_records   = all_records,
        today_count   = len(today_records)
    )


@app.route("/teacher/records")
@role_required("teacher")
def teacher_records():
    user    = get_user_by_id(session["user_id"])
    records = get_attendance_by_dept(user["dept_id"])
    return render_template("teacher/records.html",
        user    = user,
        records = records
    )


@app.route("/teacher/delete-record/<int:record_id>",
           methods=["POST"])
@role_required("teacher")
def teacher_delete_record(record_id):
    delete_attendance_record(record_id)
    return redirect(url_for("teacher_records"))


@app.route("/teacher/export")
@role_required("teacher")
def teacher_export():
    """
    Export attendance as a pivot CSV.
    Rows    = students (fixed)
    Columns = dates (grows as new dates added)
    Values  = Present / Absent
    Auto-updates every time downloaded.
    """
    user    = get_user_by_id(session["user_id"])
    dept_id = user["dept_id"]

    from database import get_attendance_pivot
    pivot = get_attendance_pivot(dept_id)

    students = pivot["students"]
    dates    = pivot["dates"]
    data     = pivot["data"]

    output = io.StringIO()
    writer = csv.writer(output)

    # ── Header row ────────────────────────────
    # Fixed columns: Sl No, Student ID, Student Name
    # Then one column per date
    header = ["Sl No", "Student ID", "Student Name"] + dates
    writer.writerow(header)

    # ── One row per student ───────────────────
    for idx, student in enumerate(students, start=1):
        sid  = student["id"]
        name = student["name"]
        row  = [idx, sid, name]

        # Add Present/Absent for each date
        for d in dates:
            row.append(data[sid].get(d, "Absent"))

        writer.writerow(row)

    # ── Summary row ───────────────────────────
    if students and dates:
        writer.writerow([])  # blank row

        # Count presents per date
        summary = ["", "", "Total Present"]
        for d in dates:
            count = sum(
                1 for s in students
                if data[s["id"]].get(d) == "Present"
            )
            summary.append(count)
        writer.writerow(summary)

        # Count absents per date
        absent_row = ["", "", "Total Absent"]
        for d in dates:
            count = sum(
                1 for s in students
                if data[s["id"]].get(d) == "Absent"
            )
            absent_row.append(count)
        writer.writerow(absent_row)

        # Attendance percentage per date
        pct_row = ["", "", "Attendance %"]
        for d in dates:
            present = sum(
                1 for s in students
                if data[s["id"]].get(d) == "Present"
            )
            total = len(students)
            pct   = round(
                (present / total * 100), 1
            ) if total > 0 else 0
            pct_row.append(f"{pct}%")
        writer.writerow(pct_row)

    output.seek(0)
    byte_out = io.BytesIO()
    byte_out.write(output.getvalue().encode("utf-8"))
    byte_out.seek(0)

    filename = (
        f"attendance_"
        f"{user['dept_name'].replace(' ', '_')}_"
        f"{date.today()}.csv"
    )

    return send_file(
        byte_out,
        mimetype  = "text/csv",
        as_attachment = True,
        download_name = filename
    )


# ══════════════════════════════════════════════
#  STUDENT ROUTES
# ══════════════════════════════════════════════

@app.route("/student/dashboard")
@role_required("student")
def student_dashboard():
    user = get_user_by_id(session["user_id"])

    if not user:
        session.clear()
        return redirect(url_for("login_page"))

    records = get_student_attendance(user["id"])

    # ADD THIS LINE
    stats = get_student_attendance_stats(user["id"])

    # If no attendance exists
    if stats is None:
        stats = {
            "present": 0,
            "absent": 0,
            "total": 0,
            "percentage": 0
        }

    # Compute ring offset for SVG
    pct = stats["percentage"]
    ring_offset = round(314 - (314 * pct / 100), 2)

    # Check face registered
    face_registered = get_face_data(user["id"]) is not None

    return render_template("student/dashboard.html",
        user            = user,
        stats           = stats,
        ring_offset     = ring_offset,
        recent_records  = records[:10],
        face_registered = face_registered,
        unread_count    = get_unread_count(user["id"])
    )

@app.route("/student/attendance")
@role_required("student")
def student_attendance():
    user    = get_user_by_id(session["user_id"])
    records = get_student_attendance(user["id"])
    stats   = get_student_attendance_stats(user["id"])

    return render_template("student/attendance.html",
        user    = user,
        records = records,
        stats   = stats
    )


@app.route("/student/profile")
@role_required("student")
def student_profile():
    user            = get_user_by_id(session["user_id"])
    stats           = get_student_attendance_stats(user["id"])
    face_registered = get_face_data(user["id"]) is not None

    return render_template("student/profile.html",
        user            = user,
        stats           = stats,
        face_registered = face_registered
    )


# ══════════════════════════════════════════════
#  TEACHER — GROUP PHOTO + MULTI PHOTO ATTENDANCE
# ══════════════════════════════════════════════

@app.route("/teacher/group-photo", methods=["POST"])
@role_required("teacher")
def teacher_group_photo():
    """
    Teacher uploads ONE group photo of the whole class.
    System finds ALL faces in the image and marks attendance
    for recognized students in teacher's department.
    """
    try:
        dept_id = int(session.get("dept_id"))

        if "photo" not in request.files:
            return jsonify({
                "success": False,
                "message": "No photo received."
            })

        file = request.files["photo"]
        if file.filename == "":
            return jsonify({
                "success": False,
                "message": "No file selected."
            })

        # Read image
        image_bytes = file.read()
        pil_image   = Image.open(
            io.BytesIO(image_bytes)
        ).convert("RGB")
        np_image    = np.array(pil_image)

        # Load ALL encodings for this dept
        dept_encodings, dept_names, dept_ids = \
            load_dept_encodings(dept_id)

        if not dept_encodings:
            return jsonify({
                "success": False,
                "message": "No registered faces in your "
                           "department. Ask students to "
                           "register their faces first."
            })

        # Find ALL faces in the group photo
        face_locations      = face_recognition.face_locations(
            np_image, model="hog"
        )
        face_encodings_list = face_recognition.face_encodings(
            np_image, face_locations
        )

        if not face_encodings_list:
            return jsonify({
                "success": False,
                "message": "No faces detected in the photo. "
                           "Please use a clearer image."
            })

        results      = []
        marked_count = 0

        for face_enc in face_encodings_list:
            matches   = face_recognition.compare_faces(
                dept_encodings, face_enc, tolerance=0.5
            )
            distances = face_recognition.face_distance(
                dept_encodings, face_enc
            )

            name       = "Unknown"
            student_id = None

            if len(distances) > 0:
                best = int(np.argmin(distances))
                if matches[best]:
                    name       = dept_names[best]
                    student_id = dept_ids[best]

            if name != "Unknown" and student_id:
                ok, msg = mark_attendance(
                    student_id, dept_id, session["user_id"]
                )
                if ok:
                    marked_count += 1
                results.append({
                    "name":    name,
                    "marked":  ok,
                    "message": msg
                })
            else:
                results.append({
                    "name":    "Unknown",
                    "marked":  False,
                    "message": "Face not recognized in dept."
                })

        return jsonify({
            "success":       True,
            "total_faces":   len(face_encodings_list),
            "marked_count":  marked_count,
            "results":       results
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error: {str(e)}"
        }), 500


@app.route("/teacher/multi-photo", methods=["POST"])
@role_required("teacher")
def teacher_multi_photo():
    """
    Teacher uploads multiple individual photos.
    Each photo is processed separately.
    One student per photo expected.
    """
    try:
        dept_id = int(session.get("dept_id"))

        if "photos" not in request.files:
            return jsonify({
                "success": False,
                "message": "No photos received."
            })

        files = request.files.getlist("photos")

        if not files:
            return jsonify({
                "success": False,
                "message": "No files selected."
            })

        # Load ALL encodings for this dept
        dept_encodings, dept_names, dept_ids = \
            load_dept_encodings(dept_id)

        if not dept_encodings:
            return jsonify({
                "success": False,
                "message": "No registered faces in your department."
            })

        results      = []
        marked_count = 0

        for file in files:
            if file.filename == "":
                continue
            try:
                image_bytes = file.read()
                pil_image   = Image.open(
                    io.BytesIO(image_bytes)
                ).convert("RGB")
                np_image    = np.array(pil_image)

                face_locs  = face_recognition.face_locations(np_image)
                face_encs  = face_recognition.face_encodings(
                    np_image, face_locs
                )

                if not face_encs:
                    results.append({
                        "file":    file.filename,
                        "name":    "No face",
                        "marked":  False,
                        "message": "No face detected in photo."
                    })
                    continue

                # Use first face found
                face_enc  = face_encs[0]
                matches   = face_recognition.compare_faces(
                    dept_encodings, face_enc, tolerance=0.5
                )
                distances = face_recognition.face_distance(
                    dept_encodings, face_enc
                )

                name       = "Unknown"
                student_id = None

                if len(distances) > 0:
                    best = int(np.argmin(distances))
                    if matches[best]:
                        name       = dept_names[best]
                        student_id = dept_ids[best]

                if name != "Unknown" and student_id:
                    ok, msg = mark_attendance(
                        student_id, dept_id, session["user_id"]
                    )
                    if ok:
                        marked_count += 1
                    results.append({
                        "file":    file.filename,
                        "name":    name,
                        "marked":  ok,
                        "message": msg
                    })
                else:
                    results.append({
                        "file":    file.filename,
                        "name":    "Unknown",
                        "marked":  False,
                        "message": "Face not recognized."
                    })

            except Exception:
                results.append({
                    "file":    file.filename,
                    "name":    "Error",
                    "marked":  False,
                    "message": "Could not process this image."
                })

        return jsonify({
            "success":      True,
            "total_photos": len(files),
            "marked_count": marked_count,
            "results":      results
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# ── Student face registration ──────────────────────────────

@app.route("/register-face", methods=["GET", "POST"])
@login_required
def register_face():
    """
    Student uploads up to 10 photos.
    System extracts face encodings from ALL photos
    and saves them all — better accuracy.
    """
    user               = get_user_by_id(session["user_id"])
    already_registered = get_face_data(user["id"]) is not None

    if request.method == "GET":
        return render_template("register_face.html",
            user               = user,
            already_registered = already_registered
        )

    # ── POST — handle uploaded photos ─────────────
    if "photos" not in request.files:
        return jsonify({
            "success": False,
            "message": "No photos received."
        })

    files = request.files.getlist("photos")

    if not files or len(files) == 0:
        return jsonify({
            "success": False,
            "message": "Please select at least one photo."
        })

    if len(files) > 10:
        return jsonify({
            "success": False,
            "message": "Maximum 10 photos allowed."
        })

    all_encodings = []   # collect encodings from ALL photos
    processed     = 0
    faces_found   = 0
    failed_files  = []

    for file in files:
        if file.filename == "":
            continue
        try:
            image_bytes = file.read()
            pil_image   = Image.open(
                io.BytesIO(image_bytes)
            ).convert("RGB")
            np_image    = np.array(pil_image)

            # Find ALL faces in this photo
            face_locations  = face_recognition.face_locations(
                np_image, model="hog"
            )
            encodings = face_recognition.face_encodings(
                np_image, face_locations
            )

            processed += 1

            if encodings:
                # Take the first (largest) face in each photo
                all_encodings.append(encodings[0])
                faces_found += 1
                print(f"  ✓ Face found in {file.filename}")
            else:
                failed_files.append(file.filename)
                print(f"  ✗ No face in {file.filename}")

        except Exception as e:
            failed_files.append(file.filename)
            print(f"  ✗ Error processing {file.filename}: {e}")
            continue

    if not all_encodings:
        return jsonify({
            "success": False,
            "message": f"No face detected in any of the "
                       f"{processed} photos. Please use clear "
                       f"well-lit photos where your face is "
                       f"clearly visible."
        })

    # ── Save ALL encodings to one file ────────────
    enc_dir  = "face_encodings_data"
    os.makedirs(enc_dir, exist_ok=True)
    enc_path = os.path.join(
        enc_dir, f"user_{user['id']}.pkl"
    )

    # Save as a LIST of encodings (not just one)
    with open(enc_path, "wb") as f:
        pickle.dump(all_encodings, f)

    save_face_data(user["id"], enc_path)

    print(f"\n✓ Saved {len(all_encodings)} encodings "
          f"for {user['full_name']} → {enc_path}")

    action  = "updated" if already_registered else "registered"
    message = (
        f"Face {action} successfully! "
        f"{faces_found} of {processed} photos "
        f"had a detected face. "
        f"More photos = better accuracy."
    )

    if failed_files:
        message += (
            f" ({len(failed_files)} photo(s) skipped "
            f"— no face found in them.)"
        )

    return jsonify({
        "success":     True,
        "message":     message,
        "faces_found": faces_found,
        "processed":   processed,
        "encodings_saved": len(all_encodings)
    })


# ══════════════════════════════════════════════
#  CHAT ROUTES
# ══════════════════════════════════════════════

@app.route("/chat")
@login_required
def chat_page():
    """Main chat page — group + private."""
    user     = get_user_by_id(session["user_id"])
    if not user:
        session.clear()
        return redirect(url_for("login_page"))

    dept_id  = user["dept_id"]
    contacts = get_chat_contacts(
        user["id"], dept_id, user["role"]
    )
    group_messages  = get_group_messages(dept_id)
    unread_count    = get_unread_count(user["id"])

    return render_template("chat.html",
        user           = user,
        contacts       = contacts,
        group_messages = group_messages,
        unread_count   = unread_count
    )


@app.route("/chat/private/<int:other_id>")
@login_required
def private_chat(other_id):
    """Load private messages between current user and other."""
    user     = get_user_by_id(session["user_id"])
    if not user:
        session.clear()
        return redirect(url_for("login_page"))

    other    = get_user_by_id(other_id)
    if not other:
        return redirect(url_for("chat_page"))

    # Mark messages as read
    mark_messages_read(other_id, user["id"])

    messages = get_private_messages(user["id"], other_id)
    contacts = get_chat_contacts(
        user["id"], user["dept_id"], user["role"]
    )
    unread_count = get_unread_count(user["id"])

    return render_template("chat.html",
        user           = user,
        contacts       = contacts,
        group_messages = get_group_messages(user["dept_id"]),
        unread_count   = unread_count,
        private_messages = messages,
        chat_with      = other,
        active_tab     = "private"
    )


@app.route("/chat/unread")
@login_required
def chat_unread():
    """Return unread message count as JSON."""
    user = get_user_by_id(session["user_id"])
    if not user:
        return jsonify({"count": 0})
    count = get_unread_count(user["id"])
    return jsonify({"count": count})


# ══════════════════════════════════════════════
#  SOCKET.IO EVENTS
# ══════════════════════════════════════════════

@socketio.on("connect")
def on_connect():
    """Client connected."""
    if "user_id" in session:
        user_id = session["user_id"]
        dept_id = session.get("dept_id")
        # Join department group room
        if dept_id:
            join_room(f"dept_{dept_id}")
        # Join personal room for private messages
        join_room(f"user_{user_id}")
        print(f"User {user_id} connected to chat")


@socketio.on("disconnect")
def on_disconnect():
    """Client disconnected."""
    if "user_id" in session:
        user_id = session["user_id"]
        dept_id = session.get("dept_id")
        if dept_id:
            leave_room(f"dept_{dept_id}")
        leave_room(f"user_{user_id}")


@socketio.on("send_group_message")
def handle_group_message(data):
    """
    Teacher or student sends a group message.
    Broadcasts to everyone in the department.
    """
    if "user_id" not in session:
        return

    user_id = session["user_id"]
    dept_id = session.get("dept_id")
    message = data.get("message", "").strip()

    if not message or not dept_id:
        return

    # Limit message length
    if len(message) > 1000:
        message = message[:1000]

    # Save to database
    saved = save_group_message(dept_id, user_id, message)

    if saved:
        # Broadcast to all users in this department
        emit("new_group_message", saved,
             room=f"dept_{dept_id}")


@socketio.on("send_private_message")
def handle_private_message(data):
    """
    Send a private message to one person.
    Only sender and receiver see it.
    """
    if "user_id" not in session:
        return

    sender_id   = session["user_id"]
    receiver_id = data.get("receiver_id")
    message     = data.get("message", "").strip()

    if not message or not receiver_id:
        return

    if len(message) > 1000:
        message = message[:1000]

    # Save to database
    saved = save_private_message(
        sender_id, receiver_id, message
    )

    if saved:
        # Send to receiver's personal room
        emit("new_private_message", saved,
             room=f"user_{receiver_id}")
        # Send back to sender too
        emit("new_private_message", saved,
             room=f"user_{sender_id}")


@socketio.on("typing")
def handle_typing(data):
    """Broadcast typing indicator."""
    if "user_id" not in session:
        return
    user     = get_user_by_id(session["user_id"])
    if not user:
        return
    room     = data.get("room")
    is_typing = data.get("is_typing", False)
    if room:
        emit("user_typing", {
            "user_id":     user["id"],
            "name":        user["full_name"],
            "is_typing":   is_typing
        }, room=room, include_self=False)


# ══════════════════════════════════════════════
#  START SERVER
# ══════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*50)
    print("   SMART ATTENDANCE SYSTEM — STARTING")
    print("="*50)
    init_db()
    print("✓ Server running at: http://127.0.0.1:5000")
    print("✓ Chat at:           http://127.0.0.1:5000/chat")
    print("Press Ctrl+C to stop.\n")
    socketio.run(
        app,
        debug=True,
        host="0.0.0.0",
        port=5000,
        allow_unsafe_werkzeug=True
    )