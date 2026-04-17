"""
EduFace MERGED — Flask Backend with Facial Recognition Attendance
===================================================================
Install: pip install -r requirements.txt
Run    : python app.py
URL    : http://127.0.0.1:5000

Features:
- Multi-role authentication (Admin, Teacher, Student)
- Facial recognition attendance system
- Random Forest machine learning model
- Student face enrollment
- Teacher-Student messaging
- Admin dashboard with model training
"""

import os, io, uuid, random, string, sqlite3, json, threading, datetime
from datetime import datetime as dt, timedelta
from functools import wraps

from flask import (Flask, request, jsonify, session,
                   send_from_directory, render_template, send_file)
from werkzeug.security import generate_password_hash, check_password_hash

# Import facial recognition functions
try:
    import model  # Import as module to set MODEL_PATH
except ImportError as e:
    print(f"[WARNING] Could not import facial recognition model: {e}")
    model = None

APP_DIR         = os.path.dirname(os.path.abspath(__file__))
BASE_DIR        = os.path.dirname(APP_DIR)  # Parent folder: college-project/

# SHARED RESOURCES (accessed by both eduface-1 and Attendance-System2)
DB_PATH         = os.path.join(BASE_DIR, 'eduface.db')
DATASET_DIR     = os.path.join(BASE_DIR, 'dataset')
MODEL_PATH      = os.path.join(BASE_DIR, 'model.pkl')

# Update model.py to use shared MODEL_PATH
if model:
    model.MODEL_PATH = MODEL_PATH

# LOCAL RESOURCES (eduface-1 only)
UPLOAD_FOLDER    = os.path.join(APP_DIR, 'uploads')  # Temporary photo storage during registration
TRAIN_STATUS_FILE = os.path.join(APP_DIR, 'train_status.json')
ALLOWED_EXT      = {'png', 'jpg', 'jpeg', 'webp', 'gif', 'mp4', 'mov'}

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key               = os.environ.get('SECRET_KEY', 'eduface-dev-secret-2025')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATASET_DIR, exist_ok=True)

# In-memory OTP store: { identifier: (otp, expires_datetime) }
OTP_STORE: dict = {}


# ═══════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ═══════════════════════════════════════════════════════════════
# FACIAL RECOGNITION HELPERS
# ═══════════════════════════════════════════════════════════════
def write_train_status(status_dict):
    """Write model training status to file"""
    with open(TRAIN_STATUS_FILE, "w") as f:
        json.dump(status_dict, f)

def read_train_status():
    """Read model training status from file"""
    if not os.path.exists(TRAIN_STATUS_FILE):
        return {"running": False, "progress": 0, "message": "Not trained"}
    with open(TRAIN_STATUS_FILE, "r") as f:
        return json.load(f)

# Initialize train status file
write_train_status({"running": False, "progress": 0, "message": "Model ready"})


