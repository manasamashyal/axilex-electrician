from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
import sqlite3
from datetime import datetime, timedelta
import hashlib
import os
import re
import uuid
import razorpay
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__,
            template_folder='frontend/templates',
            static_folder='frontend/static')
app.secret_key = 'axilex_production_secret_key_2025'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'

# Create upload folders
os.makedirs('uploads/job_images', exist_ok=True)
os.makedirs('uploads/reports', exist_ok=True)

# Razorpay Configuration
RAZORPAY_KEY_ID = "rzp_test_SoUrgCmPV9QQ1d"
RAZORPAY_KEY_SECRET = "6GQWWMKC1QPszlA7Lz3LtEyv"


razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

# ==================== DECORATORS ====================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('login'))
        if session.get('user_role') != 'Admin':
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== DATABASE INITIALIZATION ====================

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Users table with wallet balance
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT UNIQUE NOT NULL,
        role TEXT NOT NULL DEFAULT 'Electrician',
        password TEXT NOT NULL,
        wallet_balance REAL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Electricians table
    c.execute('''CREATE TABLE IF NOT EXISTS electricians (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        specialization TEXT,
        status TEXT DEFAULT 'Available',
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    # Jobs table
    c.execute('''CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        location TEXT,
        electrician_id INTEGER,
        deadline DATE,
        status TEXT DEFAULT 'Pending',
        description TEXT,
        job_image TEXT,
        amount REAL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (electrician_id) REFERENCES electricians (id)
    )''')
    
    # Tasks table
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_name TEXT NOT NULL,
        job_id INTEGER,
        electrician_id INTEGER,
        progress INTEGER DEFAULT 0,
        status TEXT DEFAULT 'Pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs (id),
        FOREIGN KEY (electrician_id) REFERENCES electricians (id)
    )''')
    
    # Materials table
    c.execute('''CREATE TABLE IF NOT EXISTS materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        quantity INTEGER DEFAULT 0,
        unit TEXT,
        usage_track TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Notifications table
    c.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT NOT NULL,
        type TEXT DEFAULT 'info',
        is_read INTEGER DEFAULT 0,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Daily Work Reports table
    c.execute('''CREATE TABLE IF NOT EXISTS daily_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_date DATE,
        electrician_id INTEGER,
        tasks_completed INTEGER DEFAULT 0,
        hours_worked INTEGER DEFAULT 0,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (electrician_id) REFERENCES electricians (id)
    )''')
    
    # Payments table
    c.execute('''CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        payment_id TEXT UNIQUE NOT NULL,
        order_id TEXT,
        amount REAL NOT NULL,
        payment_type TEXT DEFAULT 'job_payment',
        status TEXT DEFAULT 'pending',
        from_user_id INTEGER,
        to_user_id INTEGER,
        job_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (from_user_id) REFERENCES users (id),
        FOREIGN KEY (to_user_id) REFERENCES users (id),
        FOREIGN KEY (job_id) REFERENCES jobs (id)
    )''')
    
    # Insert sample data if empty
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        # Admin user
        admin_password = hashlib.sha256('admin123'.encode()).hexdigest()
        c.execute("INSERT INTO users (name, phone, email, role, password, wallet_balance) VALUES (?,?,?,?,?,?)",
                 ('Admin User', '9999999999', 'admin@axilex.com', 'Admin', admin_password, 50000))
        
        # Electrician users
        elec_password = hashlib.sha256('electrician123'.encode()).hexdigest()
        electrician_users = [
            ('John Carter', '9876543210', 'john@axilex.com', 'Electrician', elec_password, 5000),
            ('Emma Clarke', '9123456780', 'emma@axilex.com', 'Electrician', elec_password, 3000),
            ('Michael Ross', '9988776655', 'michael@axilex.com', 'Electrician', elec_password, 2000),
        ]
        
        for e in electrician_users:
            c.execute("INSERT INTO users (name, phone, email, role, password, wallet_balance) VALUES (?,?,?,?,?,?)", e)
            
        # Get user IDs
        c.execute("SELECT id, name, email FROM users WHERE role='Electrician'")
        elec_users = c.fetchall()
        
        # Insert electricians linked to users
        for user in elec_users:
            c.execute("INSERT INTO electricians (name, phone, email, specialization, status, user_id) VALUES (?,?,?,?,?,?)",
                     (user[1], '9876543210', user[2], 'General', 'Available', user[0]))
        
        # Get electrician IDs
        c.execute("SELECT id FROM electricians")
        elec_ids = [row[0] for row in c.fetchall()]
        
        if len(elec_ids) >= 2:
            # Sample jobs with amounts
            jobs_data = [
                ('Wiring Installation', 'Downtown', elec_ids[0], (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d'), 'In Progress', 'Complete wiring for new building', None, 5000),
                ('Panel Upgrade', 'Northside', elec_ids[1], (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d'), 'Pending', 'Upgrade main electrical panel', None, 3500),
                ('Lighting Repair', 'Westend', elec_ids[0], (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'), 'Completed', 'Fix commercial lighting system', None, 2000),
            ]
            for j in jobs_data:
                c.execute("INSERT INTO jobs (title, location, electrician_id, deadline, status, description, job_image, amount) VALUES (?,?,?,?,?,?,?,?)", j)
            
            # Get job IDs
            c.execute("SELECT id FROM jobs")
            job_ids = [row[0] for row in c.fetchall()]
            
            if len(job_ids) >= 2:
                # Sample tasks
                tasks_data = [
                    ('Inspect breaker box', job_ids[0], elec_ids[0], 80, 'In Progress'),
                    ('Run conduit lines', job_ids[1], elec_ids[1], 45, 'In Progress'),
                    ('Test voltage', job_ids[2], elec_ids[0], 100, 'Completed'),
                ]
                for t in tasks_data:
                    c.execute("INSERT INTO tasks (task_name, job_id, electrician_id, progress, status) VALUES (?,?,?,?,?)", t)
        
        # Sample materials
        materials_data = [
            ('Copper Wire 12AWG', 150, 'meters', 'Used 50 meters for wiring'),
            ('Circuit Breaker 20A', 20, 'pieces', 'Used 4 pieces for panel'),
            ('LED Lights 10W', 80, 'pieces', 'Used 30 pieces for lighting'),
        ]
        for m in materials_data:
            c.execute("INSERT INTO materials (name, quantity, unit, usage_track) VALUES (?,?,?,?)", m)
    
    conn.commit()
    conn.close()

# Initialize database
if os.path.exists('database.db'):
    os.remove('database.db')
init_db()
print("=" * 50)
print("AXILEX Database Initialized!")
print("Admin: admin@axilex.com / admin123")
print("Electrician: john@axilex.com / electrician123")
print("=" * 50)

def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def add_notification(user_id, message, notification_type='info'):
    try:
        conn = get_db()
        conn.execute("INSERT INTO notifications (message, type, is_read, user_id) VALUES (?,?,?,?)",
                    (message, notification_type, 0, user_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Notification error: {e}")

# ==================== AUTHENTICATION ROUTES ====================

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not email or not password:
            flash('Please enter both email and password.', 'danger')
            return render_template('login.html')
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (email, hashed_password)).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            session['user_role'] = user['role']
            session['wallet_balance'] = user['wallet_balance']
            flash(f'Welcome back, {user["name"]}!', 'success')
            add_notification(user['id'], f'You logged in at {datetime.now().strftime("%H:%M:%S")}', 'info')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password!', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        role = request.form.get('role', 'Electrician')
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not name:
            flash('Please enter your name.', 'danger')
            return render_template('register.html')
        
        if not email:
            flash('Please enter your email address.', 'danger')
            return render_template('register.html')
        
        if not password:
            flash('Please enter a password.', 'danger')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('register.html')
        
        if not validate_email(email):
            flash('Please enter a valid email address.', 'danger')
            return render_template('register.html')
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        conn = get_db()
        try:
            existing = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
            if existing:
                flash('Email already registered!', 'danger')
                return render_template('register.html')
            
            conn.execute("INSERT INTO users (name, phone, email, role, password, wallet_balance) VALUES (?,?,?,?,?,?)",
                        (name, phone, email, role, hashed_password, 0))
            conn.commit()
            
            if role == 'Electrician':
                user = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
                conn.execute("INSERT INTO electricians (name, phone, email, specialization, status, user_id) VALUES (?,?,?,?,?,?)",
                            (name, phone, email, 'General', 'Available', user['id']))
                conn.commit()
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'danger')
        finally:
            conn.close()
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

# ==================== DASHBOARD ====================

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    user_role = session['user_role']
    user_id = session['user_id']
    
    total_electricians = conn.execute("SELECT COUNT(*) as count FROM electricians").fetchone()['count']
    active_jobs = conn.execute("SELECT COUNT(*) as count FROM jobs WHERE status != 'Completed'").fetchone()['count']
    pending_tasks = conn.execute("SELECT COUNT(*) as count FROM tasks WHERE status = 'Pending'").fetchone()['count']
    completed_jobs = conn.execute("SELECT COUNT(*) as count FROM jobs WHERE status = 'Completed'").fetchone()['count']
    
    user = conn.execute("SELECT wallet_balance FROM users WHERE id=?", (user_id,)).fetchone()
    wallet_balance = user['wallet_balance'] if user else 0
    
    pending_payments = conn.execute("""
        SELECT COUNT(*) as count FROM payments WHERE status = 'pending' AND to_user_id = ?
    """, (user_id,)).fetchone()['count']
    
    job_stats = conn.execute("SELECT status, COUNT(*) as count FROM jobs GROUP BY status").fetchall()
    completion_trend = conn.execute("""
        SELECT date(created_at) as date, COUNT(*) as count 
        FROM tasks WHERE status = 'Completed' 
        AND created_at >= date('now', '-7 days')
        GROUP BY date(created_at)
    """).fetchall()
    
    notifications = conn.execute("SELECT * FROM notifications WHERE user_id IS NULL OR user_id = ? ORDER BY created_at DESC LIMIT 10", (user_id,)).fetchall()
    unread_count = conn.execute("SELECT COUNT(*) as count FROM notifications WHERE (user_id IS NULL OR user_id = ?) AND is_read=0", (user_id,)).fetchone()['count']
    
    recent_tasks = conn.execute("""
        SELECT t.*, e.name as electrician_name, j.title as job_title
        FROM tasks t 
        LEFT JOIN electricians e ON t.electrician_id = e.id 
        LEFT JOIN jobs j ON t.job_id = j.id
        ORDER BY t.created_at DESC LIMIT 5
    """).fetchall()
    
    conn.close()
    
    return render_template('dashboard.html', 
                         total_electricians=total_electricians,
                         active_jobs=active_jobs,
                         pending_tasks=pending_tasks,
                         completed_jobs=completed_jobs,
                         wallet_balance=wallet_balance,
                         pending_payments=pending_payments,
                         job_stats=[dict(row) for row in job_stats],
                         completion_trend=[dict(row) for row in completion_trend],
                         notifications=notifications,
                         unread_count=unread_count,
                         recent_tasks=recent_tasks,
                         user_role=user_role)

# ==================== PAYMENT ROUTES ====================

@app.route('/payments')
@login_required
def payments():
    conn = get_db()
    user_id = session['user_id']
    
    user = conn.execute("SELECT wallet_balance FROM users WHERE id=?", (user_id,)).fetchone()
    wallet_balance = user['wallet_balance'] if user else 0
    
    payments = conn.execute("""
        SELECT p.*, 
               u1.name as from_user_name,
               u2.name as to_user_name,
               j.title as job_title
        FROM payments p
        LEFT JOIN users u1 ON p.from_user_id = u1.id
        LEFT JOIN users u2 ON p.to_user_id = u2.id
        LEFT JOIN jobs j ON p.job_id = j.id
        WHERE p.from_user_id = ? OR p.to_user_id = ?
        ORDER BY p.created_at DESC
    """, (user_id, user_id)).fetchall()
    
    electricians = conn.execute("SELECT id, name, user_id FROM electricians").fetchall()
    
    conn.close()
    
    return render_template('payments.html', 
                         wallet_balance=wallet_balance,
                         payments=payments,
                         electricians=electricians,
                         pay_amount=wallet_balance,
                         user_role=session['user_role'])

@app.route('/api/wallet/balance')
@login_required
def get_wallet_balance():
    conn = get_db()
    user = conn.execute("SELECT wallet_balance FROM users WHERE id=?", (session['user_id'],)).fetchone()
    conn.close()
    return jsonify({'success': True, 'balance': user['wallet_balance'] if user else 0})

@app.route('/api/wallet/transfer', methods=['POST'])
@login_required
def wallet_transfer():
    try:
        data = request.json
        to_user_id = data.get('to_user_id')
        amount = float(data.get('amount', 0))
        job_id = data.get('job_id')
        
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Invalid amount'}), 400
        
        conn = get_db()
        sender = conn.execute("SELECT wallet_balance FROM users WHERE id=?", (session['user_id'],)).fetchone()
        
        if sender['wallet_balance'] < amount:
            return jsonify({'success': False, 'error': 'Insufficient balance'}), 400
        
        conn.execute("UPDATE users SET wallet_balance = wallet_balance - ? WHERE id=?", (amount, session['user_id']))
        conn.execute("UPDATE users SET wallet_balance = wallet_balance + ? WHERE id=?", (amount, to_user_id))
        
        payment_id = f"pay_{uuid.uuid4().hex[:10]}"
        conn.execute("""
            INSERT INTO payments (payment_id, amount, payment_type, status, from_user_id, to_user_id, job_id)
            VALUES (?, ?, 'wallet_transfer', 'completed', ?, ?, ?)
        """, (payment_id, amount, session['user_id'], to_user_id, job_id))
        
        conn.commit()
        
        add_notification(to_user_id, f'Received ₹{amount} from {session["user_name"]}', 'success')
        add_notification(session['user_id'], f'Payment of ₹{amount} sent successfully', 'success')
        
        conn.close()
        session['wallet_balance'] = sender['wallet_balance'] - amount
        
        return jsonify({'success': True, 'new_balance': sender['wallet_balance'] - amount})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/wallet/recharge', methods=['POST'])
@login_required
def wallet_recharge():
    try:
        data = request.json
        amount = float(data.get('amount', 0))
        
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Invalid amount'}), 400
        
        conn = get_db()
        conn.execute("UPDATE users SET wallet_balance = wallet_balance + ? WHERE id=?", (amount, session['user_id']))
        
        payment_id = f"recharge_{uuid.uuid4().hex[:10]}"
        conn.execute("""
            INSERT INTO payments (payment_id, amount, payment_type, status, from_user_id, to_user_id)
            VALUES (?, ?, 'wallet_recharge', 'completed', ?, ?)
        """, (payment_id, amount, session['user_id'], session['user_id']))
        
        conn.commit()
        
        user = conn.execute("SELECT wallet_balance FROM users WHERE id=?", (session['user_id'],)).fetchone()
        conn.close()
        
        session['wallet_balance'] = user['wallet_balance']
        add_notification(session['user_id'], f'Wallet recharged with ₹{amount}!', 'success')
        
        return jsonify({'success': True, 'new_balance': user['wallet_balance']})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== RAZORPAY PAYMENT ROUTES ====================

@app.route('/create_razorpay_order', methods=['POST'])
@login_required
def create_razorpay_order():
    try:
        data = request.json
        amount = int(float(data.get('amount', 0)) * 100)
        
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Invalid amount'}), 400
        
        order_data = {
            'amount': amount,
            'currency': 'INR',
            'payment_capture': 1,
            'notes': {
                'user_id': session['user_id'],
                'user_email': session['user_email']
            }
        }
        order = razorpay_client.order.create(data=order_data)
        
        return jsonify({
            'success': True,
            'order_id': order['id'],
            'amount': amount,
            'currency': 'INR',
            'key_id': RAZORPAY_KEY_ID
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/payment_success', methods=['POST'])
@login_required
def payment_success():
    try:
        data = request.json
        order_id = data.get('order_id')
        payment_id = data.get('payment_id')
        amount = data.get('amount')
        
        conn = get_db()
        conn.execute("UPDATE users SET wallet_balance = wallet_balance + ? WHERE id=?", 
                    (amount, session['user_id']))
        
        payment_record_id = f"razor_{payment_id[:10]}"
        conn.execute("""
            INSERT INTO payments (payment_id, amount, payment_type, status, from_user_id, to_user_id)
            VALUES (?, ?, 'wallet_recharge', 'completed', ?, ?)
        """, (payment_record_id, amount, session['user_id'], session['user_id']))
        
        conn.commit()
        conn.close()
        
        add_notification(session['user_id'], f'Wallet recharged with ₹{amount} via Razorpay!', 'success')
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== JOB ROUTES ====================

@app.route('/jobs')
@login_required
def jobs():
    search = request.args.get('search', '')
    
    conn = get_db()
    user_role = session['user_role']
    user_id = session['user_id']
    
    query = """
        SELECT j.*, e.name as electrician_name 
        FROM jobs j 
        LEFT JOIN electricians e ON j.electrician_id = e.id 
        WHERE 1=1
    """
    params = []
    
    if user_role == 'Electrician':
        electrician = conn.execute("SELECT id FROM electricians WHERE user_id=?", (user_id,)).fetchone()
        if electrician:
            query += " AND j.electrician_id = ?"
            params.append(electrician['id'])
    
    if search:
        query += " AND (j.title LIKE ? OR j.location LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    
    query += " ORDER BY j.deadline"
    jobs = conn.execute(query, params).fetchall()
    
    electricians = conn.execute("SELECT id, name FROM electricians").fetchall() if user_role == 'Admin' else []
    conn.close()
    
    return render_template('jobs.html', jobs=jobs, electricians=electricians, search=search, user_role=user_role)

@app.route('/add_job', methods=['POST'])
@admin_required
def add_job():
    try:
        title = request.form.get('title', '')
        location = request.form.get('location', '')
        electrician_id = request.form.get('electrician_id', '')
        deadline = request.form.get('deadline', '')
        description = request.form.get('description', '')
        amount = float(request.form.get('amount', 0))
        
        if not title:
            return jsonify({'success': False, 'error': 'Title is required'}), 400
        
        job_image = None
        if 'job_image' in request.files:
            file = request.files['job_image']
            if file and file.filename:
                filename = secure_filename(f"job_{int(datetime.now().timestamp())}_{file.filename}")
                filepath = os.path.join('uploads/job_images', filename)
                file.save(filepath)
                job_image = filename
        
        conn = get_db()
        conn.execute("""
            INSERT INTO jobs (title, location, electrician_id, deadline, status, description, job_image, amount) 
            VALUES (?,?,?,?,?,?,?,?)
        """, (title, location, electrician_id if electrician_id else None, deadline, 'Pending', description, job_image, amount))
        conn.commit()
        
        add_notification(session['user_id'], f'New job created: {title}', 'info')
        conn.close()
        return jsonify({'success': True, 'message': 'Job created successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/get_job/<int:id>')
@login_required
def get_job(id):
    conn = get_db()
    job = conn.execute("SELECT * FROM jobs WHERE id=?", (id,)).fetchone()
    conn.close()
    return jsonify(dict(job))

@app.route('/update_job/<int:id>', methods=['PUT'])
@admin_required
def update_job(id):
    try:
        data = request.json
        conn = get_db()
        conn.execute("UPDATE jobs SET title=?, location=?, electrician_id=?, deadline=?, status=?, description=?, amount=? WHERE id=?",
                    (data['title'], data.get('location', ''), data.get('electrician_id'), data.get('deadline', ''), data['status'], data.get('description', ''), data.get('amount', 0), id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/delete_job/<int:id>', methods=['DELETE'])
@admin_required
def delete_job(id):
    try:
        conn = get_db()
        conn.execute("DELETE FROM tasks WHERE job_id=?", (id,))
        conn.execute("DELETE FROM jobs WHERE id=?", (id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/update_job_status/<int:id>', methods=['PUT'])
@login_required
def update_job_status(id):
    data = request.json
    conn = get_db()
    conn.execute("UPDATE jobs SET status=? WHERE id=?", (data['status'], id))
    
    if data['status'] == 'Completed':
        job = conn.execute("SELECT amount, electrician_id FROM jobs WHERE id=?", (id,)).fetchone()
        if job and job['amount'] > 0:
            electrician = conn.execute("SELECT user_id FROM electricians WHERE id=?", (job['electrician_id'],)).fetchone()
            if electrician:
                conn.execute("UPDATE users SET wallet_balance = wallet_balance + ? WHERE id=?", (job['amount'], electrician['user_id']))
                
                payment_id = f"jobpay_{uuid.uuid4().hex[:10]}"
                conn.execute("""
                    INSERT INTO payments (payment_id, amount, payment_type, status, from_user_id, to_user_id, job_id)
                    VALUES (?, ?, 'job_payment', 'completed', ?, ?, ?)
                """, (payment_id, job['amount'], session['user_id'], electrician['user_id'], id))
                
                add_notification(electrician['user_id'], f'Payment of ₹{job["amount"]} credited for job completion!', 'success')
    
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ==================== ELECTRICIAN ROUTES ====================

@app.route('/electricians')
@admin_required
def electricians():
    search = request.args.get('search', '')
    filter_status = request.args.get('status', '')
    
    conn = get_db()
    query = "SELECT * FROM electricians WHERE 1=1"
    params = []
    
    if search:
        query += " AND (name LIKE ? OR specialization LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    
    if filter_status:
        query += " AND status = ?"
        params.append(filter_status)
    
    query += " ORDER BY name"
    electricians = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template('electricians.html', electricians=electricians, search=search, filter_status=filter_status)

@app.route('/get_electrician/<int:id>')
@admin_required
def get_electrician(id):
    conn = get_db()
    elec = conn.execute("SELECT * FROM electricians WHERE id=?", (id,)).fetchone()
    conn.close()
    return jsonify(dict(elec))

@app.route('/add_electrician', methods=['POST'])
@admin_required
def add_electrician():
    data = request.json
    conn = get_db()
    conn.execute("INSERT INTO electricians (name, phone, email, specialization, status) VALUES (?,?,?,?,?)",
                (data['name'], data.get('phone', ''), data.get('email', ''), data.get('specialization', ''), 'Available'))
    conn.commit()
    add_notification(session['user_id'], f'New electrician added: {data["name"]}', 'info')
    conn.close()
    return jsonify({'success': True})

@app.route('/update_electrician/<int:id>', methods=['PUT'])
@admin_required
def update_electrician(id):
    data = request.json
    conn = get_db()
    conn.execute("UPDATE electricians SET name=?, phone=?, email=?, specialization=?, status=? WHERE id=?",
                (data['name'], data.get('phone', ''), data.get('email', ''), data.get('specialization', ''), data['status'], id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/delete_electrician/<int:id>', methods=['DELETE'])
@admin_required
def delete_electrician(id):
    conn = get_db()
    conn.execute("DELETE FROM electricians WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ==================== TASK ROUTES ====================

@app.route('/tasks')
@login_required
def tasks():
    status_filter = request.args.get('status', 'all')
    
    conn = get_db()
    user_role = session['user_role']
    user_id = session['user_id']
    
    query = """
        SELECT t.*, e.name as electrician_name, j.title as job_title 
        FROM tasks t 
        LEFT JOIN electricians e ON t.electrician_id = e.id 
        LEFT JOIN jobs j ON t.job_id = j.id 
        WHERE 1=1
    """
    params = []
    
    if user_role == 'Electrician':
        electrician = conn.execute("SELECT id FROM electricians WHERE user_id=?", (user_id,)).fetchone()
        if electrician:
            query += " AND t.electrician_id = ?"
            params.append(electrician['id'])
    
    if status_filter != 'all':
        query += " AND t.status = ?"
        params.append(status_filter)
    
    query += " ORDER BY t.created_at DESC"
    tasks_data = conn.execute(query, params).fetchall()
    
    electricians = conn.execute("SELECT id, name FROM electricians").fetchall()
    jobs = conn.execute("SELECT id, title FROM jobs").fetchall()
    conn.close()
    
    return render_template('tasks.html', tasks=tasks_data, electricians=electricians, jobs=jobs, current_filter=status_filter, user_role=user_role)

@app.route('/get_task/<int:id>')
@login_required
def get_task(id):
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id=?", (id,)).fetchone()
    conn.close()
    return jsonify(dict(task))

@app.route('/add_task', methods=['POST'])
@admin_required
def add_task():
    data = request.json
    conn = get_db()
    conn.execute("INSERT INTO tasks (task_name, job_id, electrician_id, progress, status) VALUES (?,?,?,?,?)",
                (data['task_name'], data.get('job_id'), data.get('electrician_id'), 0, 'Pending'))
    conn.commit()
    
    if data.get('electrician_id'):
        electrician = conn.execute("SELECT user_id FROM electricians WHERE id=?", (data['electrician_id'],)).fetchone()
        if electrician:
            add_notification(electrician['user_id'], f'New task assigned: {data["task_name"]}', 'task')
    
    conn.close()
    return jsonify({'success': True})

@app.route('/update_task/<int:id>', methods=['PUT'])
@admin_required
def update_task(id):
    data = request.json
    conn = get_db()
    conn.execute("UPDATE tasks SET task_name=?, job_id=?, electrician_id=?, progress=?, status=? WHERE id=?",
                (data['task_name'], data.get('job_id'), data.get('electrician_id'), data['progress'], data['status'], id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/delete_task/<int:id>', methods=['DELETE'])
@admin_required
def delete_task(id):
    conn = get_db()
    conn.execute("DELETE FROM tasks WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/update_task_progress/<int:id>', methods=['PUT'])
@login_required
def update_task_progress(id):
    data = request.json
    status = 'Completed' if data['progress'] == 100 else ('In Progress' if data['progress'] > 0 else 'Pending')
    conn = get_db()
    conn.execute("UPDATE tasks SET progress=?, status=? WHERE id=?", (data['progress'], status, id))
    
    if data['progress'] == 100:
        task = conn.execute("SELECT task_name FROM tasks WHERE id=?", (id,)).fetchone()
        add_notification(session['user_id'], f'Task "{task["task_name"]}" completed! 🎉', 'success')
    
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ==================== MATERIALS ROUTES ====================

@app.route('/materials')
@login_required
def materials():
    conn = get_db()
    materials = conn.execute("SELECT * FROM materials ORDER BY name").fetchall()
    conn.close()
    return render_template('materials.html', materials=materials)

@app.route('/get_material/<int:id>')
@login_required
def get_material(id):
    conn = get_db()
    material = conn.execute("SELECT * FROM materials WHERE id=?", (id,)).fetchone()
    conn.close()
    return jsonify(dict(material))

@app.route('/add_material', methods=['POST'])
@admin_required
def add_material():
    data = request.json
    conn = get_db()
    conn.execute("INSERT INTO materials (name, quantity, unit, usage_track) VALUES (?,?,?,?)",
                (data['name'], data.get('quantity', 0), data.get('unit', 'pcs'), data.get('usage_track', '')))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/update_material/<int:id>', methods=['PUT'])
@admin_required
def update_material(id):
    data = request.json
    conn = get_db()
    conn.execute("UPDATE materials SET name=?, quantity=?, unit=?, usage_track=? WHERE id=?",
                (data['name'], data['quantity'], data.get('unit', 'pcs'), data.get('usage_track', ''), id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/delete_material/<int:id>', methods=['DELETE'])
@admin_required
def delete_material(id):
    conn = get_db()
    conn.execute("DELETE FROM materials WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ==================== REPORTS ROUTE ====================

@app.route('/reports')
@login_required
def reports():
    conn = get_db()
    
    total_electricians = conn.execute("SELECT COUNT(*) as count FROM electricians").fetchone()['count']
    active_jobs = conn.execute("SELECT COUNT(*) as count FROM jobs WHERE status != 'Completed'").fetchone()['count']
    pending_tasks = conn.execute("SELECT COUNT(*) as count FROM tasks WHERE status = 'Pending'").fetchone()['count']
    completed_jobs = conn.execute("SELECT COUNT(*) as count FROM jobs WHERE status = 'Completed'").fetchone()['count']
    total_tasks = conn.execute("SELECT COUNT(*) as count FROM tasks").fetchone()['count']
    in_progress_tasks = conn.execute("SELECT COUNT(*) as count FROM tasks WHERE status = 'In Progress'").fetchone()['count']
    
    task_completion = conn.execute("""
        SELECT status, COUNT(*) as count, 
               ROUND(CAST(COUNT(*) AS FLOAT) / (SELECT COUNT(*) FROM tasks) * 100, 1) as percentage
        FROM tasks GROUP BY status
    """).fetchall()
    
    electrician_activity = conn.execute("""
        SELECT e.name, COUNT(DISTINCT t.id) as total_tasks,
               SUM(CASE WHEN t.status = 'Completed' THEN 1 ELSE 0 END) as completed_tasks,
               ROUND(AVG(t.progress), 1) as avg_progress,
               COUNT(DISTINCT j.id) as assigned_jobs
        FROM electricians e
        LEFT JOIN tasks t ON t.electrician_id = e.id
        LEFT JOIN jobs j ON j.electrician_id = e.id
        GROUP BY e.id ORDER BY completed_tasks DESC
    """).fetchall()
    
    daily_reports = conn.execute("""
        SELECT dr.*, e.name as electrician_name 
        FROM daily_reports dr 
        LEFT JOIN electricians e ON dr.electrician_id = e.id 
        ORDER BY dr.report_date DESC LIMIT 10
    """).fetchall()
    
    payment_summary = conn.execute("""
        SELECT 
            SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END) as total_collected,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as total_transactions
        FROM payments
    """).fetchone()
    
    conn.close()
    
    return render_template('reports.html', 
                         total_electricians=total_electricians,
                         active_jobs=active_jobs,
                         pending_tasks=pending_tasks,
                         completed_jobs=completed_jobs,
                         total_tasks=total_tasks,
                         in_progress_tasks=in_progress_tasks,
                         task_completion=[dict(row) for row in task_completion],
                         electrician_activity=[dict(row) for row in electrician_activity],
                         daily_reports=daily_reports,
                         payment_summary=dict(payment_summary))

# ==================== PROFILE ====================

@app.route('/profile')
@login_required
def profile():
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (session['user_id'],)).fetchone()
    
    if not user:
        flash('User not found!', 'danger')
        return redirect(url_for('logout'))
    
    electrician = None
    if user['role'] == 'Electrician':
        electrician = conn.execute("SELECT * FROM electricians WHERE user_id=?", (user['id'],)).fetchone()
    
    conn.close()
    return render_template('profile.html', user=user, electrician=electrician)

@app.route('/api/profile', methods=['PUT'])
@login_required
def api_update_profile():
    try:
        data = request.json
        conn = get_db()
        conn.execute("UPDATE users SET name=?, phone=? WHERE id=?", 
                    (data['name'], data.get('phone', ''), session['user_id']))
        conn.commit()
        
        if session['user_role'] == 'Electrician':
            conn.execute("UPDATE electricians SET name=?, phone=? WHERE user_id=?", 
                        (data['name'], data.get('phone', ''), session['user_id']))
            conn.commit()
        
        session['user_name'] = data['name']
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/change-password', methods=['POST'])
@login_required
def api_change_password():
    try:
        data = request.json
        current_password = hashlib.sha256(data['current_password'].encode()).hexdigest()
        new_password = data['new_password']
        
        if len(new_password) < 6:
            return jsonify({'success': False, 'error': 'Password must be at least 6 characters'}), 400
        
        conn = get_db()
        user = conn.execute("SELECT password FROM users WHERE id=?", (session['user_id'],)).fetchone()
        
        if user['password'] != current_password:
            return jsonify({'success': False, 'error': 'Current password is incorrect'}), 400
        
        hashed_new = hashlib.sha256(new_password.encode()).hexdigest()
        conn.execute("UPDATE users SET password=? WHERE id=?", (hashed_new, session['user_id']))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== NOTIFICATIONS API ====================

@app.route('/api/notifications')
@login_required
def api_get_notifications():
    conn = get_db()
    user_id = session['user_id']
    notifications = conn.execute("""
        SELECT * FROM notifications 
        WHERE user_id IS NULL OR user_id = ? 
        ORDER BY created_at DESC LIMIT 20
    """, (user_id,)).fetchall()
    unread_count = conn.execute("""
        SELECT COUNT(*) as count FROM notifications 
        WHERE (user_id IS NULL OR user_id = ?) AND is_read = 0
    """, (user_id,)).fetchone()['count']
    conn.close()
    return jsonify({'success': True, 'notifications': [dict(n) for n in notifications], 'unread_count': unread_count})

@app.route('/api/notifications/<int:id>/read', methods=['POST'])
@login_required
def api_mark_notification_read(id):
    conn = get_db()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory('uploads', filename)

# Create database and tables on startup
def create_tables():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT UNIQUE NOT NULL,
        role TEXT NOT NULL DEFAULT 'Electrician',
        password TEXT NOT NULL,
        wallet_balance REAL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Electricians table
    c.execute('''CREATE TABLE IF NOT EXISTS electricians (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        specialization TEXT,
        status TEXT DEFAULT 'Available',
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    # Jobs table
    c.execute('''CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        location TEXT,
        electrician_id INTEGER,
        deadline DATE,
        status TEXT DEFAULT 'Pending',
        description TEXT,
        job_image TEXT,
        amount REAL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (electrician_id) REFERENCES electricians (id)
    )''')
    
    # Tasks table
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_name TEXT NOT NULL,
        job_id INTEGER,
        electrician_id INTEGER,
        progress INTEGER DEFAULT 0,
        status TEXT DEFAULT 'Pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs (id),
        FOREIGN KEY (electrician_id) REFERENCES electricians (id)
    )''')
    
    # Materials table
    c.execute('''CREATE TABLE IF NOT EXISTS materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        quantity INTEGER DEFAULT 0,
        unit TEXT,
        usage_track TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Notifications table
    c.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT NOT NULL,
        type TEXT DEFAULT 'info',
        is_read INTEGER DEFAULT 0,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Payments table
    c.execute('''CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        payment_id TEXT UNIQUE NOT NULL,
        amount REAL NOT NULL,
        payment_type TEXT DEFAULT 'job_payment',
        status TEXT DEFAULT 'pending',
        from_user_id INTEGER,
        to_user_id INTEGER,
        job_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (from_user_id) REFERENCES users (id),
        FOREIGN KEY (to_user_id) REFERENCES users (id),
        FOREIGN KEY (job_id) REFERENCES jobs (id)
    )''')
    
    # Daily Reports table
    c.execute('''CREATE TABLE IF NOT EXISTS daily_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_date DATE,
        electrician_id INTEGER,
        tasks_completed INTEGER DEFAULT 0,
        hours_worked INTEGER DEFAULT 0,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (electrician_id) REFERENCES electricians (id)
    )''')
    
    conn.commit()
    conn.close()

# Call this function when app starts
create_tables()

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🚀 AXILEX Electrician Management System - FINAL WEEK COMPLETE")
    print("=" * 60)
    print("📍 URL: http://localhost:5000")
    print("📧 Admin: admin@axilex.com / admin123")
    print("📧 Electrician: john@axilex.com / electrician123")
    print("=" * 60)
    print("💰 PAYMENT SYSTEM:")
    print("   - Admin Wallet: ₹50,000")
    print("   - Electrician Wallet: ₹5,000")
    print("   - Send payments from Admin to Electrician")
    print("   - View transaction history")
    print("=" * 60 + "\n")
    app.run(debug=True, port=5000)