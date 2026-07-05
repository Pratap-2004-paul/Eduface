import sqlite3
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = "attendance.db"

# ─────────────────────────────────────────────
#  INIT — create all tables + default admin
# ─────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()

    # ── departments ──────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS departments (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── users ────────────────────────────────
    # role   : "admin" | "teacher" | "student"
    # status : "pending" | "approved" | "rejected"
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name     TEXT NOT NULL,
            email         TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL,
            department_id INTEGER,
            status        TEXT DEFAULT "pending",
            created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments(id)
        )
    ''')

    # ── attendance ───────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id    INTEGER NOT NULL,
            department_id INTEGER NOT NULL,
            marked_by     INTEGER NOT NULL,
            date          TEXT NOT NULL,
            time          TEXT NOT NULL,
            status        TEXT DEFAULT "Present",
            FOREIGN KEY (student_id)    REFERENCES users(id),
            FOREIGN KEY (department_id) REFERENCES departments(id),
            FOREIGN KEY (marked_by)     REFERENCES users(id)
        )
    ''')

    # ── face_data ────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS face_data (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL UNIQUE,
            encoding_path TEXT NOT NULL,
            registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # ── group_messages ───────────────────────────
    # Department group chat messages
    c.execute('''
        CREATE TABLE IF NOT EXISTS group_messages (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            department_id INTEGER NOT NULL,
            sender_id     INTEGER NOT NULL,
            message       TEXT NOT NULL,
            sent_at       TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id)
                REFERENCES departments(id),
            FOREIGN KEY (sender_id)
                REFERENCES users(id)
        )
    ''')

    # ── private_messages ─────────────────────────
    # One-to-one private messages
    c.execute('''
        CREATE TABLE IF NOT EXISTS private_messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id   INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            message     TEXT NOT NULL,
            is_read     INTEGER DEFAULT 0,
            sent_at     TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id)
                REFERENCES users(id),
            FOREIGN KEY (receiver_id)
                REFERENCES users(id)
        )
    ''')

    conn.commit()

    # ── seed default admin ───────────────────
    c.execute("SELECT id FROM users WHERE role='admin'")
    if not c.fetchone():
        c.execute('''
            INSERT INTO users (full_name, email, password_hash, role, status)
            VALUES (?, ?, ?, "admin", "approved")
        ''', (
            "Admin",
            "admin@attendance.com",
            generate_password_hash("admin123")
        ))
        conn.commit()
        print("✓ Default admin created.")
        print("  Email   : admin@attendance.com")
        print("  Password: admin123")

    conn.close()
    print("✓ Database ready.")


# ─────────────────────────────────────────────
#  DEPARTMENT helpers
# ─────────────────────────────────────────────

def create_department(name):
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    try:
        c.execute("INSERT INTO departments (name) VALUES (?)", (name,))
        conn.commit()
        dept_id = c.lastrowid
        conn.close()
        return True, dept_id
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Department already exists."


def get_all_departments():
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    c.execute("SELECT id, name FROM departments ORDER BY name")
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1]} for r in rows]


