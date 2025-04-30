import hmac
import hashlib
from flask import Flask, render_template, request, redirect, session, url_for, flash, send_file
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import csv
import qrcode

app = Flask(__name__)
app.secret_key = 'your_flask_session_key_here'

CSV_FILE = 'attendance.csv'
STUDENT_FILE = 'students.csv'
SECRET_KEY_SALT = b'MY_SECRET_SALT'  # Replace with your secure value

# Generate secure daily HMAC key
def generate_secure_key(date_str=None):
    if not date_str:
        date_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    return hmac.new(SECRET_KEY_SALT, date_str.encode(), hashlib.sha256).hexdigest()

# Generate daily QR code
def generate_daily_qr():
    secure_key = generate_secure_key()
    base_url = "https://pccc-solar-training-program-attendance.onrender.com"
    full_url = f"{base_url}/?key={secure_key}"
    img = qrcode.make(full_url)
    filename = f"secure_qr_{datetime.now(ZoneInfo('America/New_York')).strftime('%Y%m%d')}.png"
    img.save(filename)
    print(f"\n✅ Secure QR Code URL: {full_url}")
    print(f"📸 QR saved as: {filename}\n")

# Load student list
def load_students():
    if not os.path.exists(STUDENT_FILE):
        return []
    with open(STUDENT_FILE, mode='r') as f:
        reader = csv.reader(f)
        return [row[0] for row in list(reader)[1:]]

students = load_students()

# Get check-in state
def get_checkin_state(student_name):
    today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
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

@app.route('/')
def index():
    url_key = request.args.get('key')
    expected_key = generate_secure_key()

    if url_key != expected_key:
        selected = request.args.get('student', '')
        return redirect(url_for('index', key=expected_key, student=selected))

    selected = request.args.get('student') or ""
    now = datetime.now(ZoneInfo("America/New_York"))
    today = now.strftime("%Y-%m-%d")
    current_day = now.strftime("%A")
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

@app.route('/submit', methods=['POST'])
def submit():
    name = request.form.get('student')
    check_type = request.form.get('action')
    secure_key = request.form.get('key')
    now = datetime.now(ZoneInfo("America/New_York"))
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
    url_key = request.args.get('key')
    expected_key = generate_secure_key()

    if url_key != expected_key:
        return redirect(url_for('admin', key=expected_key))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == 'password123':
            session['admin'] = True
            return redirect(url_for('dashboard', key=url_key))
        else:
            return render_template('admin.html', error="Invalid credentials", key=url_key)

    return render_template('admin.html', key=url_key)

@app.route('/dashboard')
def dashboard():
    url_key = request.args.get('key')
    expected_key = generate_secure_key()

    if url_key != expected_key:
        return redirect(url_for('dashboard', key=expected_key))

    if not session.get('admin'):
        return redirect(url_for('admin', key=url_key))

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

    return render_template('dashboard.html', records=records, key=url_key)

@app.route('/download-attendance')
def download_attendance():
    if not session.get('admin'):
        return redirect(url_for('admin', key=generate_secure_key()))
    if os.path.exists(CSV_FILE):
        return send_file(CSV_FILE, as_attachment=True)
    else:
        return "No attendance data recorded yet."

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('index', key=generate_secure_key()))

if __name__ == '__main__':
    generate_daily_qr()
    app.run(debug=False, use_reloader=False)
