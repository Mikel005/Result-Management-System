from flask import Flask, jsonify, render_template, request, redirect, send_file, session, url_for, flash, g
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature, BadSignature
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
#from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import sqlite3
import csv
import io
import urllib.parse
from datetime import datetime
import os
from utils import calculate_grade, get_grade_points
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-please-change')

# Mail Configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'mnwatu10@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'ourm irbe knlk opbk')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'mnwatu10@gmail.com')

mail = Mail(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

csrf = CSRFProtect(app)
DATABASE = 'results.db'

# Initialize AI Engine
from ai_engine import AIEngine
ai_engine = AIEngine(DATABASE)

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///results.db'
#app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
#db = SQLAlchemy(app)
#login_manager = LoginManager(app)
#login_manager.login_view = 'login'
#app.secret_key = 'your-secret-key-change-in-production'


# Database setup
def init_db():
    conn = sqlite3.connect('results.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Students table
    c.execute('''CREATE TABLE IF NOT EXISTS students
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT,
                class TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Subjects table
    c.execute('''CREATE TABLE IF NOT EXISTS subjects
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_code TEXT UNIQUE NOT NULL,
                subject_name TEXT NOT NULL,
                total_marks INTEGER DEFAULT 100,
                class_id INTEGER,
                FOREIGN KEY (class_id) REFERENCES classes(id))''')

    # Classes table
    c.execute('''CREATE TABLE IF NOT EXISTS classes
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # Faculties table
    c.execute('''CREATE TABLE IF NOT EXISTS faculties
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # Departments table
    c.execute('''CREATE TABLE IF NOT EXISTS departments
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                faculty_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (faculty_id) REFERENCES faculties(id))''')

    # Migration: Add class_id to subjects if not exists (for existing DBs)
    try:
        c.execute("ALTER TABLE subjects ADD COLUMN class_id INTEGER")
    except sqlite3.OperationalError:
        pass # Column likely exists or table doesn't exist yet

    # Migration: Add department_id to students
    try:
        c.execute("ALTER TABLE students ADD COLUMN department_id INTEGER")
    except sqlite3.OperationalError:
        pass

    # Migration: Add department_id to subjects
    try:
        c.execute("ALTER TABLE subjects ADD COLUMN department_id INTEGER")
    except sqlite3.OperationalError:
        pass

    # Migration: Add PIN to students for student portal login
    try:
        c.execute("ALTER TABLE students ADD COLUMN pin TEXT")
    except sqlite3.OperationalError:
        pass
    
    # Results table
    c.execute('''CREATE TABLE IF NOT EXISTS results
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                subject_code TEXT NOT NULL,
                marks REAL NOT NULL,
                grade TEXT,
                status TEXT DEFAULT 'pending',
                semester TEXT,
                academic_year TEXT,
                created_by TEXT,
                approved_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved_at TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (subject_code) REFERENCES subjects(subject_code))''')
    
    # Audit log table
    c.execute('''CREATE TABLE IF NOT EXISTS audit_log
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Result amendments table
    c.execute('''CREATE TABLE IF NOT EXISTS result_amendments
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id INTEGER NOT NULL,
                old_marks REAL,
                new_marks REAL,
                old_grade TEXT,
                new_grade TEXT,
                reason TEXT,
                amended_by TEXT,
                amended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (result_id) REFERENCES results(id))''')
    
    # Create default admin user if not exists
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        admin_password = generate_password_hash('admin123')
        c.execute("INSERT INTO users (username, password, role, email) VALUES (?, ?, ?, ?)",
                ('admin', admin_password, 'admin', 'admin@school.com'))
    
    # Add sample subjects if not exists
    subjects = [
        ('MATH101', 'Mathematics', 100),
        ('ENG101', 'English', 100),
        ('SCI101', 'Science', 100),
        ('HIST101', 'History', 100),
        ('CS101', 'Computer Science', 100)
    ]
    for subject in subjects:
        c.execute("INSERT OR IGNORE INTO subjects (subject_code, subject_name, total_marks) VALUES (?, ?, ?)", subject)
    
    # Migration: add unit, course_type, level to subjects table
    try:
        c.execute("ALTER TABLE subjects ADD COLUMN unit INTEGER DEFAULT 3")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE subjects ADD COLUMN course_type TEXT DEFAULT 'CORE'")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE subjects ADD COLUMN level TEXT DEFAULT '300'")
    except sqlite3.OperationalError:
        pass
    
    conn.commit()
    conn.close()

    # Migration: create course_offerings and course_registrations tables
    conn = sqlite3.connect('results.db')
    c = conn.cursor()
    try:
        c.execute('''CREATE TABLE IF NOT EXISTS course_offerings
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject_code TEXT NOT NULL,
                    semester TEXT NOT NULL,
                    academic_year TEXT NOT NULL,
                    max_seats INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (subject_code) REFERENCES subjects(subject_code))''')
    except sqlite3.OperationalError:
        pass

    try:
        c.execute('''CREATE TABLE IF NOT EXISTS course_registrations
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    offering_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(offering_id, student_id),
                    FOREIGN KEY (offering_id) REFERENCES course_offerings(id),
                    FOREIGN KEY (student_id) REFERENCES students(student_id))''')
    except sqlite3.OperationalError:
        pass

    conn.commit()
    try:
        c.execute("ALTER TABLE course_offerings ADD COLUMN teacher_id INTEGER")
    except sqlite3.OperationalError:
        pass

    # Migration: Add score breakdown to results
    for col in ['assignment', 'test1', 'test2', 'exam']:
        try:
            c.execute(f"ALTER TABLE results ADD COLUMN {col} REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session and 'student_id' not in session:
            flash('Please login first', 'error')
            # If the request is for a student route, redirect to student login
            if request.path.startswith('/student'):
                return redirect(url_for('student_login'))
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Role required decorator
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session or session['role'] not in roles:
                flash('Access denied', 'error')
                if session.get('role') == 'student':
                    return redirect(url_for('student_dashboard'))
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator



# Helper function to log actions
def log_action(user, action, details):
    db = get_db()
    c = db.cursor()
    c.execute("INSERT INTO audit_log (user, action, details) VALUES (?, ?, ?)",
            (user, action, details))
    db.commit()

# Email sending helper
def send_result_email(student_email, result_id):
    token = serializer.dumps(result_id, salt='result-view')
    link = url_for('view_student_result', token=token, _external=True)
    
    msg = Message('Your Exam Result is Ready',
                  recipients=[student_email])
    
    msg.body = f"""Hello,

Your result has been published. You can view it by clicking the link below:

{link}

This link captures the state of your result at the time of sending.
"""
    try:
        mail.send(msg)
        return True, "Email sent successfully"
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error sending email: {e}")
        print(f"Details: {error_details}")
        return False, f"Email failed: {str(e)}"


def send_registration_email(student_email, student_name, offering_rows):
    if not student_email:
        return False, 'No email provided'

    subject = 'Course Registration Confirmation'
    lines = [f'Hello {student_name},', '', 'You have successfully registered for the following course(s):', '']
    for o in offering_rows:
        lines.append(f"- {o['subject_name']} ({o['subject_code']}) - {o['semester']} {o['academic_year']}")

    lines.append('')
    lines.append('If you did not perform this action, contact the registrar.')

    msg = Message(subject, recipients=[student_email])
    msg.body = '\n'.join(lines)
    try:
        mail.send(msg)
        return True, 'Email sent'
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print('Error sending registration email:', e)
        print(f"Details: {error_details}")
        return False, f"Registration email failed: {str(e)}"

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if 'student_id' in session:
        return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        db = get_db()
        c = db.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        user = c.fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            log_action(username, 'login', 'User logged in')
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    username = session.get('username', 'Unknown')
    log_action(username, 'logout', 'User logged out')
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

# Student Portal Routes
@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        student_id = request.form['student_id'].strip()
        pin = request.form['pin'].strip()
        
        db = get_db()
        c = db.cursor()
        c.execute("SELECT * FROM students WHERE student_id=?", (student_id,))
        student = c.fetchone()
        
        if student and student['pin'] and check_password_hash(student['pin'], pin):
            session['student_id'] = student['student_id']
            session['student_name'] = student['name']
            session['role'] = 'student'
            log_action(student_id, 'student_login', 'Student logged in')
            flash('Login successful!', 'success')
            return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid Student ID or PIN', 'error')
    
    return render_template('student_login.html')

@app.route('/student/dashboard')
@login_required
@role_required('student')
def student_dashboard():
    student_id = session.get('student_id', '').strip()
    db = get_db()
    c = db.cursor()
    
    # Get student info
    c.execute("""SELECT s.*, d.name as department_name, f.name as faculty_name
                 FROM students s
                 LEFT JOIN departments d ON s.department_id = d.id
                 LEFT JOIN faculties f ON d.faculty_id = f.id
                 WHERE s.student_id=?""", (student_id,))
    student = c.fetchone()
    
    # Get stats
    c.execute("SELECT COUNT(*) as total FROM results WHERE student_id=? AND status='approved'", (student_id,))
    total_results = c.fetchone()['total']
    
    c.execute("SELECT AVG(marks) as avg FROM results WHERE student_id=? AND status='approved'", (student_id,))
    avg_marks = c.fetchone()['avg'] or 0
    
    c.execute("SELECT COUNT(DISTINCT subject_code) as total FROM results WHERE student_id=? AND status='approved'", (student_id,))
    total_subjects = c.fetchone()['total']
    
    c.execute("SELECT academic_year FROM results WHERE student_id=? AND status='approved' ORDER BY academic_year DESC LIMIT 1", (student_id,))
    latest_session = c.fetchone()
    current_session = latest_session['academic_year'] if latest_session else "No Active Session"
    
    return render_template('student_dashboard.html', 
                         student=student,
                         total_results=total_results,
                         avg_marks=round(avg_marks, 2),
                         total_subjects=total_subjects,
                         current_session=current_session)

@app.route('/student/my-results')
@login_required
@role_required('student')
def student_my_results():
    student_id = session.get('student_id', '').strip()
    year_filter = request.args.get('session', '')
    semester_filter = request.args.get('semester', '')
    
    db = get_db()
    c = db.cursor()
    
    # Get available sessions and semesters for this student for the dropdowns
    c.execute("SELECT DISTINCT academic_year FROM results WHERE student_id=? AND status='approved' ORDER BY academic_year DESC", (student_id,))
    sessions = [row['academic_year'] for row in c.fetchall()]
    
    c.execute("SELECT DISTINCT semester FROM results WHERE student_id=? AND status='approved' ORDER BY semester", (student_id,))
    semesters = [row['semester'] for row in c.fetchall()]
    
    # Build query
    query = """SELECT r.*, sub.subject_name, sub.total_marks as max_marks, sub.unit, sub.course_type, sub.level
                 FROM results r
                 JOIN subjects sub ON r.subject_code = sub.subject_code
                 WHERE r.student_id=? AND r.status='approved'"""
    params = [student_id]
    
    if year_filter:
        query += " AND r.academic_year = ?"
        params.append(year_filter)
        
    if semester_filter:
        query += " AND r.semester = ?"
        params.append(semester_filter)
        
    query += " ORDER BY r.academic_year DESC, r.semester, sub.subject_name"
    
    c.execute(query, params)
    raw_results = c.fetchall()

    # Organize results grouped by (academic_year, semester)
    grouped = {}
    for r in raw_results:
        key = (r['academic_year'], r['semester'])
        row = dict(r)
        
        # Ensure default values if subject meta is missing (fallback)
        if not row.get('unit'): row['unit'] = 3
        if not row.get('course_type'): row['course_type'] = 'CORE'
        if not row.get('level'): row['level'] = '100'

        grouped.setdefault(key, []).append(row)

    # Build a list for template consumption
    grouped_results = []
    total_points = 0
    total_cumulative_units = 0
    
    for (academic_year, semester), rows in sorted(grouped.items(), reverse=True):
        semester_units = 0
        semester_points = 0
        for r in rows:
            u = int(r.get('unit') or 0)
            gp = get_grade_points(r.get('grade', 'F'))
            semester_units += u
            semester_points += (u * gp)
            
        semester_gpa = round(semester_points / semester_units, 2) if semester_units > 0 else 0.00
        
        total_points += semester_points
        total_cumulative_units += semester_units
        
        grouped_results.append({
            'academic_year': academic_year,
            'semester': semester,
            'rows': rows,
            'total_courses': len(rows),
            'total_units': semester_units,
            'gpa': semester_gpa
        })

    cgpa = round(total_points / total_cumulative_units, 2) if total_cumulative_units > 0 else 0.00

    # Get AI Recommendations
    ai_recommendations = ai_engine.generate_personalized_recommendations(student_id).get('recommendations', [])
    ai_prediction = ai_engine.predict_performance(student_id).get('prediction', {})

    return render_template('student_my_results.html', 
                         grouped_results=grouped_results,
                         sessions=sessions, 
                         semesters=semesters,
                         selected_session=year_filter,
                         selected_semester=semester_filter,
                         cgpa=cgpa,
                         ai_recommendations=ai_recommendations,
                         ai_prediction=ai_prediction)

@app.route('/student/logout')
def student_logout():
    student_id = session.get('student_id', 'Unknown')
    log_action(student_id, 'student_logout', 'Student logged out')
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('student_login'))