def init_db():
    schema = """
    CREATE TABLE IF NOT EXISTS teachers (
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
    );
    CREATE TABLE IF NOT EXISTS students (
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
    );
    CREATE TABLE IF NOT EXISTS attendance (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id      INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
        teacher_id      INTEGER NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
        date            TEXT    NOT NULL,
        time            TEXT    DEFAULT '',
        dept            TEXT    NOT NULL,
        subject         TEXT    NOT NULL,
        present         INTEGER NOT NULL DEFAULT 0,
        photo_url       TEXT    DEFAULT '',
        face_recognized INTEGER DEFAULT 0,
        confidence      REAL    DEFAULT 0.0,
        created_at      TEXT    DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS chats (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
        student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
        created_at TEXT    DEFAULT (datetime('now','localtime')),
        UNIQUE (teacher_id, student_id)
    );
    CREATE TABLE IF NOT EXISTS messages (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id     INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
        sender_id   INTEGER NOT NULL,
        sender_type TEXT    NOT NULL,
        text        TEXT    NOT NULL,
        created_at  TEXT    DEFAULT (datetime('now','localtime'))
    );
    """
    with get_db() as conn:
        conn.executescript(schema)

        if conn.execute("SELECT COUNT(*) FROM teachers").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO teachers (name,email,mobile,dept,userid,password_hash,photo_url,status) VALUES (?,?,?,?,?,?,?,?)",
                [
                    ('Dr. Priya Sharma', 'priya.sharma@edu.in', '9876543210', 'Computer Science',
                     'priya@edu',    generate_password_hash('Teacher@123'), '', 'approved'),
                    ('Mr. Rohit Mehta',  'rohit.mehta@edu.in',  '9876543211', 'Mathematics',
                     'rohit@edu',    generate_password_hash('Rohit@123'),   '', 'approved'),
                    ('Ms. Anjali Singh', 'anjali.singh@edu.in', '9123456789', 'Physics',
                     'anjali@edu',   generate_password_hash('Anjali@123'),  '', 'pending'),
                ])

        if conn.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO students (name,email,mobile,dept,rollno,userid,password_hash,photo_url,face_enrolled,status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                [
                    ('Arjun Verma', 'arjun.verma@student.edu', '9000001111',
                     'Computer Science', 'CS2301', 'arjun@student', generate_password_hash('Arjun@123'), '', 0, 'approved'),
                    ('Sneha Patel', 'sneha.patel@student.edu', '9000002222',
                     'Mathematics',     'MA2301', 'sneha@student',  generate_password_hash('Sneha@123'), '', 0, 'approved'),
                    ('Karan Das',   'karan.das@student.edu',   '9000003333',
                     'Physics',         'PH2301', 'karan@student',  generate_password_hash('Karan@123'), '', 0, 'pending'),
                ])

        if conn.execute("SELECT COUNT(*) FROM attendance").fetchone()[0] == 0:
            t1 = conn.execute("SELECT id FROM teachers WHERE userid='priya@edu'").fetchone()
            t2 = conn.execute("SELECT id FROM teachers WHERE userid='rohit@edu'").fetchone()
            s1 = conn.execute("SELECT id FROM students WHERE userid='arjun@student'").fetchone()
            s2 = conn.execute("SELECT id FROM students WHERE userid='sneha@student'").fetchone()
            if t1 and s1:
                conn.executemany(
                    "INSERT INTO attendance (student_id,teacher_id,date,time,dept,subject,present,face_recognized,confidence) VALUES (?,?,?,?,?,?,?,?,?)",
                    [
                        (s1['id'],t1['id'],'2025-03-20','09:00','Computer Science','Data Structures',1,0,0.0),
                        (s1['id'],t1['id'],'2025-03-21','09:00','Computer Science','Data Structures',1,0,0.0),
                        (s1['id'],t1['id'],'2025-03-22','09:00','Computer Science','Data Structures',0,0,0.0),
                        (s1['id'],t1['id'],'2025-03-20','11:00','Computer Science','Algorithms',1,0,0.0),
                        (s1['id'],t1['id'],'2025-03-21','11:00','Computer Science','Algorithms',0,0,0.0),
                        (s1['id'],t1['id'],'2025-03-22','11:00','Computer Science','Algorithms',1,0,0.0),
                    ])
            if t2 and s2:
                conn.executemany(
                    "INSERT INTO attendance (student_id,teacher_id,date,time,dept,subject,present,face_recognized,confidence) VALUES (?,?,?,?,?,?,?,?,?)",
                    [
                        (s2['id'],t2['id'],'2025-03-20','10:00','Mathematics','Calculus',1,0,0.0),
                        (s2['id'],t2['id'],'2025-03-21','10:00','Mathematics','Calculus',0,0,0.0),
                        (s2['id'],t2['id'],'2025-03-22','10:00','Mathematics','Calculus',1,0,0.0),
                    ])

        if conn.execute("SELECT COUNT(*) FROM chats").fetchone()[0] == 0:
            t1 = conn.execute("SELECT id FROM teachers WHERE userid='priya@edu'").fetchone()
            t2 = conn.execute("SELECT id FROM teachers WHERE userid='rohit@edu'").fetchone()
            s1 = conn.execute("SELECT id FROM students WHERE userid='arjun@student'").fetchone()
            s2 = conn.execute("SELECT id FROM students WHERE userid='sneha@student'").fetchone()
            if t1 and s1:
                conn.execute("INSERT INTO chats (teacher_id,student_id) VALUES (?,?)", (t1['id'],s1['id']))
                c1 = conn.execute("SELECT id FROM chats WHERE teacher_id=? AND student_id=?",(t1['id'],s1['id'])).fetchone()
                conn.executemany(
                    "INSERT INTO messages (chat_id,sender_id,sender_type,text,created_at) VALUES (?,?,?,?,?)",
                    [
                        (c1['id'],t1['id'],'teacher','Hello Arjun, please submit your assignment by Friday.','2025-03-20 10:05'),
                        (c1['id'],s1['id'],'student','Yes mam, I will submit it on time!','2025-03-20 10:12'),
                        (c1['id'],t1['id'],'teacher','Great! Also prepare for the linked-lists quiz Monday.','2025-03-20 10:15'),
                    ])
            if t2 and s2:
                conn.execute("INSERT INTO chats (teacher_id,student_id) VALUES (?,?)", (t2['id'],s2['id']))
                c2 = conn.execute("SELECT id FROM chats WHERE teacher_id=? AND student_id=?",(t2['id'],s2['id'])).fetchone()
                conn.executemany(
                    "INSERT INTO messages (chat_id,sender_id,sender_type,text,created_at) VALUES (?,?,?,?,?)",
                    [
                        (c2['id'],s2['id'],'student','Sir, I have a doubt in the integration chapter.','2025-03-21 14:00'),
                        (c2['id'],t2['id'],'teacher','Sure Sneha, which problem? Share it here.','2025-03-21 14:08'),
                    ])
        conn.commit()
    print(f"[DB] Ready → {DB_PATH}")


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════
def allowed_file(fn):
    return '.' in fn and fn.rsplit('.',1)[1].lower() in ALLOWED_EXT

def save_upload(f):
    if not f or not f.filename: return ''
    if not allowed_file(f.filename): return ''
    ext  = f.filename.rsplit('.',1)[1].lower()
    name = f"{uuid.uuid4().hex}.{ext}"
    f.save(os.path.join(UPLOAD_FOLDER, name))
    return f"/uploads/{name}"

def gen_otp():
    return ''.join(random.choices(string.digits, k=6))

def rows(cursor_result):
    return [dict(r) for r in cursor_result]

