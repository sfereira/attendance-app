import hmac
import hashlib
from flask import Flask, render_template, request, redirect, session, url_for, flash
from datetime import datetime
import os
import csv
import qrcode

app = Flask(__name__)
app.secret_key = 'your_flask_session_key_here'

CSV_FILE = 'attendance.csv'
STUDENT_FILE = 'students.csv'
SECRET_KEY_SALT = b'MY_SECRET_SALT'  # 🔐 Use a long, secure value

# Secure key generator (HMAC-based)
def generate_secure_key(date_str=None):
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    return hmac.new(SECRET_KEY_SALT, date_str.encode(), hashlib.sha256).hexdigest()

# Generate QR Code
def generate_daily_qr():
    secure_key = generate_secure_key()
    base_url = "http://localhost:5000"  # Replace with your live domain
    full_url = f"{base_url}/?key={secure_key}"
    img = qrcode.make(full_url)
    filename = f"secure_qr_{datetime.now().strftime('%Y%m%d')}.png"
    img.save(filename)
    print(f"\n✅ Secure QR Code URL: {full_url}")
    print(f"📸 QR code saved as: {filename}\n")

# Load students
def load_students():
    if not os.path.exists(STUDENT_FILE):
        return []
    with open(STUDENT_FILE, mode='r') as f:
        reader = csv.reader(f)
        return [row[0] for row in list(reader)[1:]]

students = load_students()

# Get check-in state
def get_checkin_state(student_name):
    today = datetime.now().strftime("%Y-%m-%d")
    state = {'morning': False, 'lunch': False}
    if not student_name or not os.path.exists(CSV_FILE):
        return state

    with open(CSV_FILE, mode='r') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3:
                continue
            date, name, type_check = row[0], row[1], row[2]
            if date == today and name == student_name:
                if type_check == 'Morning Check-In':
                    state['morning'] = True
                elif type_check == 'Lunch Break Check-In':
                    state['lunch'] = True
    return state

# Main route
@app.route('/')
def index():
    url_key = request.args.get('key')
    today_str = datetime.now().strftime('%Y-%m-%d')
    expected_key = generate_secure_key(today_str)

    if url_key != expected_key:
        return "<h3>Invalid or expired QR code. Please ask your instructor for the latest one.</h3>"

    selected = request.args.get('student') or ""
    today = datetime.now().strftime("%Y-%m-%d")
    current_day = datetime.now().strftime("%A")
    checkin_state = get_checkin_state(selected)

    if selected and checkin_state['morning'] and checkin_state['lunch']:
        flash("Your today's attendance is recorded")

    return render_template('index.html',
                           students=students,
                           selected=selected,
                           checkin_state=checkin_state,
                           current_day=current_day,
                           today=today,
                           key=url_key)

# Submit check-in
@app.route('/submit', methods=['POST'])
def submit():
    name = request.form.get('student')
    check_type = request.form.get('action')
    secure_key = request.form.get('key')
    now = datetime.now()
    recorded_time = now.strftime("%H:%M")
    display_time = now.strftime("%I:%M %p")
    date = now.strftime("%Y-%m-%d")
    status = ""

    state = get_checkin_state(name)
    if (check_type == "Morning Check-In" and state['morning']) or \
       (check_type == "Lunch Break Check-In" and state['lunch']):
        flash(f"Your {check_type} is already recorded.")
        return redirect(url_for('index', student=name, key=secure_key))

    if check_type == "Morning Check-In":
        checkin_time = datetime.strptime(recorded_time, "%H:%M")
        if checkin_time <= datetime.strptime("09:45", "%H:%M"):
            status = "Present"
        elif checkin_time <= datetime.strptime("10:30", "%H:%M"):
            status = "Late"
        else:
            status = "Absent"

    with open(CSV_FILE, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([date, name, check_type, recorded_time, status])

    flash(f"Your {check_type} is recorded at {display_time}")
    return redirect(url_for('index', student=name, key=secure_key))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == 'password123':
            session['admin'] = True
            return redirect(url_for('dashboard'))
        else:
            return render_template('admin.html', error="Invalid credentials")
    return render_template('admin.html')

@app.route('/dashboard')
def dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin'))

    records = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='r') as file:
            reader = csv.reader(file)
            for row in reader:
                if len(row) == 5:
                    records.append({
                        'Date': row[0],
                        'Name': row[1],
                        'Type': row[2],
                        'Time': row[3],
                        'Status': row[4]
                    })

    return render_template('dashboard.html', records=records)

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('index', key=generate_secure_key()))

# Launch the app
if __name__ == '__main__':
    generate_daily_qr()
    app.run(host='0.0.0.0', port=5000, debug=False)