@app.route('/student/register', methods=['GET', 'POST'])
def student_register():
    db = get_db()
    c = db.cursor()
    if request.method == 'POST':
        student_id = request.form['student_id'].strip()
        name = request.form['name'].strip()
        email = request.form.get('email', '').strip()
        class_name = request.form.get('class', '').strip()
        department_id = request.form.get('department_id') or None
        pin = request.form.get('pin', '').strip()

        if not student_id or not name or not pin:
            flash('Please provide Student ID, name and PIN', 'error')
            return redirect(url_for('student_register'))

        hashed_pin = generate_password_hash(pin)
        try:
            c.execute("INSERT INTO students (student_id, name, email, class, department_id, pin) VALUES (?, ?, ?, ?, ?, ?)",
                      (student_id, name, email, class_name, department_id, hashed_pin))
            db.commit()
            log_action(student_id, 'student_register', f'Student registered: {name} ({student_id})')
            flash('Registration successful! You can now login using your Student ID and PIN.', 'success')
            return redirect(url_for('student_login'))
        except sqlite3.IntegrityError:
            flash('Student ID already exists. If you already registered, please login.', 'error')

    # fetch departments for dropdown
    c.execute("SELECT id, name FROM departments ORDER BY name")
    departments = c.fetchall()
    return render_template('student_register.html', departments=departments)

@app.route('/dashboard')
@login_required
def dashboard():
    # Role-based dashboard redirect
    if session.get('role') == 'teacher':
        return redirect(url_for('teacher_dashboard'))
        
    db = get_db()
    c = db.cursor()
    
    # Fetch stats
    c.execute("SELECT COUNT(*) FROM students")
    total_students = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM subjects")
    total_subjects = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM results")
    total_results = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM results WHERE status='pending'")
    pending_results = c.fetchone()[0]
    
    # Fetch recent activities
    c.execute("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 10")
    recent_activities = c.fetchall()
    
    return render_template('dashboard.html', 
                         total_students=total_students, 
                         total_subjects=total_subjects, 
                         total_results=total_results, 
                         pending_results=pending_results,
                         recent_activities=recent_activities)


@app.route('/teacher/dashboard')
@login_required
@role_required('teacher', 'staff') # Allow both just in case
def teacher_dashboard():
    db = get_db()
    c = db.cursor()
    user_id = session.get('user_id')
    
    # Fetch assigned offerings
    c.execute("""
        SELECT o.*, s.subject_name 
        FROM course_offerings o 
        JOIN subjects s ON o.subject_code = s.subject_code 
        WHERE o.teacher_id = ?
        ORDER BY o.academic_year DESC, o.semester
    """, (user_id,))
    courses = c.fetchall()
    
    return render_template('teacher_dashboard.html', courses=courses)