def delete_department(dept_id):
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    c.execute("DELETE FROM departments WHERE id=?", (dept_id,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
#  USER helpers
# ─────────────────────────────────────────────

def register_user(full_name, email, password, role, department_id):
    """
    Register a new teacher or student.
    Status starts as 'pending' — admin must approve.
    Returns (success: bool, message: str)
    """
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()

    # Check email not already used
    c.execute("SELECT id FROM users WHERE email=?", (email,))
    if c.fetchone():
        conn.close()
        return False, "Email already registered."

    hashed = generate_password_hash(password)
    try:
        c.execute('''
            INSERT INTO users (full_name, email, password_hash, role, department_id, status)
            VALUES (?, ?, ?, ?, ?, "pending")
        ''', (full_name, email, hashed, role, department_id))
        conn.commit()
        conn.close()
        return True, "Registration successful. Please wait for admin approval."
    except Exception as e:
        conn.close()
        return False, str(e)


def login_user(email, password):
    """
    Verify credentials.
    Returns user dict or None.
    """
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    c.execute('''
        SELECT u.id, u.full_name, u.email, u.password_hash,
               u.role, u.status, u.department_id, d.name
        FROM users u
        LEFT JOIN departments d ON u.department_id = d.id
        WHERE u.email = ?
    ''', (email,))
    row = conn.cursor().fetchone() if False else c.fetchone()
    conn.close()

    if not row:
        return None, "Email not found."

    if not check_password_hash(row[3], password):
        return None, "Incorrect password."

    if row[5] == "pending":
        return None, "Your account is pending admin approval."

    if row[5] == "rejected":
        return None, "Your account has been rejected. Contact admin."

    user = {
        "id":          row[0],
        "full_name":   row[1],
        "email":       row[2],
        "role":        row[4],
        "status":      row[5],
        "dept_id":     row[6],
        "dept_name":   row[7] or "N/A"
    }
    return user, "Login successful."


def get_user_by_id(user_id):
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    c.execute('''
        SELECT u.id, u.full_name, u.email, u.role,
               u.status, u.department_id, d.name, u.created_at
        FROM users u
        LEFT JOIN departments d ON u.department_id = d.id
        WHERE u.id = ?
    ''', (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id":          row[0],
        "full_name":   row[1],
        "email":       row[2],
        "role":        row[3],
        "status":      row[4],
        "dept_id":     row[5],
        "dept_name":   row[6] or "N/A",
        "created_at":  row[7]
    }


# ─────────────────────────────────────────────
#  ADMIN helpers
# ─────────────────────────────────────────────

def get_pending_users():
    """All users waiting for approval."""
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    c.execute('''
        SELECT u.id, u.full_name, u.email, u.role,
               u.status, d.name, u.created_at
        FROM users u
        LEFT JOIN departments d ON u.department_id = d.id
        WHERE u.status = "pending"
        ORDER BY u.created_at DESC
    ''')
    rows = c.fetchall()
    conn.close()
    return [_user_row(r) for r in rows]


def get_all_users(role=None):
    """All users, optionally filtered by role."""
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    if role:
        c.execute('''
            SELECT u.id, u.full_name, u.email, u.role,
                   u.status, d.name, u.created_at
            FROM users u
            LEFT JOIN departments d ON u.department_id = d.id
            WHERE u.role = ?
            ORDER BY u.created_at DESC
        ''', (role,))
    else:
        c.execute('''
            SELECT u.id, u.full_name, u.email, u.role,
                   u.status, d.name, u.created_at
            FROM users u
            LEFT JOIN departments d ON u.department_id = d.id
            WHERE u.role != "admin"
            ORDER BY u.created_at DESC
        ''')
    rows = c.fetchall()
    conn.close()
    return [_user_row(r) for r in rows]


def update_user_status(user_id, status):
    """Approve or reject a user."""
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    c.execute("UPDATE users SET status=? WHERE id=?", (status, user_id))
    conn.commit()
    conn.close()


def delete_user(user_id):
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    c.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


def _user_row(r):
    """Convert a DB row to a user dict."""
    return {
        "id":         r[0],
        "full_name":  r[1],
        "email":      r[2],
        "role":       r[3],
        "status":     r[4],
        "dept_name":  r[5] or "N/A",
        "created_at": r[6]
    }


# ─────────────────────────────────────────────
#  TEACHER helpers
# ─────────────────────────────────────────────

def get_students_by_dept(department_id):
    """All approved students in a department."""
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    c.execute('''
        SELECT id, full_name, email, status, created_at
        FROM users
        WHERE role="student" AND department_id=? AND status="approved"
        ORDER BY full_name
    ''', (department_id,))
    rows = c.fetchall()
    conn.close()
    return [
        {
            "id":         r[0],
            "full_name":  r[1],
            "email":      r[2],
            "status":     r[3],
            "created_at": r[4]
        }
        for r in rows
    ]


def mark_attendance(student_id, department_id, marked_by):
    """
    Mark one student present today.
    Prevents duplicate for same student on same day.
    Returns (success, message)
    """
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()

    today = date.today().strftime("%Y-%m-%d")
    now   = datetime.now().strftime("%H:%M:%S")

    c.execute(
        "SELECT id FROM attendance WHERE student_id=? AND date=?",
        (student_id, today)
    )
    if c.fetchone():
        conn.close()
        return False, "Already marked present today."

    c.execute('''
        INSERT INTO attendance (student_id, department_id, marked_by, date, time)
        VALUES (?, ?, ?, ?, ?)
    ''', (student_id, department_id, marked_by, today, now))
    conn.commit()
    conn.close()
    return True, f"Marked present at {now}"


def get_attendance_by_dept(department_id, filter_date=None):
    """All attendance records for a department."""
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()

    if filter_date:
        c.execute('''
            SELECT a.id, u.full_name, a.date, a.time, a.status,
                   t.full_name as teacher_name
            FROM attendance a
            JOIN users u ON a.student_id    = u.id
            JOIN users t ON a.marked_by     = t.id
            WHERE a.department_id = ? AND a.date = ?
            ORDER BY a.date DESC, a.time DESC
        ''', (department_id, filter_date))
    else:
        c.execute('''
            SELECT a.id, u.full_name, a.date, a.time, a.status,
                   t.full_name as teacher_name
            FROM attendance a
            JOIN users u ON a.student_id    = u.id
            JOIN users t ON a.marked_by     = t.id
            WHERE a.department_id = ?
            ORDER BY a.date DESC, a.time DESC
        ''', (department_id,))

    rows = c.fetchall()
    conn.close()
    return [
        {
            "id":           r[0],
            "student_name": r[1],
            "date":         r[2],
            "time":         r[3],
            "status":       r[4],
            "teacher_name": r[5]
        }
        for r in rows
    ]


def delete_attendance_record(record_id):
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    c.execute("DELETE FROM attendance WHERE id=?", (record_id,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
#  STUDENT helpers
# ─────────────────────────────────────────────

def get_student_attendance(student_id, filter_date=None):
    """All attendance records for one student."""
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()

    if filter_date:
        c.execute('''
            SELECT a.id, a.date, a.time, a.status,
                   t.full_name as teacher_name
            FROM attendance a
            JOIN users t ON a.marked_by = t.id
            WHERE a.student_id = ? AND a.date = ?
            ORDER BY a.date DESC
        ''', (student_id, filter_date))
    else:
        c.execute('''
            SELECT a.id, a.date, a.time, a.status,
                   t.full_name as teacher_name
            FROM attendance a
            JOIN users t ON a.marked_by = t.id
            WHERE a.student_id = ?
            ORDER BY a.date DESC
        ''', (student_id,))

    rows = c.fetchall()
    conn.close()
    return [
        {
            "id":           r[0],
            "date":         r[1],
            "time":         r[2],
            "status":       r[3],
            "teacher_name": r[4]
        }
        for r in rows
    ]


def get_student_attendance_stats(student_id):
    """
    Returns total days present and attendance percentage
    based on days present vs total working days recorded.
    """
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()

    # Total present
    c.execute(
        "SELECT COUNT(*) FROM attendance WHERE student_id=?",
        (student_id,)
    )
    present = c.fetchone()[0]

    # Total unique dates any attendance was marked in dept
    c.execute('''
        SELECT COUNT(DISTINCT date) FROM attendance
        WHERE department_id = (
            SELECT department_id FROM users WHERE id = ?
        )
    ''', (student_id,))
    total_days = c.fetchone()[0]

    conn.close()

    pct = round((present / total_days * 100), 1) if total_days > 0 else 0
    return {
        "present":    present,
        "total_days": total_days,
        "percentage": pct
    }


# ─────────────────────────────────────────────
#  FACE DATA helpers
# ─────────────────────────────────────────────

def save_face_data(user_id, encoding_path):
    """Save face encoding path for a user."""
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO face_data (user_id, encoding_path)
        VALUES (?, ?)
    ''', (user_id, encoding_path))
    conn.commit()
    conn.close()


def get_face_data(user_id):
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    c.execute(
        "SELECT encoding_path FROM face_data WHERE user_id=?",
        (user_id,)
    )
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def get_all_face_data_for_dept(department_id):
    """
    Load all face encoding paths for students in a department.
    Used by teacher's face recognition.
    """
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    c.execute('''
        SELECT u.id, u.full_name, f.encoding_path
        FROM face_data f
        JOIN users u ON f.user_id = u.id
        WHERE u.department_id = ?
          AND u.role = "student"
          AND u.status = "approved"
    ''', (department_id,))
    rows = c.fetchall()
    conn.close()
    return [
        {
            "user_id":       r[0],
            "full_name":     r[1],
            "encoding_path": r[2]
        }
        for r in rows
    ]

def get_face_registration_status(department_id):
    """
    Returns list of all students in a dept
    with a flag showing if they registered face or not.
    """
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    c.execute('''
        SELECT u.id, u.full_name, u.email,
               CASE WHEN f.user_id IS NOT NULL
                    THEN 1 ELSE 0 END as face_registered
        FROM users u
        LEFT JOIN face_data f ON u.id = f.user_id
        WHERE u.department_id = ?
          AND u.role = "student"
          AND u.status = "approved"
        ORDER BY face_registered DESC, u.full_name
    ''', (department_id,))
    rows = c.fetchall()
    conn.close()
    return [
        {
            "id":              r[0],
            "full_name":       r[1],
            "email":           r[2],
            "face_registered": bool(r[3])
        }
        for r in rows
    ]


def get_all_face_stats():
    """
    Admin view — how many students registered faces
    per department.
    """
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    c.execute('''
        SELECT d.name,
               COUNT(u.id) as total_students,
               COUNT(f.user_id) as registered_faces
        FROM departments d
        LEFT JOIN users u
          ON u.department_id = d.id
          AND u.role = "student"
          AND u.status = "approved"
        LEFT JOIN face_data f ON f.user_id = u.id
        GROUP BY d.id, d.name
        ORDER BY d.name
    ''')
    rows = c.fetchall()
    conn.close()
    return [
        {
            "dept_name":  r[0],
            "total":      r[1],
            "registered": r[2],
            "missing":    r[1] - r[2]
        }
        for r in rows
    ]

def update_user_details(user_id, full_name, email,
                         department_id, status,
                         new_password=None):
    """
    Admin updates a user's details.
    Returns (success: bool, message: str)
    """
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()

    # Check email not taken by another user
    c.execute(
        "SELECT id FROM users WHERE email=? AND id!=?",
        (email, user_id)
    )
    if c.fetchone():
        conn.close()
        return False, "Email already used by another user."

    if new_password:
        from werkzeug.security import generate_password_hash
        hashed = generate_password_hash(new_password)
        c.execute('''
            UPDATE users
            SET full_name=?, email=?,
                department_id=?, status=?,
                password_hash=?
            WHERE id=?
        ''', (full_name, email,
              department_id, status,
              hashed, user_id))
    else:
        c.execute('''
            UPDATE users
            SET full_name=?, email=?,
                department_id=?, status=?
            WHERE id=?
        ''', (full_name, email,
              department_id, status,
              user_id))

    conn.commit()
    conn.close()
    return True, "User updated successfully."

def get_attendance_pivot(department_id):
    """
    Returns attendance as a pivot table.

    Structure:
    {
      "students": [
        {"id": 3, "name": "Rahul Singh"},
        ...
      ],
      "dates": ["2026-06-15", "2026-06-16", ...],
      "data": {
        3: {"2026-06-15": "Present", "2026-06-16": "Absent"},
        ...
      }
    }
    """
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()

    # Get all approved students in dept
    c.execute('''
        SELECT id, full_name
        FROM users
        WHERE department_id = ?
          AND role = "student"
          AND status = "approved"
        ORDER BY full_name
    ''', (department_id,))
    student_rows = c.fetchall()
    students = [
        {"id": r[0], "name": r[1]}
        for r in student_rows
    ]

    if not students:
        conn.close()
        return {
            "students": [],
            "dates":    [],
            "data":     {}
        }

    # Get all unique dates attendance was taken in dept
    c.execute('''
        SELECT DISTINCT date
        FROM attendance
        WHERE department_id = ?
        ORDER BY date ASC
    ''', (department_id,))
    dates = [r[0] for r in c.fetchall()]

    # Get all attendance records for dept
    c.execute('''
        SELECT student_id, date
        FROM attendance
        WHERE department_id = ?
    ''', (department_id,))
    records = c.fetchall()
    conn.close()

    # Build a set of (student_id, date) for O(1) lookup
    present_set = set()
    for student_id, att_date in records:
        present_set.add((student_id, att_date))

    # Build pivot data
    data = {}
    for student in students:
        sid = student["id"]
        data[sid] = {}
        for d in dates:
            if (sid, d) in present_set:
                data[sid][d] = "Present"
            else:
                data[sid][d] = "Absent"

    return {
        "students": students,
        "dates":    dates,
        "data":     data
    }

# ─────────────────────────────────────────────
#  CHAT helpers
# ─────────────────────────────────────────────

def save_group_message(department_id, sender_id, message):
    """Save a group chat message."""
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    c.execute('''
        INSERT INTO group_messages
            (department_id, sender_id, message)
        VALUES (?, ?, ?)
    ''', (department_id, sender_id, message))
    msg_id = c.lastrowid
    conn.commit()

    # Fetch the saved message with sender name
    c.execute('''
        SELECT gm.id, u.full_name, u.role,
               gm.message, gm.sent_at
        FROM group_messages gm
        JOIN users u ON gm.sender_id = u.id
        WHERE gm.id = ?
    ''', (msg_id,))
    row = c.fetchone()
    conn.close()

    if row:
        return {
            "id":          row[0],
            "sender_name": row[1],
            "sender_role": row[2],
            "message":     row[3],
            "sent_at":     row[4]
        }
    return None


def get_group_messages(department_id, limit=100):
    """Get last N group messages for a department."""
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    c.execute('''
        SELECT gm.id, u.full_name, u.role,
               gm.message, gm.sent_at, gm.sender_id
        FROM group_messages gm
        JOIN users u ON gm.sender_id = u.id
        WHERE gm.department_id = ?
        ORDER BY gm.sent_at DESC
        LIMIT ?
    ''', (department_id, limit))
    rows = c.fetchall()
    conn.close()

    # Reverse to show oldest first
    rows = list(reversed(rows))
    return [
        {
            "id":          r[0],
            "sender_name": r[1],
            "sender_role": r[2],
            "message":     r[3],
            "sent_at":     r[4],
            "sender_id":   r[5]
        }
        for r in rows
    ]


def save_private_message(sender_id, receiver_id, message):
    """Save a private message between two users."""
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    c.execute('''
        INSERT INTO private_messages
            (sender_id, receiver_id, message)
        VALUES (?, ?, ?)
    ''', (sender_id, receiver_id, message))
    msg_id = c.lastrowid
    conn.commit()

    # Fetch saved message with sender name
    c.execute('''
        SELECT pm.id, u.full_name, u.role,
               pm.message, pm.sent_at,
               pm.sender_id, pm.receiver_id
        FROM private_messages pm
        JOIN users u ON pm.sender_id = u.id
        WHERE pm.id = ?
    ''', (msg_id,))
    row = c.fetchone()
    conn.close()

    if row:
        return {
            "id":          row[0],
            "sender_name": row[1],
            "sender_role": row[2],
            "message":     row[3],
            "sent_at":     row[4],
            "sender_id":   row[5],
            "receiver_id": row[6]
        }
    return None


def get_private_messages(user1_id, user2_id, limit=100):
    """Get private messages between two users."""
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    c.execute('''
        SELECT pm.id, u.full_name, u.role,
               pm.message, pm.sent_at,
               pm.sender_id, pm.receiver_id,
               pm.is_read
        FROM private_messages pm
        JOIN users u ON pm.sender_id = u.id
        WHERE (pm.sender_id = ? AND pm.receiver_id = ?)
           OR (pm.sender_id = ? AND pm.receiver_id = ?)
        ORDER BY pm.sent_at DESC
        LIMIT ?
    ''', (user1_id, user2_id,
          user2_id, user1_id, limit))
    rows = c.fetchall()
    conn.close()

    rows = list(reversed(rows))
    return [
        {
            "id":          r[0],
            "sender_name": r[1],
            "sender_role": r[2],
            "message":     r[3],
            "sent_at":     r[4],
            "sender_id":   r[5],
            "receiver_id": r[6],
            "is_read":     r[7]
        }
        for r in rows
    ]


def mark_messages_read(sender_id, receiver_id):
    """Mark all messages from sender to receiver as read."""
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    c.execute('''
        UPDATE private_messages
        SET is_read = 1
        WHERE sender_id = ? AND receiver_id = ?
    ''', (sender_id, receiver_id))
    conn.commit()
    conn.close()


def get_unread_count(user_id):
    """Get total unread private messages for a user."""
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()
    c.execute('''
        SELECT COUNT(*)
        FROM private_messages
        WHERE receiver_id = ? AND is_read = 0
    ''', (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count


def get_chat_contacts(user_id, department_id, role):
    """
    Get list of people this user can chat with privately.
    Teacher → all students in their dept
    Student → all teachers in their dept
    """
    conn = sqlite3.connect(DATABASE)
    c    = conn.cursor()

    if role == "teacher":
        # Teachers see all students in their dept
        c.execute('''
            SELECT u.id, u.full_name, u.role
            FROM users u
            WHERE u.department_id = ?
              AND u.role = "student"
              AND u.status = "approved"
              AND u.id != ?
            ORDER BY u.full_name
        ''', (department_id, user_id))
    else:
        # Students see all teachers in their dept
        c.execute('''
            SELECT u.id, u.full_name, u.role
            FROM users u
            WHERE u.department_id = ?
              AND u.role = "teacher"
              AND u.status = "approved"
              AND u.id != ?
            ORDER BY u.full_name
        ''', (department_id, user_id))

    rows = c.fetchall()
    conn.close()
    return [
        {
            "id":       r[0],
            "name":     r[1],
            "role":     r[2]
        }
        for r in rows
    ]