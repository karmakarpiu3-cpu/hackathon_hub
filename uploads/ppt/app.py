from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
import sqlite3
import os
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'supersecretkey'

DATABASE = 'hackathon.db'
UPLOAD_FOLDER = 'uploads'
PPT_FOLDER = os.path.join(UPLOAD_FOLDER, 'ppt')
REPORT_FOLDER = os.path.join(UPLOAD_FOLDER, 'reports')

os.makedirs(PPT_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# =========================
# Database Connection
# =========================
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# =========================
# Database Initialization
# =========================
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'participant'
    )
    ''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        deadline TEXT
    )
    ''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        project_title TEXT,
        description TEXT,
        github_link TEXT,
        ppt_file TEXT,
        report_file TEXT,
        video_link TEXT,
        submit_time TEXT,
        status TEXT DEFAULT 'Submitted',
        admin_review TEXT DEFAULT 'Pending',
        score INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    ''')

    # Default admin
    cur.execute("SELECT * FROM users WHERE email = ?", ('admin@hackathon.com',))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            ('Admin', 'admin@hackathon.com', 'admin123', 'admin')
        )

    # Default settings row
    cur.execute("SELECT * FROM settings")
    if cur.fetchone() is None:
        cur.execute("INSERT INTO settings (deadline) VALUES (?)", ('2099-12-31 23:59',))

    conn.commit()
    conn.close()


# =========================
# Helpers
# =========================
def get_deadline():
    conn = get_db_connection()
    row = conn.execute("SELECT deadline FROM settings LIMIT 1").fetchone()
    conn.close()
    return row['deadline'] if row else None


def is_deadline_passed():
    deadline = get_deadline()
    if not deadline:
        return False
    return datetime.now() > datetime.strptime(deadline, '%Y-%m-%d %H:%M')


# =========================
# Routes
# =========================
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                (name, email, password, 'participant')
            )
            conn.commit()
            flash('Registration successful!')
            return redirect('/login')
        except sqlite3.IntegrityError:
            flash('Email already exists.')
        finally:
            conn.close()

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ? AND password = ?",
            (email, password)
        ).fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['name'] = user['name']

            if user['role'] == 'admin':
                return redirect('/admin')
            return redirect('/dashboard')
        else:
            flash('Invalid credentials.')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    submission = conn.execute(
        "SELECT * FROM submissions WHERE user_id = ?",
        (session['user_id'],)
    ).fetchone()
    conn.close()

    return render_template(
        'dashboard.html',
        submission=submission,
        deadline=get_deadline(),
        deadline_passed=is_deadline_passed()
    )


@app.route('/submit', methods=['GET', 'POST'])
def submit_project():
    if 'user_id' not in session:
        return redirect('/login')

    if is_deadline_passed():
        flash('Submission deadline has passed.')
        return redirect('/dashboard')

    if request.method == 'POST':
        title = request.form['project_title']
        description = request.form['description']
        github = request.form['github_link']
        video = request.form['video_link']

        ppt = request.files.get('ppt_file')
        report = request.files.get('report_file')

        ppt_filename = None
        report_filename = None

        if ppt and ppt.filename:
            ppt_filename = secure_filename(ppt.filename)
            ppt.save(os.path.join(PPT_FOLDER, ppt_filename))

        if report and report.filename:
            report_filename = secure_filename(report.filename)
            report.save(os.path.join(REPORT_FOLDER, report_filename))

        conn = get_db_connection()

        existing = conn.execute(
            "SELECT * FROM submissions WHERE user_id = ?",
            (session['user_id'],)
        ).fetchone()

        if existing:
            ppt_filename = ppt_filename or existing['ppt_file']
            report_filename = report_filename or existing['report_file']

            conn.execute('''
                UPDATE submissions
                SET project_title=?, description=?, github_link=?,
                    ppt_file=?, report_file=?, video_link=?, submit_time=?
                WHERE user_id=?
            ''', (
                title, description, github,
                ppt_filename, report_filename,
                video, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                session['user_id']
            ))
        else:
            conn.execute('''
                INSERT INTO submissions
                (user_id, project_title, description, github_link,
                 ppt_file, report_file, video_link, submit_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session['user_id'], title, description, github,
                ppt_filename, report_filename,
                video, datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))

        conn.commit()
        conn.close()

        flash('Project submitted successfully!')
        return redirect('/dashboard')

    return render_template('submit_project.html')


@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect('/login')

    if request.method == 'POST':
        deadline = request.form['deadline']
        conn = get_db_connection()
        conn.execute("UPDATE settings SET deadline = ? WHERE id = 1", (deadline,))
        conn.commit()
        conn.close()

    conn = get_db_connection()
    submissions = conn.execute('''
        SELECT submissions.*,
               COALESCE(users.name, 'Deleted User') as name,
               COALESCE(users.email, 'N/A') as email
        FROM submissions
        LEFT JOIN users ON submissions.user_id = users.id
        ORDER BY submit_time DESC
    ''').fetchall()
    conn.close()

    return render_template(
        'admin_dashboard.html',
        submissions=submissions,
        deadline=get_deadline()
    )


@app.route('/review/<int:submission_id>', methods=['GET', 'POST'])
def review_submission(submission_id):
    if session.get('role') != 'admin':
        return redirect('/login')

    conn = get_db_connection()

    if request.method == 'POST':
        review = request.form['admin_review']
        score = request.form['score']

        conn.execute('''
            UPDATE submissions
            SET admin_review = ?, score = ?
            WHERE id = ?
        ''', (review, score, submission_id))
        conn.commit()
        conn.close()
        return redirect('/admin')

    submission = conn.execute(
        "SELECT * FROM submissions WHERE id = ?",
        (submission_id,)
    ).fetchone()
    conn.close()

    return render_template('review_submission.html', submission=submission)


@app.route('/uploads/<folder>/<filename>')
def uploaded_file(folder, filename):
    if folder == 'ppt':
        return send_from_directory(PPT_FOLDER, filename)
    elif folder == 'reports':
        return send_from_directory(REPORT_FOLDER, filename)
    return 'Invalid folder'


if __name__ == '__main__':
    init_db()
    app.run(debug=True)