@app.route('/teacher/grade/<int:offering_id>', methods=['GET', 'POST'])
@login_required
@role_required('teacher', 'staff')
def grade_course(offering_id):
    db = get_db()
    c = db.cursor()
    
    # Verify assignment
    c.execute("SELECT * FROM course_offerings WHERE id=? AND teacher_id=?", (offering_id, session.get('user_id')))
    offering = c.fetchone()
    if not offering:
        flash('You are not assigned to this course.', 'error')
        return redirect(url_for('teacher_dashboard'))
    
    # Get subject details
    c.execute("SELECT subject_name FROM subjects WHERE subject_code=?", (offering['subject_code'],))
    subject = c.fetchone()
    
    if request.method == 'POST':
        count = 0
        try:
            # Iterate student IDs from form
            student_ids = request.form.getlist('student_id[]')
            
            for sid in student_ids:
                assignment = float(request.form.get(f'assignment_{sid}', 0))
                test1 = float(request.form.get(f'test1_{sid}', 0))
                test2 = float(request.form.get(f'test2_{sid}', 0))
                exam = float(request.form.get(f'exam_{sid}', 0))
                
                # Validation
                if not (0 <= assignment <= 20 and 0 <= test1 <= 20 and 0 <= test2 <= 20 and 0 <= exam <= 40):
                    flash(f'Invalid scores for student {sid}. Max scores: Assign(20), Test(20), Exam(40).', 'warning')
                    continue

                total = assignment + test1 + test2 + exam
                grade = calculate_grade(total)
                
                timestamp = datetime.now()

                # Check if result exists
                c.execute("SELECT id FROM results WHERE student_id=? AND subject_code=? AND semester=? AND academic_year=?",
                         (sid, offering['subject_code'], offering['semester'], offering['academic_year']))
                existing = c.fetchone()
                
                if existing:
                    c.execute("""UPDATE results SET 
                        marks=?, grade=?, assignment=?, test1=?, test2=?, exam=?, approved_by=?, approved_at=? 
                        WHERE id=?""", 
                        (total, grade, assignment, test1, test2, exam, session['username'], timestamp, existing['id']))
                else:
                    c.execute("""INSERT INTO results 
                        (student_id, subject_code, marks, grade, assignment, test1, test2, exam, semester, academic_year, created_by, status, approved_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved', ?)""",
                        (sid, offering['subject_code'], total, grade, assignment, test1, test2, exam, 
                         offering['semester'], offering['academic_year'], session['username'], timestamp))
                count += 1
            
            db.commit()
            flash(f'Updated grades for {count} students.', 'success')
            
        except ValueError:
            flash('Invalid score value entered.', 'error')
        except sqlite3.Error as e:
            flash(f'Database error: {e}', 'error')
            
    # Fetch registered students OR students in the class associated with the subject
    query = """
        SELECT DISTINCT s.student_id, s.name, r.assignment, r.test1, r.test2, r.exam, r.marks
        FROM students s
        LEFT JOIN course_registrations cr ON s.student_id = cr.student_id AND cr.offering_id = ?
        LEFT JOIN results r ON s.student_id = r.student_id 
            AND r.subject_code = ? 
            AND r.semester = ? 
            AND r.academic_year = ?
        WHERE cr.offering_id IS NOT NULL 
           OR s.class = (
                SELECT c.class_name 
                FROM subjects sub 
                JOIN classes c ON sub.class_id = c.id 
                WHERE sub.subject_code = ?
           )
        ORDER BY s.name
    """
    c.execute(query, (offering_id, offering['subject_code'], offering['semester'], offering['academic_year'], offering['subject_code']))
    students = c.fetchall()
    
    return render_template('grade_course.html', offering=offering, subject=subject, students=students)


# Admin: Course Offerings (create offerings per semester/session)
@app.route('/offerings')
@login_required
@role_required('admin')
def offerings():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT o.*, s.subject_name FROM course_offerings o JOIN subjects s ON o.subject_code = s.subject_code ORDER BY o.academic_year DESC, o.semester")
    raw = c.fetchall()
    offerings = []
    for o in raw:
        c.execute("SELECT COUNT(*) as cnt FROM course_registrations WHERE offering_id=?", (o['id'],))
        cnt = c.fetchone()['cnt']
        try:
            max_seats = int(o['max_seats'] or 0)
        except Exception:
            max_seats = 0
        remaining = None
        if max_seats > 0:
            remaining = max_seats - cnt
        od = dict(o)
        od['registered_count'] = cnt
        od['remaining_seats'] = remaining
        offerings.append(od)
    # fetch subjects for add form
    c.execute("SELECT subject_code, subject_name FROM subjects ORDER BY subject_name")
    subjects = c.fetchall()
    
    # fetch classes for bulk add
    c.execute("SELECT * FROM classes ORDER BY class_name")
    classes = c.fetchall()

    # fetch teachers
    c.execute("SELECT id, username FROM users WHERE role='teacher' ORDER BY username")
    teachers = c.fetchall()
    
    return render_template('offerings.html', offerings=offerings, subjects=subjects, classes=classes, teachers=teachers)


@app.route('/offerings/add', methods=['POST'])
@login_required
@role_required('admin')
def add_offering():
    subject_codes = request.form.getlist('subject_code')
    semester = request.form['semester']
    academic_year = request.form['academic_year']
    teacher_id = request.form.get('teacher_id') # Optional

    db = get_db()
    c = db.cursor()
    
    count = 0
    errors = 0
    
    for code in subject_codes:
        try:
            c.execute("INSERT INTO course_offerings (subject_code, semester, academic_year, max_seats, teacher_id) VALUES (?, ?, ?, 0, ?)",
                      (code, semester, academic_year, teacher_id))
            count += 1
        except sqlite3.Error:
            errors += 1
            
    db.commit()
    
    if count > 0:
        flash(f'{count} course offering(s) created', 'success')
    if errors > 0:
        flash(f'{errors} offering(s) failed (duplicates?)', 'warning')
        
    return redirect(url_for('offerings'))


@app.route('/offerings/delete/<int:offering_id>')
@login_required
@role_required('admin')
def delete_offering(offering_id):
    db = get_db()
    c = db.cursor()
    try:
        c.execute("DELETE FROM course_registrations WHERE offering_id=?", (offering_id,))
        c.execute("DELETE FROM course_offerings WHERE id=?", (offering_id,))
        db.commit()
        flash('Offering deleted', 'success')
    except sqlite3.Error as e:
        flash(f'Error deleting offering: {e}', 'error')
    return redirect(url_for('offerings'))


@app.route('/offerings/bulk-add', methods=['POST'])
@login_required
@role_required('admin')
def bulk_add_offering():
    class_id = request.form['class_id']
    semester = request.form['semester']
    academic_year = request.form['academic_year']
    max_seats = request.form.get('max_seats') or 0
    teacher_id = request.form.get('teacher_id')
    
    db = get_db()
    c = db.cursor()
    
    # Get all subjects for this class
    c.execute("SELECT subject_code FROM subjects WHERE class_id=?", (class_id,))
    subjects = c.fetchall()
    
    if not subjects:
        flash('No subjects found for this class.', 'error')
        return redirect(url_for('offerings'))
        
    count = 0
    errors = 0
    
    for s in subjects:
        try:
            # Check if offering already exists
            c.execute("SELECT id FROM course_offerings WHERE subject_code=? AND semester=? AND academic_year=?",
                     (s['subject_code'], semester, academic_year))
            if not c.fetchone():
                c.execute("INSERT INTO course_offerings (subject_code, semester, academic_year, max_seats, teacher_id) VALUES (?, ?, ?, ?, ?)",
                        (s['subject_code'], semester, academic_year, int(max_seats), teacher_id))
                count += 1
        except sqlite3.Error:
            errors += 1
            
    db.commit()
    
    if count > 0:
        flash(f'Successfully added {count} offerings.', 'success')
    if errors > 0:
        flash(f'Skipped {errors} subjects due to errors.', 'warning')
    if count == 0 and errors == 0:
        flash('All subjects for this class are already assigned to this session.', 'info')
        
    return redirect(url_for('offerings'))


@app.route('/admin/registrations')
@login_required
@role_required('admin')
def admin_registrations():
    db = get_db()
    c = db.cursor()
    
    student_filter = request.args.get('student_id', '').strip()
    session_filter = request.args.get('session', '').strip()
    semester_filter = request.args.get('semester', '').strip()
    
    query = """
        SELECT cr.id as reg_id, cr.registered_at, s.student_id, s.name as student_name, 
               o.subject_code, sub.subject_name, o.semester, o.academic_year
        FROM course_registrations cr
        JOIN students s ON cr.student_id = s.student_id
        JOIN course_offerings o ON cr.offering_id = o.id
        JOIN subjects sub ON o.subject_code = sub.subject_code
        WHERE 1=1
    """
    params = []
    
    if student_filter:
        query += " AND (s.student_id LIKE ? OR s.name LIKE ?)"
        params.extend([f'%{student_filter}%', f'%{student_filter}%'])
    if session_filter:
        query += " AND o.academic_year = ?"
        params.append(session_filter)
    if semester_filter:
        query += " AND o.semester = ?"
        params.append(semester_filter)
        
    query += " ORDER BY cr.registered_at DESC"
    
    c.execute(query, params)
    registrations = c.fetchall()
    
    # Fetch sessions/semesters for filters
    c.execute("SELECT DISTINCT academic_year FROM course_offerings ORDER BY academic_year DESC")
    sessions = [r['academic_year'] for r in c.fetchall()]
    c.execute("SELECT DISTINCT semester FROM course_offerings ORDER BY semester")
    semesters = [r['semester'] for r in c.fetchall()]
    
    return render_template('admin_registrations.html', registrations=registrations, 
                         sessions=sessions, semesters=semesters,
                         selected_session=session_filter, selected_semester=semester_filter,
                         search=student_filter)


