from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os
from datetime import datetime, date, timedelta

app = Flask(__name__)
app.secret_key = 'clinic-secret-key-2024'

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clinic.db')

TIME_SLOTS = [f"{h:02d}:{m:02d}" for h in range(10, 20) for m in (0, 30)]
DURATION_OPTIONS = [30, 45, 60, 90, 120]
WEEKDAY_ZH = ['一', '二', '三', '四', '五', '六', '日']


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS therapists (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS patients (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            name              TEXT NOT NULL,
            phone             TEXT,
            birth_date        TEXT,
            gender            TEXT,
            address           TEXT,
            emergency_contact TEXT,
            notes             TEXT,
            created_at        TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS appointments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id   INTEGER NOT NULL REFERENCES patients(id),
            therapist_id INTEGER NOT NULL REFERENCES therapists(id),
            date         TEXT NOT NULL,
            start_time   TEXT NOT NULL,
            duration     INTEGER NOT NULL DEFAULT 60,
            cost         REAL    NOT NULL DEFAULT 0,
            status       TEXT    NOT NULL DEFAULT 'scheduled',
            notes        TEXT,
            created_at   TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS medical_records (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id     INTEGER NOT NULL REFERENCES patients(id),
            appointment_id INTEGER,
            record_date    TEXT NOT NULL,
            therapist_id   INTEGER,
            pain_score     INTEGER DEFAULT 0,
            -- 主訴症狀
            symptom_neck        INTEGER DEFAULT 0,
            symptom_shoulder    INTEGER DEFAULT 0,
            symptom_upper_back  INTEGER DEFAULT 0,
            symptom_lower_back  INTEGER DEFAULT 0,
            symptom_hip         INTEGER DEFAULT 0,
            symptom_knee        INTEGER DEFAULT 0,
            symptom_ankle       INTEGER DEFAULT 0,
            symptom_wrist       INTEGER DEFAULT 0,
            symptom_elbow       INTEGER DEFAULT 0,
            symptom_headache    INTEGER DEFAULT 0,
            symptom_dizziness   INTEGER DEFAULT 0,
            symptom_numbness    INTEGER DEFAULT 0,
            symptom_weakness    INTEGER DEFAULT 0,
            symptom_limited_rom INTEGER DEFAULT 0,
            -- 疼痛性質
            pain_sharp   INTEGER DEFAULT 0,
            pain_dull    INTEGER DEFAULT 0,
            pain_burning INTEGER DEFAULT 0,
            pain_numb    INTEGER DEFAULT 0,
            -- 既往病史
            history_hypertension  INTEGER DEFAULT 0,
            history_diabetes      INTEGER DEFAULT 0,
            history_heart_disease INTEGER DEFAULT 0,
            history_osteoporosis  INTEGER DEFAULT 0,
            history_cancer        INTEGER DEFAULT 0,
            history_surgery       INTEGER DEFAULT 0,
            history_fracture      INTEGER DEFAULT 0,
            history_pregnancy     INTEGER DEFAULT 0,
            -- 治療方式
            treatment_manual      INTEGER DEFAULT 0,
            treatment_ultrasound  INTEGER DEFAULT 0,
            treatment_electro     INTEGER DEFAULT 0,
            treatment_heat        INTEGER DEFAULT 0,
            treatment_ice         INTEGER DEFAULT 0,
            treatment_exercise    INTEGER DEFAULT 0,
            treatment_traction    INTEGER DEFAULT 0,
            treatment_taping      INTEGER DEFAULT 0,
            treatment_acupuncture INTEGER DEFAULT 0,
            treatment_massage     INTEGER DEFAULT 0,
            -- 文字紀錄
            assessment     TEXT,
            plan           TEXT,
            therapist_notes TEXT,
            created_at     TEXT DEFAULT (datetime('now','localtime'))
        );
    ''')
    if conn.execute("SELECT COUNT(*) FROM therapists").fetchone()[0] == 0:
        conn.executemany("INSERT INTO therapists (name) VALUES (?)",
                         [('治療師甲',), ('治療師乙',), ('治療師丙',)])
    conn.commit()
    conn.close()


# ─── helpers ─────────────────────────────────────────────────────────────────

def prev_workday(d):
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def next_workday(d):
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def nearest_workday(d):
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def compute_grid(appointments, therapists):
    """Build schedule grid: grid[slot_idx][therapist_idx] = cell or None."""
    slot_idx = {s: i for i, s in enumerate(TIME_SLOTS)}
    t_idx    = {t['id']: i for i, t in enumerate(therapists)}
    grid     = [[None] * len(therapists) for _ in TIME_SLOTS]

    for appt in appointments:
        si = slot_idx.get(appt['start_time'])
        ti = t_idx.get(appt['therapist_id'])
        if si is None or ti is None:
            continue
        rowspan = max(1, appt['duration'] // 30)
        grid[si][ti] = {'start': True, 'appt': dict(appt), 'rowspan': rowspan}
        for r in range(1, rowspan):
            if si + r < len(TIME_SLOTS):
                grid[si + r][ti] = {'start': False}

    return grid


# ─── calendar ────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('calendar_view', date=nearest_workday(date.today()).isoformat()))


@app.route('/calendar')
def calendar_view():
    date_str = request.args.get('date', date.today().isoformat())
    try:
        current = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        current = date.today()
    current = nearest_workday(current)

    conn = get_db()
    therapists = conn.execute("SELECT * FROM therapists ORDER BY id").fetchall()
    appointments = conn.execute("""
        SELECT a.*, p.name AS patient_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        WHERE a.date = ? AND a.status != 'cancelled'
        ORDER BY a.start_time
    """, (current.isoformat(),)).fetchall()
    conn.close()

    grid = compute_grid(appointments, therapists)

    return render_template('calendar.html',
        current=current,
        prev_date=prev_workday(current).isoformat(),
        next_date=next_workday(current).isoformat(),
        therapists=therapists,
        time_slots=TIME_SLOTS,
        grid=grid,
        weekday=WEEKDAY_ZH[current.weekday()],
    )


# ─── appointments ─────────────────────────────────────────────────────────────

@app.route('/appointments/new', methods=['GET', 'POST'])
def new_appointment():
    conn = get_db()
    therapists = conn.execute("SELECT * FROM therapists ORDER BY id").fetchall()
    patients   = conn.execute("SELECT id, name, phone FROM patients ORDER BY name").fetchall()

    if request.method == 'POST':
        f = request.form
        conn.execute("""
            INSERT INTO appointments
                (patient_id, therapist_id, date, start_time, duration, cost, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (f['patient_id'], f['therapist_id'], f['date'],
              f['start_time'], int(f['duration']), float(f['cost'] or 0),
              f.get('notes', '')))
        conn.commit()
        conn.close()
        flash('預約已新增', 'success')
        return redirect(url_for('calendar_view', date=f['date']))

    conn.close()
    return render_template('appointment_form.html',
        therapists=therapists,
        patients=patients,
        appointment=None,
        time_slots=TIME_SLOTS,
        duration_options=DURATION_OPTIONS,
        default_date=request.args.get('date', date.today().isoformat()),
        default_therapist=request.args.get('therapist_id', ''),
        default_time=request.args.get('start_time', ''),
    )


@app.route('/appointments/<int:appt_id>/edit', methods=['GET', 'POST'])
def edit_appointment(appt_id):
    conn = get_db()
    appt       = dict(conn.execute("SELECT * FROM appointments WHERE id = ?", (appt_id,)).fetchone())
    therapists = conn.execute("SELECT * FROM therapists ORDER BY id").fetchall()
    patients   = conn.execute("SELECT id, name, phone FROM patients ORDER BY name").fetchall()

    if request.method == 'POST':
        f = request.form
        conn.execute("""
            UPDATE appointments
            SET patient_id=?, therapist_id=?, date=?, start_time=?,
                duration=?, cost=?, status=?, notes=?
            WHERE id=?
        """, (f['patient_id'], f['therapist_id'], f['date'],
              f['start_time'], int(f['duration']), float(f['cost'] or 0),
              f.get('status', 'scheduled'), f.get('notes', ''), appt_id))
        conn.commit()
        conn.close()
        flash('預約已更新', 'success')
        return redirect(url_for('calendar_view', date=f['date']))

    conn.close()
    return render_template('appointment_form.html',
        therapists=therapists,
        patients=patients,
        appointment=appt,
        time_slots=TIME_SLOTS,
        duration_options=DURATION_OPTIONS,
        default_date=appt['date'],
        default_therapist=str(appt['therapist_id']),
        default_time=appt['start_time'],
    )


@app.route('/appointments/<int:appt_id>/cancel', methods=['POST'])
def cancel_appointment(appt_id):
    conn = get_db()
    row = conn.execute("SELECT date FROM appointments WHERE id = ?", (appt_id,)).fetchone()
    conn.execute("UPDATE appointments SET status='cancelled' WHERE id = ?", (appt_id,))
    conn.commit()
    conn.close()
    flash('預約已取消', 'warning')
    return redirect(url_for('calendar_view', date=row['date']))


@app.route('/appointments/<int:appt_id>/complete', methods=['POST'])
def complete_appointment(appt_id):
    conn = get_db()
    row = conn.execute("SELECT date FROM appointments WHERE id = ?", (appt_id,)).fetchone()
    conn.execute("UPDATE appointments SET status='completed' WHERE id = ?", (appt_id,))
    conn.commit()
    conn.close()
    flash('預約已標記為完成', 'success')
    return redirect(url_for('calendar_view', date=row['date']))


# ─── patients ────────────────────────────────────────────────────────────────

@app.route('/patients')
def patients():
    conn = get_db()
    q = request.args.get('q', '').strip()
    like = f'%{q}%'
    rows = conn.execute("""
        SELECT p.*, COUNT(a.id) AS visit_count
        FROM patients p
        LEFT JOIN appointments a ON a.patient_id = p.id AND a.status = 'completed'
        WHERE p.name LIKE ? OR p.phone LIKE ?
        GROUP BY p.id ORDER BY p.name
    """, (like, like)).fetchall()
    conn.close()
    return render_template('patients.html', patients=rows, q=q)


@app.route('/patients/new', methods=['GET', 'POST'])
def new_patient():
    if request.method == 'POST':
        f = request.form
        conn = get_db()
        conn.execute("""
            INSERT INTO patients (name, phone, birth_date, gender, address, emergency_contact, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (f['name'], f.get('phone',''), f.get('birth_date',''), f.get('gender',''),
              f.get('address',''), f.get('emergency_contact',''), f.get('notes','')))
        conn.commit()
        conn.close()
        flash('個案已新增', 'success')
        return redirect(url_for('patients'))
    return render_template('patient_form.html', patient=None)


@app.route('/patients/<int:patient_id>/edit', methods=['GET', 'POST'])
def edit_patient(patient_id):
    conn = get_db()
    patient = dict(conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone())
    if request.method == 'POST':
        f = request.form
        conn.execute("""
            UPDATE patients SET name=?, phone=?, birth_date=?, gender=?,
            address=?, emergency_contact=?, notes=? WHERE id=?
        """, (f['name'], f.get('phone',''), f.get('birth_date',''), f.get('gender',''),
              f.get('address',''), f.get('emergency_contact',''), f.get('notes',''), patient_id))
        conn.commit()
        conn.close()
        flash('個案資料已更新', 'success')
        return redirect(url_for('patients'))
    conn.close()
    return render_template('patient_form.html', patient=patient)


# ─── medical records ─────────────────────────────────────────────────────────

BOOL_FIELDS = [
    'symptom_neck','symptom_shoulder','symptom_upper_back','symptom_lower_back',
    'symptom_hip','symptom_knee','symptom_ankle','symptom_wrist','symptom_elbow',
    'symptom_headache','symptom_dizziness','symptom_numbness','symptom_weakness',
    'symptom_limited_rom',
    'pain_sharp','pain_dull','pain_burning','pain_numb',
    'history_hypertension','history_diabetes','history_heart_disease',
    'history_osteoporosis','history_cancer','history_surgery',
    'history_fracture','history_pregnancy',
    'treatment_manual','treatment_ultrasound','treatment_electro','treatment_heat',
    'treatment_ice','treatment_exercise','treatment_traction','treatment_taping',
    'treatment_acupuncture','treatment_massage',
]


@app.route('/records/new', methods=['GET', 'POST'])
def new_record():
    conn = get_db()
    patients   = conn.execute("SELECT id, name FROM patients ORDER BY name").fetchall()
    therapists = conn.execute("SELECT * FROM therapists ORDER BY id").fetchall()

    if request.method == 'POST':
        f    = request.form
        vals = {field: (1 if field in f else 0) for field in BOOL_FIELDS}
        cols = ', '.join(BOOL_FIELDS)
        phs  = ', '.join(':' + field for field in BOOL_FIELDS)
        conn.execute(f"""
            INSERT INTO medical_records
                (patient_id, appointment_id, record_date, therapist_id, pain_score,
                 {cols}, assessment, plan, therapist_notes)
            VALUES
                (:patient_id, :appointment_id, :record_date, :therapist_id, :pain_score,
                 {phs}, :assessment, :plan, :therapist_notes)
        """, {
            'patient_id':     f['patient_id'],
            'appointment_id': f.get('appointment_id') or None,
            'record_date':    f['record_date'],
            'therapist_id':   f.get('therapist_id') or None,
            'pain_score':     int(f.get('pain_score', 0)),
            **vals,
            'assessment':     f.get('assessment', ''),
            'plan':           f.get('plan', ''),
            'therapist_notes': f.get('therapist_notes', ''),
        })
        conn.commit()
        pid = f['patient_id']
        conn.close()
        flash('病歷已新增', 'success')
        return redirect(url_for('patient_records', patient_id=pid))

    conn.close()
    return render_template('medical_record.html',
        patients=patients,
        therapists=therapists,
        record=None,
        patient_id=request.args.get('patient_id', ''),
        appointment_id=request.args.get('appointment_id', ''),
        today=date.today().isoformat(),
    )


@app.route('/patients/<int:patient_id>/records')
def patient_records(patient_id):
    conn = get_db()
    patient = dict(conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone())
    records = conn.execute("""
        SELECT mr.*, t.name AS therapist_name
        FROM medical_records mr
        LEFT JOIN therapists t ON mr.therapist_id = t.id
        WHERE mr.patient_id = ?
        ORDER BY mr.record_date DESC, mr.id DESC
    """, (patient_id,)).fetchall()
    conn.close()
    return render_template('patient_records.html', patient=patient, records=records)


# ─── report ──────────────────────────────────────────────────────────────────

@app.route('/report')
def report():
    date_str = request.args.get('date', date.today().isoformat())
    try:
        report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        report_date = date.today()

    conn = get_db()
    therapists = conn.execute("SELECT * FROM therapists ORDER BY id").fetchall()
    appointments = conn.execute("""
        SELECT a.*, p.name AS patient_name, t.name AS therapist_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN therapists t ON a.therapist_id = t.id
        WHERE a.date = ?
        ORDER BY a.therapist_id, a.start_time
    """, (report_date.isoformat(),)).fetchall()
    conn.close()

    active = [a for a in appointments if a['status'] != 'cancelled']
    revenue = sum(a['cost'] for a in appointments if a['status'] == 'completed')

    t_stats = {}
    for t in therapists:
        ta = [a for a in appointments if a['therapist_id'] == t['id']]
        t_stats[t['id']] = {
            'name':         t['name'],
            'count':        len([a for a in ta if a['status'] != 'cancelled']),
            'completed':    len([a for a in ta if a['status'] == 'completed']),
            'revenue':      sum(a['cost'] for a in ta if a['status'] == 'completed'),
            'appointments': ta,
        }

    return render_template('report.html',
        report_date=report_date,
        weekday=WEEKDAY_ZH[report_date.weekday()],
        therapists=therapists,
        appointments=appointments,
        t_stats=t_stats,
        total=len(active),
        revenue=revenue,
    )


# ─── main ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