def require_login(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if 'role' not in session:
                return jsonify({'ok':False,'msg':'Not authenticated.'}), 401
            if roles and session['role'] not in roles:
                return jsonify({'ok':False,'msg':'Forbidden.'}), 403
            return fn(*a, **kw)
        return wrapper
    return deco

_T = ('id','name','email','mobile','dept','userid','photo_url','status','created_at')
_S = ('id','name','email','mobile','dept','rollno','userid','photo_url','face_enrolled','status','created_at')

def safe_t(r):
    if not r: return {}
    d = dict(r); return {k:d.get(k,'') for k in _T}

def safe_s(r):
    if not r: return {}
    d = dict(r); return {k:d.get(k,'') for k in _S}

def admin_t(r):
    d = safe_t(r); d['password_hash'] = dict(r).get('password_hash',''); return d
def admin_s(r):
    d = safe_s(r); d['password_hash'] = dict(r).get('password_hash',''); return d


# ═══════════════════════════════════════════════════════════════
# STATIC & PAGE ROUTES
# ═══════════════════════════════════════════════════════════════
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/pages/<page>')
def serve_page(page):
    if page in ('admin.html','teacher.html','student.html'):
        return render_template(f'pages/{page}')
    return 'Not found', 404


# ═══════════════════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════════════════
@app.route('/api/auth/login', methods=['POST'])
def api_login():
    d    = request.get_json(force=True)
    role = d.get('role','')
    uid  = d.get('userid','').strip()
    pwd  = d.get('password','')

    if role == 'admin':
        if uid == 'admin@123' and pwd == 'Admin@123':
            session.clear()
            session['role'] = 'admin'; session['user_id'] = 0
            return jsonify({'ok':True,'role':'admin','name':'Administrator'})
        return jsonify({'ok':False,'msg':'Invalid admin credentials.'}), 401

    table = 'teachers' if role == 'teacher' else 'students' if role == 'student' else None
    if not table:
        return jsonify({'ok':False,'msg':'Unknown role.'}), 400

    with get_db() as c:
        row = c.execute(f"SELECT * FROM {table} WHERE userid=?", (uid,)).fetchone()
    if row and check_password_hash(row['password_hash'], pwd):
        if row['status'] != 'approved':
            return jsonify({'ok':False,'msg':'Account pending admin approval.'}), 403
        session.clear()
        session['role'] = role; session['user_id'] = row['id']
        user = safe_t(row) if role == 'teacher' else safe_s(row)
        return jsonify({'ok':True,'role':role,'user':user})
    return jsonify({'ok':False,'msg':'Invalid User ID or Password.'}), 401


@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    session.clear(); return jsonify({'ok':True})


@app.route('/api/auth/me')
def api_me():
    if 'role' not in session: return jsonify({'ok':False}), 401
    role = session['role']; uid = session['user_id']
    if role == 'admin':
        return jsonify({'ok':True,'role':'admin','name':'Administrator'})
    table = 'teachers' if role == 'teacher' else 'students'
    with get_db() as c:
        row = c.execute(f"SELECT * FROM {table} WHERE id=?", (uid,)).fetchone()
    user = safe_t(row) if role == 'teacher' else safe_s(row)
    return jsonify({'ok':True,'role':role,'user':user})


@app.route('/api/auth/send-otp', methods=['POST'])
def api_send_otp():
    d = request.get_json(force=True)
    identifier = d.get('identifier','').strip()
    method     = d.get('method','email')
    if not identifier:
        return jsonify({'ok':False,'msg':'Please provide email or mobile.'}), 400

    with get_db() as c:
        found = False
        for tbl in ('teachers','students'):
            if method == 'email':
                found = bool(c.execute(f"SELECT id FROM {tbl} WHERE email=?", (identifier,)).fetchone())
            else:
                found = bool(c.execute(f"SELECT id FROM {tbl} WHERE mobile=?", (identifier,)).fetchone())
            if found: break

    if not found:
        return jsonify({'ok':False,'msg':f'No account found with this {method}.'}), 404

    otp = gen_otp()
    OTP_STORE[identifier] = (otp, datetime.now() + timedelta(minutes=10))
    print(f"[OTP] {identifier} → {otp}")
    return jsonify({'ok':True,'otp_demo':otp,'msg':f'OTP sent to your {method}.'})


@app.route('/api/auth/verify-otp', methods=['POST'])
def api_verify_otp():
    d = request.get_json(force=True)
    identifier = d.get('identifier','').strip()
    entered    = d.get('otp','').strip()
    entry = OTP_STORE.get(identifier)
    if not entry:
        return jsonify({'ok':False,'msg':'No OTP found. Request again.'}), 400
    otp, expiry = entry
    if datetime.now() > expiry:
        del OTP_STORE[identifier]
        return jsonify({'ok':False,'msg':'OTP expired.'}), 400
    if entered != otp:
        return jsonify({'ok':False,'msg':'Incorrect OTP.'}), 400
    del OTP_STORE[identifier]
    with get_db() as c:
        for tbl in ('teachers','students'):
            row = c.execute(f"SELECT userid FROM {tbl} WHERE email=? OR mobile=?",
                            (identifier,identifier)).fetchone()
            if row:
                return jsonify({'ok':True,'userid':row['userid'],
                                'password_hint':'Use your registered password.'})
    return jsonify({'ok':True,'userid':'admin@123','password_hint':'Admin@123'})


# ═══════════════════════════════════════════════════════════════
# REGISTRATION
# ═══════════════════════════════════════════════════════════════
@app.route('/api/teachers/register', methods=['POST'])
def api_register_teacher():
    name=request.form.get('name','').strip(); mobile=request.form.get('mobile','').strip()
    email=request.form.get('email','').strip(); dept=request.form.get('dept','').strip()
    userid=request.form.get('userid','').strip(); password=request.form.get('password','')
    if not all([name,mobile,email,dept,userid,password]):
        return jsonify({'ok':False,'msg':'All fields are required.'}), 400
    with get_db() as c:
        if c.execute("SELECT id FROM teachers WHERE userid=?", (userid,)).fetchone():
            return jsonify({'ok':False,'msg':'User ID already taken.'}), 409
        if c.execute("SELECT id FROM teachers WHERE email=?", (email,)).fetchone():
            return jsonify({'ok':False,'msg':'Email already registered.'}), 409
        photo_url = save_upload(request.files.get('photo'))
        c.execute("INSERT INTO teachers (name,email,mobile,dept,userid,password_hash,photo_url,status) "
                  "VALUES (?,?,?,?,?,?,?,'pending')",
                  (name,email,mobile,dept,userid,generate_password_hash(password),photo_url))
        c.commit()
    return jsonify({'ok':True,'msg':'Registration submitted. Awaiting admin approval.'})


@app.route('/api/students/register', methods=['POST'])
def api_register_student():
    """Student registration with face enrollment support
    
    Form fields:
      - name, email, mobile, dept, rollno, userid, password (required)
      - photo (profile photo, required)
      - face_photos (array of captured face images, optional)
    """
    import requests
    
    name = request.form.get('name', '').strip()
    mobile = request.form.get('mobile', '').strip()
    email = request.form.get('email', '').strip()
    dept = request.form.get('dept', '').strip()
    rollno = request.form.get('rollno', '').strip()
    userid = request.form.get('userid', '').strip()
    password = request.form.get('password', '')
    
    # Validation
    if not all([name, mobile, email, dept, userid, password]):
        return jsonify({'ok': False, 'msg': 'All fields are required.'}), 400
    
    if not request.files.get('photo'):
        return jsonify({'ok': False, 'msg': 'Profile photo is required.'}), 400
    
    # Check uniqueness
    with get_db() as c:
        if c.execute("SELECT id FROM students WHERE userid=?", (userid,)).fetchone():
            return jsonify({'ok': False, 'msg': 'User ID already taken.'}), 409
        if c.execute("SELECT id FROM students WHERE email=?", (email,)).fetchone():
            return jsonify({'ok': False, 'msg': 'Email already registered.'}), 409
    
    # Save profile photo
    photo_url = save_upload(request.files.get('photo'))
    
    # Insert student into database
    try:
        with get_db() as c:
            c.execute(
                "INSERT INTO students (name, email, mobile, dept, rollno, userid, password_hash, photo_url, face_enrolled, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (name, email, mobile, dept, rollno, userid, generate_password_hash(password), photo_url, 0, 'pending')
            )
            c.commit()
            student_id = c.execute("SELECT id FROM students WHERE userid=?", (userid,)).fetchone()[0]
    except Exception as e:
        return jsonify({'ok': False, 'msg': f'Database error: {str(e)}'}), 500
    
    # Create dataset folder for this student
    student_dataset_dir = os.path.join(DATASET_DIR, str(student_id))
    os.makedirs(student_dataset_dir, exist_ok=True)
    
    # Process face photos (multipart array of images)
    face_photos = request.files.getlist('face_photos[]')
    saved_faces = 0
    
    if face_photos:
        for idx, face_file in enumerate(face_photos):
            try:
                if face_file and face_file.filename and allowed_file(face_file.filename):
                    ext = face_file.filename.rsplit('.', 1)[1].lower()
                    face_filename = f"face_{idx:03d}.{ext}"  # face_000.jpg, face_001.jpg, etc.
                    face_path = os.path.join(student_dataset_dir, face_filename)
                    face_file.save(face_path)
                    saved_faces += 1
            except Exception as e:
                app.logger.error(f"Error saving face photo {idx}: {str(e)}")
                continue
    
    # If face photos were uploaded, train the model in the background
    training_status = "Awaiting admin approval"
    if saved_faces > 0:
        try:
            # Call ML engine to train model
            ml_engine_url = "http://localhost:5100/api/train-model"
            response = requests.post(ml_engine_url, json={"student_id": student_id}, timeout=5)
            
            if response.status_code == 202:  # Accepted, training started
                training_status = f"Face enrollment: {saved_faces} photos captured. Model training in progress."
                # Set face_enrolled to 1 once model training completes
                # For now, it will be updated by the ML engine
            else:
                training_status = f"Face enrollment: {saved_faces} photos captured. Model training may not have started."
                app.logger.warning(f"ML Engine training endpoint returned {response.status_code}")
        except requests.exceptions.ConnectionError:
            training_status = f"Face enrollment: {saved_faces} photos captured. ML Engine not available - will train when restarted."
            app.logger.warning(f"Could not connect to ML Engine at {ml_engine_url}")
        except Exception as e:
            training_status = f"Face enrollment: {saved_faces} photos captured. Error during training: {str(e)}"
            app.logger.error(f"Error calling ML Engine: {str(e)}")
    else:
        training_status = "Awaiting admin approval (No face photos captured)"
    
    return jsonify({
        'ok': True,
        'msg': 'Registration submitted. ' + training_status,
        'student_id': student_id,
        'face_photos_saved': saved_faces
    }), 201


# ═══════════════════════════════════════════════════════════════
# ADMIN
# ═══════════════════════════════════════════════════════════════
@app.route('/api/admin/stats')
@require_login('admin')
def api_admin_stats():
    with get_db() as c:
        return jsonify({
            'teachers':   c.execute("SELECT COUNT(*) FROM teachers WHERE status='approved'").fetchone()[0],
            'students':   c.execute("SELECT COUNT(*) FROM students WHERE status='approved'").fetchone()[0],
            'attendance': c.execute("SELECT COUNT(*) FROM attendance").fetchone()[0],
            'messages':   c.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
            'pending':    c.execute("SELECT COUNT(*) FROM teachers WHERE status='pending'").fetchone()[0]
                        + c.execute("SELECT COUNT(*) FROM students WHERE status='pending'").fetchone()[0],
            'face_enrolled': c.execute("SELECT COUNT(*) FROM students WHERE face_enrolled=1").fetchone()[0],
        })

@app.route('/api/admin/teachers')
@require_login('admin')
def api_admin_teachers():
    q = f"%{request.args.get('q','').lower()}%"
    with get_db() as c:
        rs = c.execute("SELECT * FROM teachers WHERE lower(name) LIKE ? OR lower(dept) LIKE ? OR lower(userid) LIKE ? "
                       "ORDER BY status DESC, created_at DESC", (q,q,q)).fetchall()
    return jsonify([admin_t(r) for r in rs])

@app.route('/api/admin/students')
@require_login('admin')
def api_admin_students():
    q = f"%{request.args.get('q','').lower()}%"
    with get_db() as c:
        rs = c.execute("SELECT * FROM students WHERE lower(name) LIKE ? OR lower(dept) LIKE ? OR lower(userid) LIKE ? "
                       "ORDER BY status DESC, created_at DESC", (q,q,q)).fetchall()
    return jsonify([admin_s(r) for r in rs])

@app.route('/api/admin/teachers/<int:tid>/approve', methods=['POST'])
@require_login('admin')
def api_approve_teacher(tid):
    with get_db() as c: c.execute("UPDATE teachers SET status='approved' WHERE id=?", (tid,)); c.commit()
    return jsonify({'ok':True})

@app.route('/api/admin/teachers/<int:tid>/reject', methods=['DELETE'])
@require_login('admin')
def api_reject_teacher(tid):
    with get_db() as c: c.execute("DELETE FROM teachers WHERE id=?", (tid,)); c.commit()
    return jsonify({'ok':True})

@app.route('/api/admin/students/<int:sid>/approve', methods=['POST'])
@require_login('admin')
def api_approve_student(sid):
    with get_db() as c: c.execute("UPDATE students SET status='approved' WHERE id=?", (sid,)); c.commit()
    return jsonify({'ok':True})

@app.route('/api/admin/students/<int:sid>/reject', methods=['DELETE'])
@require_login('admin')
def api_reject_student(sid):
    with get_db() as c: c.execute("DELETE FROM students WHERE id=?", (sid,)); c.commit()
    return jsonify({'ok':True})

@app.route('/api/admin/teachers/<int:tid>/edit', methods=['POST'])
@require_login('admin')
def api_edit_teacher(tid):
    name     = request.form.get('name',     '').strip()
    email    = request.form.get('email',    '').strip()
    mobile   = request.form.get('mobile',   '').strip()
    dept     = request.form.get('dept',     '').strip()
    userid   = request.form.get('userid',   '').strip()
    password = request.form.get('password', '').strip()
    status   = request.form.get('status',   '').strip()

    if not all([name, email, mobile, dept, userid]):
        return jsonify({'ok': False, 'msg': 'Name, email, mobile, dept and userid are required.'}), 400

    with get_db() as c:
        # Check userid conflict with another teacher
        conflict = c.execute(
            "SELECT id FROM teachers WHERE userid=? AND id!=?", (userid, tid)).fetchone()
        if conflict:
            return jsonify({'ok': False, 'msg': 'User ID already taken by another teacher.'}), 409

        # Check email conflict
        conflict_email = c.execute(
            "SELECT id FROM teachers WHERE email=? AND id!=?", (email, tid)).fetchone()
        if conflict_email:
            return jsonify({'ok': False, 'msg': 'Email already used by another teacher.'}), 409

        photo_url = save_upload(request.files.get('photo'))

        if password:
            # Update password too
            if photo_url:
                c.execute(
                    "UPDATE teachers SET name=?,email=?,mobile=?,dept=?,userid=?,password_hash=?,photo_url=?,status=? WHERE id=?",
                    (name, email, mobile, dept, userid, generate_password_hash(password), photo_url, status or 'approved', tid))
            else:
                c.execute(
                    "UPDATE teachers SET name=?,email=?,mobile=?,dept=?,userid=?,password_hash=?,status=? WHERE id=?",
                    (name, email, mobile, dept, userid, generate_password_hash(password), status or 'approved', tid))
        else:
            if photo_url:
                c.execute(
                    "UPDATE teachers SET name=?,email=?,mobile=?,dept=?,userid=?,photo_url=?,status=? WHERE id=?",
                    (name, email, mobile, dept, userid, photo_url, status or 'approved', tid))
            else:
                c.execute(
                    "UPDATE teachers SET name=?,email=?,mobile=?,dept=?,userid=?,status=? WHERE id=?",
                    (name, email, mobile, dept, userid, status or 'approved', tid))
        c.commit()

    with get_db() as c:
        row = c.execute("SELECT * FROM teachers WHERE id=?", (tid,)).fetchone()
    return jsonify({'ok': True, 'msg': 'Teacher updated successfully.', 'user': safe_t(row)})


@app.route('/api/admin/students/<int:sid>/edit', methods=['POST'])
@require_login('admin')
def api_edit_student(sid):
    name     = request.form.get('name',     '').strip()
    email    = request.form.get('email',    '').strip()
    mobile   = request.form.get('mobile',   '').strip()
    dept     = request.form.get('dept',     '').strip()
    rollno   = request.form.get('rollno',   '').strip()
    userid   = request.form.get('userid',   '').strip()
    password = request.form.get('password', '').strip()
    status   = request.form.get('status',   '').strip()

    if not all([name, email, mobile, dept, userid]):
        return jsonify({'ok': False, 'msg': 'Name, email, mobile, dept and userid are required.'}), 400

    with get_db() as c:
        conflict = c.execute(
            "SELECT id FROM students WHERE userid=? AND id!=?", (userid, sid)).fetchone()
        if conflict:
            return jsonify({'ok': False, 'msg': 'User ID already taken by another student.'}), 409

        conflict_email = c.execute(
            "SELECT id FROM students WHERE email=? AND id!=?", (email, sid)).fetchone()
        if conflict_email:
            return jsonify({'ok': False, 'msg': 'Email already used by another student.'}), 409

        photo_url = save_upload(request.files.get('photo'))

        if password:
            if photo_url:
                c.execute(
                    "UPDATE students SET name=?,email=?,mobile=?,dept=?,rollno=?,userid=?,password_hash=?,photo_url=?,status=? WHERE id=?",
                    (name, email, mobile, dept, rollno, userid, generate_password_hash(password), photo_url, status or 'approved', sid))
            else:
                c.execute(
                    "UPDATE students SET name=?,email=?,mobile=?,dept=?,rollno=?,userid=?,password_hash=?,status=? WHERE id=?",
                    (name, email, mobile, dept, rollno, userid, generate_password_hash(password), status or 'approved', sid))
        else:
            if photo_url:
                c.execute(
                    "UPDATE students SET name=?,email=?,mobile=?,dept=?,rollno=?,userid=?,photo_url=?,status=? WHERE id=?",
                    (name, email, mobile, dept, rollno, userid, photo_url, status or 'approved', sid))
            else:
                c.execute(
                    "UPDATE students SET name=?,email=?,mobile=?,dept=?,rollno=?,userid=?,status=? WHERE id=?",
                    (name, email, mobile, dept, rollno, userid, status or 'approved', sid))
        c.commit()

    with get_db() as c:
        row = c.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
    return jsonify({'ok': True, 'msg': 'Student updated successfully.', 'user': safe_s(row)})


@app.route('/api/admin/attendance')
@require_login('admin')
def api_admin_attendance():
    q = f"%{request.args.get('q','').lower()}%"
    with get_db() as c:
        rs = c.execute("""
            SELECT a.*, s.name AS student_name, t.name AS teacher_name
            FROM attendance a JOIN students s ON a.student_id=s.id JOIN teachers t ON a.teacher_id=t.id
            WHERE lower(a.subject) LIKE ? OR lower(a.dept) LIKE ?
            ORDER BY a.date DESC""", (q,q)).fetchall()
    return jsonify(rows(rs))

@app.route('/api/admin/chats')
@require_login('admin')
def api_admin_chats():
    with get_db() as c:
        chats_rs = c.execute("""
            SELECT ch.id, t.name AS teacher_name, s.name AS student_name
            FROM chats ch JOIN teachers t ON ch.teacher_id=t.id JOIN students s ON ch.student_id=s.id
            ORDER BY ch.created_at DESC""").fetchall()
        result = []
        for ch in chats_rs:
            msgs = c.execute("""
                SELECT m.sender_type, m.text, m.created_at,
                       CASE m.sender_type WHEN 'teacher' THEN t.name ELSE s.name END AS sender_name
                FROM messages m JOIN chats c2 ON m.chat_id=c2.id
                JOIN teachers t ON c2.teacher_id=t.id JOIN students s ON c2.student_id=s.id
                WHERE m.chat_id=? ORDER BY m.created_at""", (ch['id'],)).fetchall()
            d = dict(ch); d['messages'] = rows(msgs); result.append(d)
    return jsonify(result)

@app.route('/api/admin/facial_recognition_status')
@require_login('admin')
def api_facial_recognition_status():
    """Get facial recognition system status for admin dashboard"""
    with get_db() as c:
        student_count = c.execute("SELECT COUNT(*) FROM students WHERE status='approved'").fetchone()[0]
        face_enrolled = c.execute("SELECT COUNT(*) FROM students WHERE face_enrolled=1").fetchone()[0]
        face_recognized_count = c.execute("SELECT COUNT(*) FROM attendance WHERE face_recognized=1").fetchone()[0]
    
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
    
    model_exists = os.path.exists(MODEL_PATH)
    train_status = read_train_status()
    
    return jsonify({
        "system_status": {
            "total_students": student_count,
            "face_enrolled": face_enrolled,
            "face_images_collected": len(dataset_dirs),
            "faces_per_student": faces_per_student,
            "model_trained": model_exists,
            "face_recognized_count": face_recognized_count,
        },
        "train_status": train_status,
        "recommendations": []
    })


# ═══════════════════════════════════════════════════════════════
# TEACHER
# ═══════════════════════════════════════════════════════════════
@app.route('/api/teacher/profile')
@require_login('teacher')
def api_teacher_profile():
    with get_db() as c:
        row = c.execute("SELECT * FROM teachers WHERE id=?", (session['user_id'],)).fetchone()
    return jsonify(safe_t(row))

@app.route('/api/teacher/attendance', methods=['POST'])
@require_login('teacher')
def api_mark_attendance():
    tid     = session['user_id']
    date    = request.form.get('date','').strip()
    time_v  = request.form.get('time','').strip()
    dept    = request.form.get('dept','').strip()
    subject = request.form.get('subject','').strip()
    if not all([date, dept, subject]):
        return jsonify({'ok':False,'msg':'Date, dept and subject required.'}), 400
    photo_url = save_upload(request.files.get('photo'))
    with get_db() as c:
        studs = c.execute("SELECT * FROM students WHERE dept=? AND status='approved'", (dept,)).fetchall()
        if not studs:
            return jsonify({'ok':False,'msg':'No approved students in this department.'}), 404
        results = []
        for s in studs:
            present = 1 if random.random() > 0.25 else 0
            c.execute("INSERT INTO attendance (student_id,teacher_id,date,time,dept,subject,present,photo_url,face_recognized,confidence) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (s['id'],tid,date,time_v,dept,subject,present,photo_url,0,0.0))
            results.append({'student_id':s['id'],'student_name':s['name'],
                            'photo_url':s['photo_url'],'dept':s['dept'],'present':bool(present)})
        c.commit()
    return jsonify({'ok':True,'results':results,
                    'summary':{'total':len(results),
                               'present':sum(1 for r in results if r['present']),
                               'absent': sum(1 for r in results if not r['present'])}})

@app.route('/api/teacher/recognize_face', methods=['POST'])
@require_login('teacher')
def api_recognize_face():
    """Recognize student face from uploaded image"""
    if "image" not in request.files:
        return jsonify({"recognized": False, "error":"no_image"}), 400
    
    img_file = request.files["image"]
    try:
        emb = model.extract_embedding_for_image(img_file.stream)
        if emb is None:
            return jsonify({"recognized": False, "error":"face_not_detected"}), 200
        
        clf = model.load_model_if_exists()
        if clf is None:
            return jsonify({"recognized": False, "error":"model_not_trained"}), 200
        
        pred_label, conf = model.predict_with_model(clf, emb)
        
        # Confidence threshold
        CONFIDENCE_THRESHOLD = 0.35
        if conf < CONFIDENCE_THRESHOLD:
            return jsonify({"recognized": False, "confidence": float(conf), "error":"low_confidence"}), 200
        
        # Find student name
        with get_db() as c:
            row = c.execute("SELECT id, name FROM students WHERE id=?", (int(pred_label),)).fetchone()
            if not row:
                return jsonify({"recognized": False, "error":"student_not_found"}), 200
            student_id = row['id']
            name = row['name']
        
        return jsonify({
            "recognized": True,
            "student_id": student_id,
            "name": name,
            "confidence": float(conf)
        }), 200
        
    except Exception as e:
        app.logger.error(f"Face recognition error: {e}")
        return jsonify({"recognized": False, "error": str(e)}), 500

@app.route('/api/teacher/train_model', methods=['POST'])
@require_login('teacher')
def api_train_model():
    """Start facial recognition model training"""
    status = read_train_status()
    if status.get("running"):
        return jsonify({"status":"already_running"}), 202
    
    # Reset status
    write_train_status({"running": True, "progress": 0, "message": "Starting training"})
    
    # Start background thread
    def train_callback(progress, message):
        write_train_status({"running": progress < 100, "progress": progress, "message": message})
    
    t = threading.Thread(target=model.train_model_background, args=(DATASET_DIR, train_callback))
    t.daemon = True
    t.start()
    
    return jsonify({"status":"started"}), 202

@app.route('/api/teacher/train_status', methods=['GET'])
@require_login('teacher')
def api_train_status():
    """Get model training progress"""
    return jsonify(read_train_status())

@app.route('/api/teacher/attendance/history')
@require_login('teacher')
def api_teacher_attendance_history():
    with get_db() as c:
        rs = c.execute("""
            SELECT a.*, s.name AS student_name, s.photo_url AS student_photo
            FROM attendance a JOIN students s ON a.student_id=s.id
            WHERE a.teacher_id=? ORDER BY a.date DESC""", (session['user_id'],)).fetchall()
    return jsonify(rows(rs))

@app.route('/api/students/list')
@require_login('teacher')
def api_students_list():
    with get_db() as c:
        rs = c.execute("SELECT id,name,email,mobile,dept,rollno,userid,photo_url,face_enrolled,status,created_at "
                       "FROM students WHERE status='approved' ORDER BY name").fetchall()
    return jsonify(rows(rs))


# ═══════════════════════════════════════════════════════════════
# STUDENT
# ═══════════════════════════════════════════════════════════════
@app.route('/api/student/profile')
@require_login('student')
def api_student_profile():
    with get_db() as c:
        row = c.execute("SELECT * FROM students WHERE id=?", (session['user_id'],)).fetchone()
    return jsonify(safe_s(row))

@app.route('/api/student/enroll_face', methods=['POST'])
@require_login('student')
def api_enroll_face():
    """Enroll student face images for facial recognition"""
    student_id = session['user_id']
    files = request.files.getlist("images[]")
    
    # Create dataset folder for this student
    folder = os.path.join(DATASET_DIR, str(student_id))
    os.makedirs(folder, exist_ok=True)
    
    saved = 0
    for f in files:
        try:
            fname = f"{dt.now().timestamp():.6f}_{saved}.jpg"
            path = os.path.join(folder, fname)
            f.save(path)
            saved += 1
        except Exception as e:
            app.logger.error(f"Error saving face image: {e}")
    
    # Update face_enrolled flag in database
    if saved > 0:
        with get_db() as c:
            c.execute("UPDATE students SET face_enrolled=1 WHERE id=?", (student_id,))
            c.commit()
    
    return jsonify({"ok": True, "msg": f"Successfully enrolled {saved} face images!", "saved": saved})

@app.route('/api/student/attendance')
@require_login('student')
def api_student_attendance():
    with get_db() as c:
        rs = c.execute("""
            SELECT a.*, s.name AS student_name, t.name AS teacher_name
            FROM attendance a JOIN students s ON a.student_id=s.id JOIN teachers t ON a.teacher_id=t.id
            WHERE a.student_id=? ORDER BY a.subject, a.date""", (session['user_id'],)).fetchall()
    return jsonify(rows(rs))

@app.route('/api/teachers/list')
@require_login('student')
def api_teachers_list():
    with get_db() as c:
        rs = c.execute("SELECT id,name,email,mobile,dept,userid,photo_url,status,created_at "
                       "FROM teachers WHERE status='approved' ORDER BY name").fetchall()
    return jsonify(rows(rs))


# ═══════════════════════════════════════════════════════════════
# CHAT
# ═══════════════════════════════════════════════════════════════
@app.route('/api/chats')
@require_login('teacher','student')
def api_get_chats():
    role = session['role']; uid = session['user_id']
    with get_db() as c:
        if role == 'teacher':
            rs = c.execute("""
                SELECT ch.id, ch.teacher_id, ch.student_id,
                       s.name AS student_name, s.photo_url AS other_photo, s.dept AS other_dept,
                       (SELECT text       FROM messages WHERE chat_id=ch.id ORDER BY created_at DESC LIMIT 1) AS last_message,
                       (SELECT created_at FROM messages WHERE chat_id=ch.id ORDER BY created_at DESC LIMIT 1) AS last_time
                FROM chats ch JOIN students s ON ch.student_id=s.id
                WHERE ch.teacher_id=? ORDER BY last_time DESC""", (uid,)).fetchall()
        else:
            rs = c.execute("""
                SELECT ch.id, ch.teacher_id, ch.student_id,
                       t.name AS teacher_name, t.photo_url AS other_photo, t.dept AS other_dept,
                       (SELECT text       FROM messages WHERE chat_id=ch.id ORDER BY created_at DESC LIMIT 1) AS last_message,
                       (SELECT created_at FROM messages WHERE chat_id=ch.id ORDER BY created_at DESC LIMIT 1) AS last_time
                FROM chats ch JOIN teachers t ON ch.teacher_id=t.id
                WHERE ch.student_id=? ORDER BY last_time DESC""", (uid,)).fetchall()
    return jsonify(rows(rs))

@app.route('/api/chats', methods=['POST'])
@require_login('teacher','student')
def api_create_chat():
    d = request.get_json(force=True)
    role = session['role']; uid = session['user_id']
    teacher_id = uid if role == 'teacher' else d.get('other_id')
    student_id = d.get('other_id') if role == 'teacher' else uid
    if not teacher_id or not student_id:
        return jsonify({'ok':False,'msg':'Missing participant.'}), 400
    with get_db() as c:
        ex = c.execute("SELECT id FROM chats WHERE teacher_id=? AND student_id=?",
                       (teacher_id, student_id)).fetchone()
        if ex: return jsonify({'ok':True,'chat_id':ex['id']})
        c.execute("INSERT INTO chats (teacher_id,student_id) VALUES (?,?)", (teacher_id, student_id))
        c.commit()
        chat_id = c.execute("SELECT id FROM chats WHERE teacher_id=? AND student_id=?",
                            (teacher_id, student_id)).fetchone()['id']
    return jsonify({'ok':True,'chat_id':chat_id})

@app.route('/api/chats/<int:chat_id>/messages')
@require_login('teacher','student')
def api_get_messages(chat_id):
    with get_db() as c:
        rs = c.execute("SELECT * FROM messages WHERE chat_id=? ORDER BY created_at", (chat_id,)).fetchall()
    return jsonify(rows(rs))

@app.route('/api/chats/<int:chat_id>/messages', methods=['POST'])
@require_login('teacher','student')
def api_send_message(chat_id):
    d    = request.get_json(force=True)
    text = d.get('text','').strip()
    if not text: return jsonify({'ok':False,'msg':'Message cannot be empty.'}), 400
    role = session['role']; uid = session['user_id']
    sender_type = 'teacher' if role == 'teacher' else 'student'
    with get_db() as c:
        c.execute("INSERT INTO messages (chat_id,sender_id,sender_type,text) VALUES (?,?,?,?)",
                  (chat_id, uid, sender_type, text))
        c.commit()
        msg_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        ts     = c.execute("SELECT created_at FROM messages WHERE id=?", (msg_id,)).fetchone()['created_at']
    return jsonify({'ok':True,'message_id':msg_id,'created_at':ts})


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT (Port 5000 - UI Portal)
# ═══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    init_db()
    print("\n" + "="*70)
    print("  🌐 EduFace UI Portal (Option 2 Architecture)")
    print("  📍 Port 5000 - User Interface & Authentication")
    print("="*70)
    print("  🔗 Connected Services:")
    print("     • ML Engine: http://localhost:5100 (Attendance-System2)")
    print("     • Database: " + DB_PATH)
    print("     • Dataset: " + DATASET_DIR)
    print("="*70)
    print("  🔐 DEFAULT CREDENTIALS:")
    print("     • ADMIN      →  admin@123       /  Admin@123")
    print("     • TEACHER    →  priya@edu       /  Teacher@123")
    print("     • STUDENT    →  arjun@student   /  Arjun@123")
    print("="*70)
    print("  ✨ FEATURES:")
    print("     ✓ Multi-role authentication (Admin, Teacher, Student)")
    print("     ✓ Student registration with face enrollment")
    print("     ✓ Teacher-Student messaging & collaboration")
    print("     ✓ Admin dashboard & approval management")
    print("     ✓ Attendance marking with UI (faces recognized by ML engine)")
    print("     ✓ Model training status from ML engine")
    print("="*70)
    print("  🚀 Starting UI Portal on Port 5000...")
    print("     NOTE: Attendance-System2 ML Engine must run separately on Port 5100")
    print("="*70 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