@app.route('/admin/registrations/delete/<int:reg_id>')
@login_required
@role_required('admin')
def admin_delete_registration(reg_id):
    db = get_db()
    c = db.cursor()
    try:
        # Get details for logging before delete
        c.execute("""
            SELECT s.name, o.subject_code 
            FROM course_registrations cr
            JOIN students s ON cr.student_id = s.student_id
            JOIN course_offerings o ON cr.offering_id = o.id
            WHERE cr.id = ?
        """, (reg_id,))
        reg = c.fetchone()
        
        if reg:
            c.execute("DELETE FROM course_registrations WHERE id = ?", (reg_id,))
            db.commit()
            log_action(session['username'], 'delete_registration', 
                      f"Deleted registration for {reg['name']} - {reg['subject_code']}")
            flash('Registration deleted successfully', 'success')
        else:
            flash('Registration not found', 'error')
    except sqlite3.Error as e:
        flash(f'Error deleting registration: {e}', 'error')
        
    return redirect(url_for('admin_registrations'))


# Student: register for courses (per offering)
@app.route('/student/course-register', methods=['GET', 'POST'])
@login_required
@role_required('student')
def student_course_register():
    db = get_db()
    c = db.cursor()
    student_id = session.get('student_id', '').strip()

    if request.method == 'POST':
        selected = request.form.getlist('offering')
        
        if not selected:
             flash("No courses selected. Please select at least one course.", "warning")
             return redirect(url_for('student_course_register'))

        successful = []
        failed_full = []
        already = []

        # get current regs for student
        c.execute("SELECT offering_id FROM course_registrations WHERE student_id=?", (student_id,))
        current_regs = {row['offering_id'] for row in c.fetchall()}

        for oid in selected:
            try:
                oid_i = int(oid)
            except ValueError:
                continue

            if oid_i in current_regs:
                already.append(oid_i)
                continue

            # check max seats - REMOVED
            # c.execute("SELECT max_seats FROM course_offerings WHERE id=?", (oid_i,))
            # offering = c.fetchone()
            # if not offering:
            #     continue
            # max_seats = offering['max_seats'] or 0

            # if max_seats > 0:
            #     c.execute("SELECT COUNT(*) as cnt FROM course_registrations WHERE offering_id=?", (oid_i,))
            #     cnt = c.fetchone()['cnt']
            #     if cnt >= max_seats:
            #         failed_full.append(oid_i)
            #         continue

            try:
                c.execute("INSERT INTO course_registrations (offering_id, student_id) VALUES (?, ?)", (oid_i, student_id))
                successful.append(oid_i)
            except sqlite3.IntegrityError:
                # Already registered (constraint failed)
                already.append(oid_i)
            except sqlite3.Error as e:
                # Catch other DB errors and flash them for debugging
                flash(f"Error registering for course {oid_i}: {e}", "error")
                pass

        db.commit()

        msg_parts = []
        if successful:
            msg_parts.append(f"Registered for {len(successful)} course(s)")
            # store for confirmation page
            session['last_registered_offerings'] = successful
            # send email confirmation if student has email
            c.execute("SELECT email, name FROM students WHERE student_id=?", (student_id,))
            s = c.fetchone()
            if s and s['email']:
                # fetch offering rows
                q = f"SELECT o.*, sub.subject_name FROM course_offerings o JOIN subjects sub ON o.subject_code=sub.subject_code WHERE o.id IN ({','.join(['?']*len(successful))})"
                c.execute(q, tuple(successful))
                offering_rows = c.fetchall()
                sent, sent_msg = send_registration_email(s['email'], s['name'], offering_rows)
                if sent:
                    msg_parts.append('Confirmation email sent')
                else:
                    msg_parts.append('Email send failed')

        if already:
            msg_parts.append(f"Already registered for {len(already)} course(s)")

        if failed_full:
            msg_parts.append(f"{len(failed_full)} course(s) were full and skipped")

        flash('; '.join(msg_parts) or 'No selections processed', 'success')
        if successful:
            return redirect(url_for('registration_confirmation'))
        return redirect(url_for('student_course_register'))

    # filters
    semester = request.args.get('semester', '')
    academic_year = request.args.get('session', '')
    class_id = request.args.get('class', '')

    query = "SELECT o.*, s.subject_name FROM course_offerings o JOIN subjects s ON o.subject_code = s.subject_code WHERE 1=1"
    params = []
    if semester:
        query += " AND o.semester = ?"
        params.append(semester)
    if academic_year:
        query += " AND o.academic_year = ?"
        params.append(academic_year)
    if class_id:
        query += " AND s.class_id = ?"
        params.append(class_id)
        
    query += " ORDER BY o.academic_year DESC, o.semester"

    c.execute(query, params)
    offerings = c.fetchall()

    # fetch student's current registrations
    c.execute("SELECT offering_id FROM course_registrations WHERE student_id=?", (student_id,))
    regs = {row['offering_id'] for row in c.fetchall()}

    # annotate offerings with registration counts and remaining seats
    annotated = []
    for o in offerings:
        c.execute("SELECT COUNT(*) as cnt FROM course_registrations WHERE offering_id=?", (o['id'],))
        cnt = c.fetchone()['cnt']
        remaining = None
        try:
            max_seats = int(o['max_seats'] or 0)
        except Exception:
            max_seats = 0
        if max_seats > 0:
            remaining = max_seats - cnt
        else:
            remaining = None
        od = dict(o)
        od['registered_count'] = cnt
        od['remaining_seats'] = remaining
        annotated.append(od)

    offerings = annotated

    # fetch available sessions/semesters
    c.execute("SELECT DISTINCT academic_year FROM course_offerings ORDER BY academic_year DESC")
    sessions = [r['academic_year'] for r in c.fetchall()]
    c.execute("SELECT DISTINCT semester FROM course_offerings ORDER BY semester")
    semesters = [r['semester'] for r in c.fetchall()]
    
    # fetch classes
    c.execute("SELECT * FROM classes ORDER BY class_name")
    classes = c.fetchall()

    return render_template('student_course_register.html', offerings=offerings, regs=regs, sessions=sessions, semesters=semesters, classes=classes, selected_session=academic_year, selected_semester=semester, selected_class=class_id)


@app.route('/student/my-courses')
@login_required
@role_required('student')
def student_my_courses():
    student_id = session.get('student_id', '').strip()
    db = get_db()
    c = db.cursor()
    
    # Get all registrations for this student
    query = """
        SELECT cr.id as reg_id, o.*, s.subject_name, s.unit, s.course_type, s.level 
        FROM course_registrations cr
        JOIN course_offerings o ON cr.offering_id = o.id
        JOIN subjects s ON o.subject_code = s.subject_code
        WHERE cr.student_id = ?
        ORDER BY o.academic_year DESC, o.semester DESC, s.subject_name
    """
    c.execute(query, (student_id,))
    registrations = c.fetchall()
    
    # Group by session and semester
    grouped = {}
    for r in registrations:
        key = (r['academic_year'], r['semester'])
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(r)
        
    return render_template('student_my_courses.html', grouped_registrations=grouped)


@app.route('/student/registration-confirmation')
@login_required
@role_required('student')
def registration_confirmation():
    db = get_db()
    c = db.cursor()
    last = session.pop('last_registered_offerings', [])
    offerings = []
    if last:
        q = f"SELECT o.*, s.subject_name, s.unit FROM course_offerings o JOIN subjects s ON o.subject_code = s.subject_code WHERE o.id IN ({','.join(['?']*len(last))})"
        c.execute(q, tuple(last))
        offerings = c.fetchall()
        
    student_id = session.get('student_id', '').strip()
    c.execute("SELECT * FROM students WHERE student_id=?", (student_id,))
    student = c.fetchone()
    
    return render_template('registration_confirmation.html', offerings=offerings, student=student)

@app.route('/students')
@login_required
@role_required('admin', 'teacher')
def students():
    db = get_db()
    c = db.cursor()
    c.execute("""SELECT s.*, d.name as department_name, f.name as faculty_name 
                 FROM students s
                 LEFT JOIN departments d ON s.department_id = d.id
                 LEFT JOIN faculties f ON d.faculty_id = f.id
                 ORDER BY s.name""")
    students = c.fetchall()
    return render_template('students.html', students=students)

@app.route('/students/add', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'teacher')
def add_student():
    db = get_db()
    c = db.cursor()
    
    if request.method == 'POST':
        student_id = request.form['student_id'].strip()
        name = request.form['name'].strip()
        email = request.form['email']
        class_name = request.form['class']
        department_id = request.form['department_id']
        pin = request.form.get('pin', '')
        
        # Hash PIN if provided
        hashed_pin = generate_password_hash(pin) if pin else None
        
        try:
            c.execute("INSERT INTO students (student_id, name, email, class, department_id, pin) VALUES (?, ?, ?, ?, ?, ?)",
                    (student_id, name, email, class_name, department_id, hashed_pin))
            db.commit()
            
            log_action(session['username'], 'add_student', f'Added student: {name} ({student_id})')
            flash('Student added successfully!', 'success')
            return redirect(url_for('students'))
        except sqlite3.IntegrityError:
            flash('Student ID already exists', 'error')
            
    # Fetch departments
    c.execute("""SELECT d.id, d.name as dept_name, f.name as faculty_name 
                 FROM departments d 
                 JOIN faculties f ON d.faculty_id = f.id 
                 ORDER BY f.name, d.name""")
    departments = c.fetchall()
    
    return render_template('add_student.html', departments=departments)

@app.route('/students/edit/<path:student_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'teacher')
def edit_student(student_id):
    db = get_db()
    c = db.cursor()
    
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        class_name = request.form['class']
        department_id = request.form['department_id']
        pin = request.form.get('pin', '')
        
        try:
            # Update PIN only if provided
            if pin:
                hashed_pin = generate_password_hash(pin)
                c.execute("UPDATE students SET name=?, email=?, class=?, department_id=?, pin=? WHERE student_id=?",
                        (name, email, class_name, department_id, hashed_pin, student_id))
            else:
                c.execute("UPDATE students SET name=?, email=?, class=?, department_id=? WHERE student_id=?",
                        (name, email, class_name, department_id, student_id))
            db.commit()
            
            log_action(session['username'], 'edit_student', f'Edited student: {name} ({student_id})')
            flash('Student updated successfully!', 'success')
            return redirect(url_for('students'))
        except sqlite3.Error as e:
            flash(f'An error occurred: {e}', 'error')
            
    c.execute("SELECT * FROM students WHERE student_id=?", (student_id,))
    student = c.fetchone()
    
    if not student:
        flash('Student not found', 'error')
        return redirect(url_for('students'))
    
    # Fetch departments
    c.execute("""SELECT d.id, d.name as dept_name, f.name as faculty_name 
                 FROM departments d 
                 JOIN faculties f ON d.faculty_id = f.id 
                 ORDER BY f.name, d.name""")
    departments = c.fetchall()
        
    return render_template('edit_student.html', student=student, departments=departments)

@app.route('/students/delete/<path:student_id>')
@login_required
@role_required('admin', 'teacher')
def delete_student(student_id):
    db = get_db()
    c = db.cursor()
    
    try:
        # Check for existing results first to give better error message
        c.execute("SELECT COUNT(*) as count FROM results WHERE student_id=?", (student_id,))
        if c.fetchone()['count'] > 0:
            flash('Cannot delete student with existing results. Please delete their results first.', 'error')
            return redirect(url_for('students'))

        c.execute("SELECT name FROM students WHERE student_id=?", (student_id,))
        student = c.fetchone()
        
        if student:
            name = student['name']
            c.execute("DELETE FROM students WHERE student_id=?", (student_id,))
            db.commit()
            log_action(session['username'], 'delete_student', f'Deleted student: {name} ({student_id})')
            flash('Student deleted successfully!', 'success')
        else:
            flash('Student not found', 'error')
            
    except sqlite3.IntegrityError:
        flash('Cannot delete student. They may have related records.', 'error')
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
        
    return redirect(url_for('students'))

@app.route('/subjects')
@login_required
@role_required('admin', 'teacher')
def subjects():
    db = get_db()
    c = db.cursor()
    c.execute("""SELECT s.*, c.class_name, d.name as department_name, f.name as faculty_name 
                FROM subjects s 
                LEFT JOIN classes c ON s.class_id = c.id
                LEFT JOIN departments d ON s.department_id = d.id
                LEFT JOIN faculties f ON d.faculty_id = f.id
                ORDER BY c.class_name, s.subject_name""")
    subjects = c.fetchall()
    return render_template('subjects.html', subjects=subjects)

@app.route('/subjects/add', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def add_subject():
    if request.method == 'POST':
        subject_code = request.form['subject_code']
        subject_name = request.form['subject_name']
        total_marks = request.form['total_marks']
        class_id = request.form['class_id']
        department_id = request.form['department_id']
        
        unit = request.form['unit']
        
        try:
            db = get_db()
            c = db.cursor()
            c.execute("INSERT INTO subjects (subject_code, subject_name, total_marks, class_id, department_id, unit) VALUES (?, ?, ?, ?, ?, ?)",
                    (subject_code, subject_name, total_marks, class_id, department_id, unit))
            db.commit()
            
            log_action(session['username'], 'add_subject', f'Added subject: {subject_name} ({subject_code})')
            flash('Subject added successfully!', 'success')
            return redirect(url_for('subjects'))
        except sqlite3.IntegrityError:
            flash('Subject code already exists', 'error')
    
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM classes ORDER BY class_name")
    classes = c.fetchall()
    
    # Fetch departments
    c.execute("""SELECT d.id, d.name as dept_name, f.name as faculty_name 
                 FROM departments d 
                 JOIN faculties f ON d.faculty_id = f.id 
                 ORDER BY f.name, d.name""")
    departments = c.fetchall()
    
    return render_template('add_subject.html', classes=classes, departments=departments)

@app.route('/subjects/edit/<path:subject_code>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit_subject(subject_code):
    db = get_db()
    c = db.cursor()
    
    if request.method == 'POST':
        subject_name = request.form['subject_name']
        total_marks = request.form['total_marks']
        class_id = request.form['class_id']
        department_id = request.form['department_id']
        
        unit = request.form['unit']
        
        try:
            c.execute("""UPDATE subjects SET subject_name=?, total_marks=?, class_id=?, department_id=?, unit=? 
                        WHERE subject_code=?""",
                    (subject_name, total_marks, class_id, department_id, unit, subject_code))
            db.commit()
            
            log_action(session['username'], 'edit_subject', f'Edited subject: {subject_name} ({subject_code})')
            flash('Subject updated successfully!', 'success')
            return redirect(url_for('subjects'))
        except sqlite3.Error as e:
            flash(f'An error occurred: {e}', 'error')
    
    c.execute("SELECT * FROM subjects WHERE subject_code=?", (subject_code,))
    subject = c.fetchone()
    
    if not subject:
        flash('Subject not found', 'error')
        return redirect(url_for('subjects'))
    
    c.execute("SELECT * FROM classes ORDER BY class_name")
    classes = c.fetchall()
    
    c.execute("""SELECT d.id, d.name as dept_name, f.name as faculty_name 
                 FROM departments d 
                 JOIN faculties f ON d.faculty_id = f.id 
                 ORDER BY f.name, d.name""")
    departments = c.fetchall()
    
    return render_template('edit_subject.html', subject=subject, classes=classes, departments=departments)

@app.route('/subjects/delete/<path:subject_code>')
@login_required
@role_required('admin')
def delete_subject(subject_code):
    db = get_db()
    c = db.cursor()
    
    try:
        # Check for existing results
        c.execute("SELECT COUNT(*) as count FROM results WHERE subject_code=?", (subject_code,))
        if c.fetchone()['count'] > 0:
            flash('Cannot delete subject with existing results. Please delete results first.', 'error')
            return redirect(url_for('subjects'))
        
        c.execute("SELECT subject_name FROM subjects WHERE subject_code=?", (subject_code,))
        subject = c.fetchone()
        
        if subject:
            name = subject['subject_name']
            c.execute("DELETE FROM subjects WHERE subject_code=?", (subject_code,))
            db.commit()
            log_action(session['username'], 'delete_subject', f'Deleted subject: {name} ({subject_code})')
            flash('Subject deleted successfully!', 'success')
        else:
            flash('Subject not found', 'error')
    except sqlite3.Error as e:
        flash(f'An error occurred: {str(e)}', 'error')
    
    return redirect(url_for('subjects'))

@app.route('/classes')
@login_required
@role_required('admin', 'teacher')
def classes():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM classes ORDER BY class_name")
    classes = c.fetchall()
    return render_template('classes.html', classes=classes)

@app.route('/classes/add', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def add_class():
    if request.method == 'POST':
        class_name = request.form['class_name']
        try:
            db = get_db()
            c = db.cursor()
            c.execute("INSERT INTO classes (class_name) VALUES (?)", (class_name,))
            db.commit()
            log_action(session['username'], 'add_class', f'Added class: {class_name}')
            flash('Class added successfully!', 'success')
            return redirect(url_for('classes'))
        except sqlite3.IntegrityError:
            flash('Class already exists', 'error')
            
    return render_template('add_class.html')

@app.route('/classes/edit/<int:class_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit_class(class_id):
    db = get_db()
    c = db.cursor()
    
    if request.method == 'POST':
        class_name = request.form['class_name']
        
        try:
            c.execute("UPDATE classes SET class_name=? WHERE id=?", (class_name, class_id))
            db.commit()
            log_action(session['username'], 'edit_class', f'Edited class: {class_name}')
            flash('Class updated successfully!', 'success')
            return redirect(url_for('classes'))
        except sqlite3.IntegrityError:
            flash('Class name already exists', 'error')
        except sqlite3.Error as e:
            flash(f'An error occurred: {e}', 'error')
    
    c.execute("SELECT * FROM classes WHERE id=?", (class_id,))
    cls = c.fetchone()
    
    if not cls:
        flash('Class not found', 'error')
        return redirect(url_for('classes'))
    
    return render_template('edit_class.html', cls=cls)

@app.route('/classes/delete/<int:class_id>')
@login_required
@role_required('admin')
def delete_class(class_id):
    db = get_db()
    c = db.cursor()
    
    # Check if used in subjects
    c.execute("SELECT COUNT(*) as count FROM subjects WHERE class_id=?", (class_id,))
    if c.fetchone()['count'] > 0:
        flash('Cannot delete class. It has associated subjects.', 'error')
        return redirect(url_for('classes'))
        
    c.execute("DELETE FROM classes WHERE id=?", (class_id,))
    db.commit()
    log_action(session['username'], 'delete_class', f'Deleted class ID: {class_id}')
    flash('Class deleted successfully!', 'success')
    return redirect(url_for('classes'))

# Faculty Routes
@app.route('/faculties')
@login_required
@role_required('admin')
def faculties():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM faculties ORDER BY name")
    faculties = c.fetchall()
    return render_template('faculties.html', faculties=faculties)

@app.route('/faculties/add', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def add_faculty():
    if request.method == 'POST':
        name = request.form['name']
        try:
            db = get_db()
            c = db.cursor()
            c.execute("INSERT INTO faculties (name) VALUES (?)", (name,))
            db.commit()
            log_action(session['username'], 'add_faculty', f'Added faculty: {name}')
            flash('Faculty added successfully!', 'success')
            return redirect(url_for('faculties'))
        except sqlite3.IntegrityError:
            flash('Faculty already exists', 'error')
    return render_template('add_faculty.html')

@app.route('/faculties/edit/<int:faculty_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit_faculty(faculty_id):
    db = get_db()
    c = db.cursor()
    
    if request.method == 'POST':
        name = request.form['name']
        
        try:
            c.execute("UPDATE faculties SET name=? WHERE id=?", (name, faculty_id))
            db.commit()
            log_action(session['username'], 'edit_faculty', f'Edited faculty: {name}')
            flash('Faculty updated successfully!', 'success')
            return redirect(url_for('faculties'))
        except sqlite3.IntegrityError:
            flash('Faculty name already exists', 'error')
        except sqlite3.Error as e:
            flash(f'An error occurred: {e}', 'error')
    
    c.execute("SELECT * FROM faculties WHERE id=?", (faculty_id,))
    faculty = c.fetchone()
    
    if not faculty:
        flash('Faculty not found', 'error')
        return redirect(url_for('faculties'))
    
    return render_template('edit_faculty.html', faculty=faculty)

@app.route('/faculties/delete/<int:faculty_id>')
@login_required
@role_required('admin')
def delete_faculty(faculty_id):
    db = get_db()
    c = db.cursor()
    # Check dependencies
    c.execute("SELECT COUNT(*) as count FROM departments WHERE faculty_id=?", (faculty_id,))
    if c.fetchone()['count'] > 0:
        flash('Cannot delete faculty with associated departments.', 'error')
        return redirect(url_for('faculties'))
    c.execute("DELETE FROM faculties WHERE id=?", (faculty_id,))
    db.commit()
    log_action(session['username'], 'delete_faculty', f'Deleted faculty ID: {faculty_id}')
    flash('Faculty deleted successfully!', 'success')
    return redirect(url_for('faculties'))

# Department Routes
@app.route('/departments')
@login_required
@role_required('admin')
def departments():
    db = get_db()
    c = db.cursor()
    c.execute("""SELECT d.*, f.name as faculty_name 
                 FROM departments d 
                 LEFT JOIN faculties f ON d.faculty_id = f.id 
                 ORDER BY f.name, d.name""")
    departments = c.fetchall()
    return render_template('departments.html', departments=departments)

@app.route('/departments/add', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def add_department():
    db = get_db()
    c = db.cursor()
    if request.method == 'POST':
        name = request.form['name']
        faculty_id = request.form['faculty_id']
        try:
            c.execute("INSERT INTO departments (name, faculty_id) VALUES (?, ?)", (name, faculty_id))
            db.commit()
            log_action(session['username'], 'add_department', f'Added department: {name}')
            flash('Department added successfully!', 'success')
            return redirect(url_for('departments'))
        except sqlite3.IntegrityError:
            flash('Department already exists', 'error')
            
    c.execute("SELECT * FROM faculties ORDER BY name")
    faculties = c.fetchall()
    return render_template('add_department.html', faculties=faculties)

@app.route('/departments/edit/<int:dept_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit_department(dept_id):
    db = get_db()
    c = db.cursor()
    
    if request.method == 'POST':
        name = request.form['name']
        faculty_id = request.form['faculty_id']
        
        try:
            c.execute("UPDATE departments SET name=?, faculty_id=? WHERE id=?", 
                     (name, faculty_id, dept_id))
            db.commit()
            log_action(session['username'], 'edit_department', f'Edited department: {name}')
            flash('Department updated successfully!', 'success')
            return redirect(url_for('departments'))
        except sqlite3.IntegrityError:
            flash('Department name already exists', 'error')
        except sqlite3.Error as e:
            flash(f'An error occurred: {e}', 'error')
    
    c.execute("SELECT * FROM departments WHERE id=?", (dept_id,))
    department = c.fetchone()
    
    if not department:
        flash('Department not found', 'error')
        return redirect(url_for('departments'))
    
    c.execute("SELECT * FROM faculties ORDER BY name")
    faculties = c.fetchall()
    
    return render_template('edit_department.html', department=department, faculties=faculties)

@app.route('/departments/delete/<int:dept_id>')
@login_required
@role_required('admin')
def delete_department(dept_id):
    db = get_db()
    c = db.cursor()
    # Check dependencies (students, subjects)
    c.execute("SELECT COUNT(*) as count FROM students WHERE department_id=?", (dept_id,))
    if c.fetchone()['count'] > 0:
        flash('Cannot delete department with associated students.', 'error')
        return redirect(url_for('departments'))
        
    c.execute("DELETE FROM departments WHERE id=?", (dept_id,))
    db.commit()
    log_action(session['username'], 'delete_department', f'Deleted department ID: {dept_id}')
    flash('Department deleted successfully!', 'success')
    return redirect(url_for('departments'))

@app.route('/results')
@login_required
@role_required('admin', 'teacher')
def results():
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    class_filter = request.args.get('class', '')
    year_filter = request.args.get('academic_year', '')
    semester_filter = request.args.get('semester', '')
    
    db = get_db()
    c = db.cursor()
    
    query = """SELECT r.*, s.name as student_name, s.class, sub.subject_name 
            FROM results r
            JOIN students s ON r.student_id = s.student_id
            JOIN subjects sub ON r.subject_code = sub.subject_code
            WHERE 1=1"""
    params = []
    
    if search:
        query += " AND (s.name LIKE ? OR r.student_id LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    
    if status_filter:
        query += " AND r.status = ?"
        params.append(status_filter)
    
    if class_filter:
        query += " AND s.class = ?"
        params.append(class_filter)

    if year_filter:
        query += " AND r.academic_year = ?"
        params.append(year_filter)

    if semester_filter:
        query += " AND r.semester = ?"
        params.append(semester_filter)
    
    query += " ORDER BY r.created_at DESC"
    
    c.execute(query, params)
    results = c.fetchall()
    
    # Get unique classes for filter
    c.execute("SELECT DISTINCT class FROM students ORDER BY class")
    classes = c.fetchall()

    # Get unique semesters for filter
    c.execute("SELECT DISTINCT semester FROM results ORDER BY semester")
    semesters = [row['semester'] for row in c.fetchall()]
    
    return render_template('results.html', results=results, classes=classes, 
                        semesters=semesters, search=search, status_filter=status_filter, 
                        class_filter=class_filter, year_filter=year_filter, 
                        semester_filter=semester_filter)

@app.route('/results/add', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'teacher')
def add_result():
    if request.method == 'POST':
        student_id = request.form['student_id']
        subject_code = request.form['subject_code']
        try:
            marks = float(request.form['marks'])
        except ValueError:
            flash('Invalid marks value. Please enter a number.', 'error')
            return redirect(url_for('add_result'))
            
        semester = request.form['semester']
        academic_year = request.form['academic_year']
        
        grade = calculate_grade(marks)
        
        db = get_db()
        c = db.cursor()
        c.execute("""INSERT INTO results (student_id, subject_code, marks, grade, semester, 
                    academic_year, created_by, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, subject_code, marks, grade, semester, academic_year, 
                session['username'], 'pending'))
        db.commit()
        
        log_action(session['username'], 'add_result', 
                f'Added result for {student_id} in {subject_code}: {marks}')
        flash('Result added successfully!', 'success')
        return redirect(url_for('results'))
    
    # Get students and subjects for the form with department info
    db = get_db()
    c = db.cursor()
    
    # Fetch students with department info
    c.execute("""SELECT s.*, d.id as dept_id, d.name as dept_name, f.id as faculty_id 
                 FROM students s
                 LEFT JOIN departments d ON s.department_id = d.id
                 LEFT JOIN faculties f ON d.faculty_id = f.id
                 ORDER BY s.name""")
    students = c.fetchall()
    
    # Fetch subjects with department info
    c.execute("""SELECT s.*, d.id as dept_id, d.name as dept_name, f.id as faculty_id 
                 FROM subjects s
                 LEFT JOIN departments d ON s.department_id = d.id
                 LEFT JOIN faculties f ON d.faculty_id = f.id
                 ORDER BY s.subject_name""")
    subjects = c.fetchall()
    
    # Fetch departments for filter
    c.execute("""SELECT d.id, d.name as dept_name, f.id as faculty_id, f.name as faculty_name 
                 FROM departments d 
                 JOIN faculties f ON d.faculty_id = f.id 
                 ORDER BY f.name, d.name""")
    departments = c.fetchall()
    
    # Fetch faculties for filter
    c.execute("SELECT * FROM faculties ORDER BY name")
    faculties = c.fetchall()
    
    return render_template('add_result.html', students=students, subjects=subjects, 
                         departments=departments, faculties=faculties)

@app.route('/results/approve/<int:result_id>')
@login_required
@role_required('admin')
def approve_result(result_id):
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE results SET status='approved', approved_by=?, approved_at=? WHERE id=?",
            (session['username'], datetime.now(), result_id))
    db.commit()
    
    log_action(session['username'], 'approve_result', f'Approved result ID: {result_id}')
    flash('Result approved successfully!', 'success')
    return redirect(url_for('results'))

@app.route('/results/amend/<int:result_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def amend_result(result_id):
    db = get_db()
    c = db.cursor()
    
    if request.method == 'POST':
        try:
            new_marks = float(request.form['marks'])
        except ValueError:
            flash('Invalid marks value.', 'error')
            return redirect(url_for('amend_result', result_id=result_id))
            
        reason = request.form['reason']
        
        # Get old result
        c.execute("SELECT * FROM results WHERE id=?", (result_id,))
        old_result = c.fetchone()
        
        old_marks = old_result['marks']
        old_grade = old_result['grade']
        new_grade = calculate_grade(new_marks)
        
        # Update result
        c.execute("UPDATE results SET marks=?, grade=? WHERE id=?",
                (new_marks, new_grade, result_id))
        
        # Log amendment
        c.execute("""INSERT INTO result_amendments (result_id, old_marks, new_marks, 
                    old_grade, new_grade, reason, amended_by) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (result_id, old_marks, new_marks, old_grade, new_grade, reason, session['username']))
        
        db.commit()
        
        log_action(session['username'], 'amend_result', 
                f'Amended result ID {result_id}: {old_marks} -> {new_marks}')
        flash('Result amended successfully!', 'success')
        return redirect(url_for('results'))
    
    c.execute("""SELECT r.*, s.name as student_name, sub.subject_name 
                FROM results r
                JOIN students s ON r.student_id = s.student_id
                JOIN subjects sub ON r.subject_code = sub.subject_code
                WHERE r.id=?""", (result_id,))
    result = c.fetchone()
    
    # Get amendment history
    c.execute("SELECT * FROM result_amendments WHERE result_id=? ORDER BY amended_at DESC", (result_id,))
    amendments = c.fetchall()
    
    return render_template('amend_result.html', result=result, amendments=amendments)

@app.route('/results/delete/<int:result_id>')
@login_required
@role_required('admin')
def delete_result(result_id):
    db = get_db()
    c = db.cursor()
    
    try:
        # Get result info for logging
        c.execute("""SELECT r.student_id, s.name as student_name, sub.subject_name 
                    FROM results r
                    JOIN students s ON r.student_id = s.student_id
                    JOIN subjects sub ON r.subject_code = sub.subject_code
                    WHERE r.id=?""", (result_id,))
        result = c.fetchone()
        
        if result:
            # Delete related amendments first
            c.execute("DELETE FROM result_amendments WHERE result_id=?", (result_id,))
            # Delete the result
            c.execute("DELETE FROM results WHERE id=?", (result_id,))
            db.commit()
            
            log_action(session['username'], 'delete_result', 
                      f'Deleted result ID {result_id} for {result["student_name"]} in {result["subject_name"]}')
            flash('Result deleted successfully!', 'success')
        else:
            flash('Result not found', 'error')
    except sqlite3.Error as e:
        flash(f'An error occurred: {str(e)}', 'error')
    
    return redirect(url_for('results'))

@app.route('/student/result/<token>')
def view_student_result(token):
    try:
        result_id = serializer.loads(token, salt='result-view', max_age=86400) # Valid for 24 hours
    except SignatureExpired:
        return render_template('error.html', message='The result link has expired.'), 400
    except BadTimeSignature:
        return render_template('error.html', message='Invalid result link.'), 400
    except BadSignature:
        return render_template('error.html', message='Invalid result link.'), 400
        
    db = get_db()
    c = db.cursor()
    c.execute("""SELECT r.*, s.name as student_name, s.student_id, sub.subject_name 
                FROM results r
                JOIN students s ON r.student_id = s.student_id
                JOIN subjects sub ON r.subject_code = sub.subject_code
                WHERE r.id=?""", (result_id,))
    result = c.fetchone()
    
    if not result:
        return render_template('error.html', message='Result not found.'), 404
        
    return render_template('student_result.html', result=result)

@app.route('/results/send/<int:result_id>')
@login_required
@role_required('admin', 'teacher')
def send_result(result_id):
    db = get_db()
    c = db.cursor()
    
    # Get student email
    c.execute("""SELECT s.email, s.name FROM results r
                JOIN students s ON r.student_id = s.student_id
                WHERE r.id=?""", (result_id,))
    student = c.fetchone()
    
    if not student or not student['email']:
        flash('Student does not have an email address linked.', 'error')
        return redirect(url_for('results'))
        
    success, message = send_result_email(student['email'], result_id)
    if success:
        flash(f'Result sent to {student["name"]} ({student["email"]})', 'success')
        log_action(session['username'], 'send_email', f'Sent result {result_id} to {student["email"]}')
    else:
        flash(f'Failed to send email: {message}', 'error')
        
    return redirect(url_for('results'))

@app.route('/reports')
@login_required
@role_required('admin', 'teacher')
def reports():
    return render_template('reports.html')

# AI Insights Routes
@app.route('/ai-insights')
@login_required
@role_required('admin', 'teacher')
def ai_insights():
    db = get_db()
    c = db.cursor()
    # Get students and classes for dropdowns
    c.execute("SELECT * FROM students ORDER BY name")
    students = c.fetchall()
    c.execute("SELECT DISTINCT class FROM students ORDER BY class")
    classes = [row['class'] for row in c.fetchall()]
    return render_template('ai_insights.html', students=students, classes=classes)

@app.route('/api/ai/predict/<path:student_id>')
@login_required
@role_required('admin', 'teacher')
def api_predict_performance(student_id):
    result = ai_engine.predict_performance(student_id)
    return jsonify(result)

@app.route('/api/ai/risk')
@login_required
@role_required('admin', 'teacher')
def api_at_risk_students():
    threshold = float(request.args.get('threshold', 60))
    result = ai_engine.identify_at_risk_students(threshold)
    return jsonify({'students': result})

@app.route('/api/ai/recommendations/<path:student_id>')
@login_required
@role_required('admin', 'teacher')
def api_recommendations(student_id):
    result = ai_engine.generate_personalized_recommendations(student_id)
    return jsonify(result)

@app.route('/api/ai/compare/<path:student_id>')
@login_required
@role_required('admin', 'teacher')
def api_comparative_insights(student_id):
    result = ai_engine.get_comparative_insights(student_id)
    return jsonify(result)

@app.route('/api/ai/class/<path:class_name>')
@login_required
@role_required('admin', 'teacher')
def api_class_insights(class_name):
    # Decode class name if needed
    class_name = urllib.parse.unquote(class_name)
    result = ai_engine.generate_class_insights(class_name)
    return jsonify(result)

@app.route('/api/ai/anomalies')
@login_required
@role_required('admin', 'teacher')
def api_anomalies():
    result = ai_engine.detect_anomalies()
    return jsonify({'anomalies': result})

@app.route('/api/analytics')
@login_required
@role_required('admin', 'teacher')
def analytics():
    db = get_db()
    c = db.cursor()
    
    # Grade distribution
    c.execute("""SELECT grade, COUNT(*) as count FROM results 
                WHERE status='approved' GROUP BY grade ORDER BY grade""")
    grade_dist = [dict(row) for row in c.fetchall()]
    
    # Subject-wise average
    c.execute("""SELECT sub.subject_name, AVG(r.marks) as avg_marks 
                FROM results r
                JOIN subjects sub ON r.subject_code = sub.subject_code
                WHERE r.status='approved'
                GROUP BY sub.subject_name
                ORDER BY avg_marks DESC""")
    subject_avg = [dict(row) for row in c.fetchall()]
    
    # Class-wise performance
    c.execute("""SELECT s.class, AVG(r.marks) as avg_marks, COUNT(*) as total_results
                FROM results r
                JOIN students s ON r.student_id = s.student_id
                WHERE r.status='approved'
                GROUP BY s.class
                ORDER BY s.class""")
    class_performance = [dict(row) for row in c.fetchall()]
    
    return jsonify({
        'grade_distribution': grade_dist,
        'subject_average': subject_avg,
        'class_performance': class_performance
    })

@app.route('/import', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'teacher')
def import_results():
    if request.method == 'POST':
        file = request.files['file']
        if file and file.filename.endswith('.csv'):
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_reader = csv.DictReader(stream)
            
            db = get_db()
            c = db.cursor()
            
            count = 0
            for row in csv_reader:
                try:
                    marks = float(row['marks'])
                    grade = calculate_grade(marks)
                    c.execute("""INSERT INTO results (student_id, subject_code, marks, grade, 
                                semester, academic_year, created_by, status) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                            (row['student_id'], row['subject_code'], marks, grade,
                            row.get('semester', 'first semester'), 
                            row.get('academic_year', '2022/2023'),
                            session['username'], 'pending'))
                    count += 1
                except Exception as e:
                    flash(f"Error importing row: {str(e)}", 'error')
            
            db.commit()
            
            log_action(session['username'], 'import_results', f'Imported {count} results')
            flash(f'Successfully imported {count} results!', 'success')
            return redirect(url_for('results'))
        else:
            flash('Please upload a valid CSV file', 'error')
    
    return render_template('import.html')

@app.route('/export')
@login_required
@role_required('admin', 'teacher')
def export_results():
    db = get_db()
    c = db.cursor()
    
    c.execute("""SELECT r.student_id, s.name, s.class, sub.subject_name, 
                r.marks, r.grade, r.semester, r.academic_year, r.status
                FROM results r
                JOIN students s ON r.student_id = s.student_id
                JOIN subjects sub ON r.subject_code = sub.subject_code
                ORDER BY s.name, sub.subject_name""")
    results = c.fetchall()
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Student ID', 'Name', 'Class', 'Subject', 'Marks', 'Grade', 
                    'Semester', 'Academic Year', 'Status'])
    
    for result in results:
        writer.writerow([result['student_id'], result['name'], result['class'], 
                        result['subject_name'], result['marks'], result['grade'],
                        result['semester'], result['academic_year'], result['status']])
    
    output.seek(0)
    
    log_action(session['username'], 'export_results', f'Exported {len(results)} results')
    
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'results_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

@app.route('/audit-log')
@login_required
@role_required('admin')
def audit_log():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 100")
    logs = c.fetchall()
    return render_template('audit_log.html', logs=logs)

@app.route('/users')
@login_required
@role_required('admin')
def users():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT id, username, role, email, created_at FROM users ORDER BY username")
    users = c.fetchall()
    return render_template('users.html', users=users)

@app.route('/users/add', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def add_user():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = generate_password_hash(request.form['password'].strip())
        role = request.form['role']
        email = request.form['email']
        
        try:
            db = get_db()
            c = db.cursor()
            c.execute("INSERT INTO users (username, password, role, email) VALUES (?, ?, ?, ?)",
                    (username, password, role, email))
            db.commit()
            
            log_action(session['username'], 'add_user', f'Added user: {username} ({role})')
            flash('User added successfully!', 'success')
            return redirect(url_for('users'))
        except sqlite3.IntegrityError:
            flash('Username already exists', 'error')
    
    return render_template('add_user.html')

@app.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit_user(user_id):
    db = get_db()
    c = db.cursor()
    
    if request.method == 'POST':
        role = request.form['role']
        email = request.form['email']
        password = request.form['password']
        
        try:
            if password:
                hashed_password = generate_password_hash(password)
                c.execute("UPDATE users SET role=?, email=?, password=? WHERE id=?",
                        (role, email, hashed_password, user_id))
            else:
                c.execute("UPDATE users SET role=?, email=? WHERE id=?",
                        (role, email, user_id))
            db.commit()
            
            log_action(session['username'], 'edit_user', f'Edited user ID: {user_id}')
            flash('User updated successfully!', 'success')
            return redirect(url_for('users'))
        except sqlite3.Error as e:
            flash(f'An error occurred: {e}', 'error')
            
    c.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('users'))
        
    return render_template('edit_user.html', user=user)

@app.route('/users/delete/<int:user_id>')
@login_required
@role_required('admin')
def delete_user(user_id):
    if user_id == session['user_id']:
        flash('You cannot delete your own account!', 'error')
        return redirect(url_for('users'))
        
    db = get_db()
    c = db.cursor()
    
    c.execute("SELECT username FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    if user:
        username = user['username']
        c.execute("DELETE FROM users WHERE id=?", (user_id,))
        db.commit()
        log_action(session['username'], 'delete_user', f'Deleted user: {username}')
        flash('User deleted successfully!', 'success')
    else:
        flash('User not found', 'error')
        
    return redirect(url_for('users'))

@app.errorhandler(500)
def internal_error(error):
    import traceback
    error_details = traceback.format_exc()
    print(f"500 Internal Server Error: {error}")
    print(error_details)
    db = getattr(g, '_database', None)
    if db is not None:
        db.rollback()
    
    # In production, you might want to show a generic error page,
    # but for debugging we'll flash the error if debug is on
    if app.debug:
        flash(f"Internal Server Error: {str(error)}", "error")
    else:
        flash("An unexpected error occurred. Please try again later.", "error")
        
    return render_template('error.html', message='Internal Server Error. Please contact admin.'), 500

@app.route('/test-email-config')
@login_required
@role_required('admin')
def test_email_config():
    """Simple route to test email configuration and connectivity."""
    msg = Message('Test Email Configuration',
                  recipients=[app.config['MAIL_USERNAME']])
    msg.body = "If you are reading this, your email configuration is working correctly."
    try:
        mail.send(msg)
        return "Email test successful! Check your inbox."
    except Exception as e:
        import traceback
        return f"Email test failed: {str(e)}<br><pre>{traceback.format_exc()}</pre>"

if __name__ == '__main__':
    init_db()
    app.run(debug=os.environ.get('FLASK_DEBUG', 'False') == 'True')