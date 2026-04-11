from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
import os
from datetime import datetime, date, timedelta
from collections import defaultdict

app = Flask(__name__)
app.secret_key = 'clinic-secret-key-2024'

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clinic.db')

TIME_SLOTS = [f"{h:02d}:{m:02d}" for h in range(10, 20) for m in (0, 30)]
DURATION_OPTIONS = [30, 45, 60, 90, 120]
WEEKDAY_ZH = ['一', '二', '三', '四', '五', '六', '日']
REFERRAL_SOURCES = [
    ('online_search',      '網路搜尋'),
    ('social_media',       '社群媒體 (IG/FB)'),
    ('friend_referral',    '親友介紹'),
    ('therapist_referral', '治療師介紹'),
    ('walk_in',            '路過 / 自然到訪'),
    ('other',              '其他'),
]

# (value, display_label, [price_presets])
SERVICE_TYPES = [
    ('assessment',    '單純評估衛教',        [1500]),
    ('full_treatment','完整治療',            [2500, 2800]),
    ('exercise',      '運動訓練',            [2500, 2800]),
    ('winback',       '高階儀器 — Winback',  [1500]),
    ('shockwave',     '高階儀器 — 震波',     [1500]),
    ('space_rental',  '場租',               [300]),
]

PACKAGE_TYPES = [
    ('10x2500', '10堂方案', 10, 2500),
    ('20x2000', '20堂方案', 20, 2000),
]

THERAPIST_COLORS = {
    'Endy':    '#4a6fa5',
    'Jeffrey': '#4a9070',
    'Diana':   '#b8976c',
    'Rex':     '#7a5fa0',
    'Alison':  '#b85c78',
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS therapists (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            name             TEXT NOT NULL,
            base_salary      REAL    DEFAULT 0,
            commission_type  TEXT    DEFAULT 'percent',
            commission_value REAL    DEFAULT 0
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
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id      INTEGER NOT NULL REFERENCES patients(id),
            therapist_id    INTEGER NOT NULL REFERENCES therapists(id),
            date            TEXT NOT NULL,
            start_time      TEXT NOT NULL,
            duration        INTEGER NOT NULL DEFAULT 60,
            cost            REAL    NOT NULL DEFAULT 0,
            status          TEXT    NOT NULL DEFAULT 'scheduled',
            notes           TEXT,
            is_designated   INTEGER DEFAULT 1,
            referral_source TEXT,
            created_at      TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS service_records (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id     INTEGER NOT NULL REFERENCES patients(id),
            appointment_id INTEGER,
            record_date    TEXT NOT NULL,
            therapist_id   INTEGER,
            svc_full_body_massage  INTEGER DEFAULT 0,
            svc_local_massage      INTEGER DEFAULT 0,
            svc_stretch            INTEGER DEFAULT 0,
            svc_joint_mobility     INTEGER DEFAULT 0,
            svc_fascia_release     INTEGER DEFAULT 0,
            svc_strength           INTEGER DEFAULT 0,
            svc_core               INTEGER DEFAULT 0,
            svc_balance            INTEGER DEFAULT 0,
            svc_aerobic            INTEGER DEFAULT 0,
            svc_breathing          INTEGER DEFAULT 0,
            svc_posture            INTEGER DEFAULT 0,
            svc_coordination       INTEGER DEFAULT 0,
            area_head_neck         INTEGER DEFAULT 0,
            area_shoulder          INTEGER DEFAULT 0,
            area_upper_back        INTEGER DEFAULT 0,
            area_lower_back        INTEGER DEFAULT 0,
            area_hip               INTEGER DEFAULT 0,
            area_thigh             INTEGER DEFAULT 0,
            area_knee              INTEGER DEFAULT 0,
            area_calf              INTEGER DEFAULT 0,
            area_ankle_foot        INTEGER DEFAULT 0,
            area_upper_limb        INTEGER DEFAULT 0,
            area_full_body         INTEGER DEFAULT 0,
            goal_relaxation        INTEGER DEFAULT 0,
            goal_flexibility       INTEGER DEFAULT 0,
            goal_strength          INTEGER DEFAULT 0,
            goal_posture           INTEGER DEFAULT 0,
            goal_performance       INTEGER DEFAULT 0,
            goal_general_health    INTEGER DEFAULT 0,
            comfort_before         INTEGER DEFAULT 5,
            comfort_after          INTEGER DEFAULT 5,
            content                TEXT,
            feedback               TEXT,
            next_plan              TEXT,
            created_at             TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS session_packages (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id        INTEGER NOT NULL REFERENCES patients(id),
            package_type      TEXT NOT NULL,
            total_sessions    INTEGER NOT NULL,
            used_sessions     INTEGER DEFAULT 0,
            price_per_session REAL NOT NULL,
            purchase_date     TEXT NOT NULL,
            notes             TEXT,
            created_at        TEXT DEFAULT (datetime('now','localtime'))
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
            assessment      TEXT,
            plan            TEXT,
            therapist_notes TEXT,
            created_at      TEXT DEFAULT (datetime('now','localtime'))
        );
    ''')
    if conn.execute("SELECT COUNT(*) FROM therapists").fetchone()[0] == 0:
        conn.executemany("INSERT INTO therapists (name) VALUES (?)",
                         [('Endy',), ('Jeffrey',), ('Diana',)])
    conn.commit()
    conn.close()


def migrate_db():
    """Add new columns to existing databases without losing data."""
    conn = get_db()
    migrations = [
        "ALTER TABLE therapists ADD COLUMN base_salary REAL DEFAULT 0",
        "ALTER TABLE therapists ADD COLUMN commission_type TEXT DEFAULT 'percent'",
        "ALTER TABLE therapists ADD COLUMN commission_value REAL DEFAULT 0",
        "ALTER TABLE appointments ADD COLUMN is_designated INTEGER DEFAULT 1",
        "ALTER TABLE appointments ADD COLUMN referral_source TEXT",
        "ALTER TABLE appointments ADD COLUMN service_type TEXT DEFAULT 'full_treatment'",
        "ALTER TABLE appointments ADD COLUMN payment_method TEXT DEFAULT 'cash'",
        "ALTER TABLE appointments ADD COLUMN payment_status TEXT DEFAULT 'unpaid'",
        "ALTER TABLE appointments ADD COLUMN session_package_id INTEGER DEFAULT NULL",
        "ALTER TABLE appointments ADD COLUMN signature_data TEXT DEFAULT NULL",
        "ALTER TABLE therapists ADD COLUMN work_start TEXT DEFAULT '09:00'",
        "ALTER TABLE therapists ADD COLUMN work_end TEXT DEFAULT '18:00'",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists

    # Add new therapists if not present
    for name in ('Rex', 'Alison'):
        if not conn.execute(
            "SELECT id FROM therapists WHERE name = ?", (name,)
        ).fetchone():
            conn.execute("INSERT INTO therapists (name) VALUES (?)", (name,))

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
    return redirect(url_for('calendar_view'))


@app.route('/calendar')
def calendar_view():
    conn = get_db()
    therapists = conn.execute("SELECT * FROM therapists ORDER BY id").fetchall()
    conn.close()
    return render_template('calendar.html', therapists=therapists)


@app.route('/appointments/api')
def appointments_api():
    """JSON feed for FullCalendar."""
    COLORS = {
        'Endy':    ('#4a6fa5', '#3a5a8f'),
        'Jeffrey': ('#4a9070', '#3a7a5a'),
        'Diana':   ('#b8976c', '#a2845c'),
        'Rex':     ('#7a5fa0', '#6a4f8a'),
        'Alison':  ('#b85c78', '#9a4c65'),
    }
    DEFAULT_COLOR = ('#6b7280', '#4b5563')

    start_str = (request.args.get('start') or '')[:10]
    end_str   = (request.args.get('end')   or '')[:10]
    if not start_str:
        start_str = date.today().isoformat()
    if not end_str:
        end_str = start_str

    conn = get_db()
    rows = conn.execute("""
        SELECT a.*, p.name AS patient_name, t.name AS therapist_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN therapists t ON a.therapist_id = t.id
        WHERE a.date >= ? AND a.date < ? AND a.status != 'cancelled'
        ORDER BY a.date, a.start_time
    """, (start_str, end_str)).fetchall()
    conn.close()

    events = []
    for a in rows:
        bg, border = COLORS.get(a['therapist_name'], DEFAULT_COLOR)
        if a['status'] == 'cancelled':
            bg, border = '#9ca3af', '#6b7280'
        elif a['status'] == 'completed':
            bg = bg + 'bb'  # slightly translucent

        h, m  = map(int, a['start_time'].split(':'))
        total = h * 60 + m + a['duration']
        eh, em = divmod(total, 60)

        events.append({
            'id':    str(a['id']),
            'title': a['patient_name'],
            'start': f"{a['date']}T{a['start_time']}:00",
            'end':   f"{a['date']}T{eh:02d}:{em:02d}:00",
            'backgroundColor': bg,
            'borderColor':     border,
            'editable': a['status'] == 'scheduled',
            'extendedProps': {
                'patient_id':          a['patient_id'],
                'therapist_id':        a['therapist_id'],
                'therapist_name':      a['therapist_name'],
                'cost':                int(a['cost']),
                'duration':            a['duration'],
                'notes':               a['notes'] or '',
                'status':              a['status'],
                'service_type':        a['service_type'] or 'full_treatment',
                'payment_method':      a['payment_method'] or 'cash',
                'payment_status':      a['payment_status'] or 'unpaid',
                'session_package_id':  a['session_package_id'],
            },
        })
    return jsonify(events)


@app.route('/appointments/<int:appt_id>/move', methods=['POST'])
def move_appointment(appt_id):
    """Called by FullCalendar drag-and-drop / resize."""
    data     = request.get_json()
    new_date = data.get('date')
    new_time = data.get('start_time')
    new_dur  = data.get('duration')

    conn = get_db()
    if new_dur:
        conn.execute(
            "UPDATE appointments SET date=?, start_time=?, duration=? WHERE id=?",
            (new_date, new_time, new_dur, appt_id))
    else:
        conn.execute(
            "UPDATE appointments SET date=?, start_time=? WHERE id=?",
            (new_date, new_time, appt_id))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


# ─── appointments ─────────────────────────────────────────────────────────────

@app.route('/appointments/new', methods=['GET', 'POST'])
def new_appointment():
    conn = get_db()
    therapists = conn.execute("SELECT * FROM therapists ORDER BY id").fetchall()
    patients   = conn.execute("SELECT id, name, phone FROM patients ORDER BY name").fetchall()

    if request.method == 'POST':
        f = request.form
        is_designated      = 1 if f.get('is_designated') == '1' else 0
        referral_source    = f.get('referral_source', '') if not is_designated else ''
        conn.execute("""
            INSERT INTO appointments
                (patient_id, therapist_id, date, start_time, duration, cost, notes,
                 is_designated, referral_source, service_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f['patient_id'], f['therapist_id'], f['date'],
              f['start_time'], int(f['duration']), float(f['cost'] or 0),
              f.get('notes', ''), is_designated, referral_source,
              f.get('service_type', 'full_treatment')))
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
        referral_sources=REFERRAL_SOURCES,
        service_types=SERVICE_TYPES,
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
        is_designated      = 1 if f.get('is_designated') == '1' else 0
        referral_source    = f.get('referral_source', '') if not is_designated else ''
        conn.execute("""
            UPDATE appointments
            SET patient_id=?, therapist_id=?, date=?, start_time=?,
                duration=?, cost=?, status=?, notes=?,
                is_designated=?, referral_source=?, service_type=?
            WHERE id=?
        """, (f['patient_id'], f['therapist_id'], f['date'],
              f['start_time'], int(f['duration']), float(f['cost'] or 0),
              f.get('status', 'scheduled'), f.get('notes', ''),
              is_designated, referral_source,
              f.get('service_type', 'full_treatment'), appt_id))
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
        referral_sources=REFERRAL_SOURCES,
        service_types=SERVICE_TYPES,
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
    # Redirect to checkout — completion happens there
    return redirect(url_for('checkout_appointment', appt_id=appt_id))


@app.route('/appointments/<int:appt_id>/checkout', methods=['GET', 'POST'])
def checkout_appointment(appt_id):
    conn = get_db()
    appt = conn.execute("""
        SELECT a.*, p.name AS patient_name, t.name AS therapist_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN therapists t ON a.therapist_id = t.id
        WHERE a.id = ?
    """, (appt_id,)).fetchone()
    if not appt:
        conn.close()
        flash('找不到預約', 'danger')
        return redirect(url_for('calendar_view'))

    if request.method == 'POST':
        method = request.form.get('payment_method', 'cash')
        if method == 'session':
            pkg_id = request.form.get('session_package_id')
            if not pkg_id:
                conn.close()
                flash('請選擇堂數方案', 'danger')
                return redirect(url_for('checkout_appointment', appt_id=appt_id))
            conn.execute("""
                UPDATE appointments
                SET payment_method='session', session_package_id=?, status='completed'
                WHERE id=?
            """, (pkg_id, appt_id))
            conn.commit()
            conn.close()
            return redirect(url_for('sign_appointment', appt_id=appt_id))
        else:
            conn.execute("""
                UPDATE appointments
                SET payment_method=?, payment_status='paid', status='completed',
                    session_package_id=NULL
                WHERE id=?
            """, (method, appt_id))
            conn.commit()
            conn.close()
            flash('結帳完成，已記錄付款', 'success')
            return redirect(url_for('calendar_view', date=appt['date']))

    # GET: load available packages for this patient
    packages = conn.execute("""
        SELECT * FROM session_packages
        WHERE patient_id = ? AND used_sessions < total_sessions
        ORDER BY created_at
    """, (appt['patient_id'],)).fetchall()
    conn.close()
    return render_template('checkout.html', appt=dict(appt), packages=packages)


@app.route('/appointments/<int:appt_id>/sign', methods=['GET', 'POST'])
def sign_appointment(appt_id):
    conn = get_db()
    appt = conn.execute("""
        SELECT a.*, p.name AS patient_name, t.name AS therapist_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN therapists t ON a.therapist_id = t.id
        WHERE a.id = ?
    """, (appt_id,)).fetchone()
    if not appt:
        conn.close()
        flash('找不到預約', 'danger')
        return redirect(url_for('calendar_view'))

    pkg = None
    if appt['session_package_id']:
        pkg = conn.execute(
            "SELECT * FROM session_packages WHERE id = ?", (appt['session_package_id'],)
        ).fetchone()

    if request.method == 'POST':
        sig = request.form.get('signature_data', '')
        conn.execute("""
            UPDATE appointments
            SET status='completed', payment_status='paid', signature_data=?
            WHERE id=?
        """, (sig, appt_id))
        if appt['session_package_id']:
            conn.execute(
                "UPDATE session_packages SET used_sessions = used_sessions + 1 WHERE id=?",
                (appt['session_package_id'],)
            )
        conn.commit()
        conn.close()
        flash('簽名完成，已銷課 1 堂', 'success')
        return redirect(url_for('calendar_view', date=appt['date']))

    conn.close()
    return render_template('sign.html',
        appt=dict(appt),
        pkg=dict(pkg) if pkg else None,
    )


@app.route('/api/patients/<int:patient_id>/packages')
def patient_packages_api(patient_id):
    conn = get_db()
    pkgs = conn.execute("""
        SELECT * FROM session_packages
        WHERE patient_id = ? AND used_sessions < total_sessions
        ORDER BY created_at
    """, (patient_id,)).fetchall()
    conn.close()
    return jsonify([{
        'id':                p['id'],
        'package_type':      p['package_type'],
        'remaining':         p['total_sessions'] - p['used_sessions'],
        'total':             p['total_sessions'],
        'price_per_session': p['price_per_session'],
        'purchase_date':     p['purchase_date'],
    } for p in pkgs])


@app.route('/patients/<int:patient_id>/packages/new', methods=['POST'])
def new_package(patient_id):
    f = request.form
    pkg_type = f.get('package_type')
    pkg_info = next((p for p in PACKAGE_TYPES if p[0] == pkg_type), None)
    if pkg_info:
        conn = get_db()
        conn.execute("""
            INSERT INTO session_packages
                (patient_id, package_type, total_sessions, price_per_session, purchase_date, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (patient_id, pkg_type, pkg_info[2], pkg_info[3],
              f.get('purchase_date', date.today().isoformat()),
              f.get('notes', '')))
        conn.commit()
        conn.close()
        flash(f'已購買 {pkg_info[1]}（{pkg_info[2]}堂，每堂 NT${pkg_info[3]}）', 'success')
    return redirect(url_for('patient_records', patient_id=patient_id))


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

# Service types that map to service record (health promotion), rest → medical record
SERVICE_RECORD_TYPES = {'exercise', 'space_rental'}

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

SERVICE_RECORD_BOOL_FIELDS = [
    'svc_full_body_massage','svc_local_massage','svc_stretch','svc_joint_mobility',
    'svc_fascia_release','svc_strength','svc_core','svc_balance','svc_aerobic',
    'svc_breathing','svc_posture','svc_coordination',
    'area_head_neck','area_shoulder','area_upper_back','area_lower_back',
    'area_hip','area_thigh','area_knee','area_calf','area_ankle_foot',
    'area_upper_limb','area_full_body',
    'goal_relaxation','goal_flexibility','goal_strength','goal_posture',
    'goal_performance','goal_general_health',
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
    service_records = conn.execute("""
        SELECT sr.*, t.name AS therapist_name
        FROM service_records sr
        LEFT JOIN therapists t ON sr.therapist_id = t.id
        WHERE sr.patient_id = ?
        ORDER BY sr.record_date DESC, sr.id DESC
    """, (patient_id,)).fetchall()
    packages = conn.execute("""
        SELECT * FROM session_packages WHERE patient_id = ? ORDER BY created_at DESC
    """, (patient_id,)).fetchall()
    conn.close()
    return render_template('patient_records.html',
        patient=patient, records=records, service_records=service_records,
        packages=packages, package_types=PACKAGE_TYPES, today=date.today().isoformat()
    )


@app.route('/service-records/new', methods=['GET', 'POST'])
def new_service_record():
    conn = get_db()
    patients   = conn.execute("SELECT id, name FROM patients ORDER BY name").fetchall()
    therapists = conn.execute("SELECT * FROM therapists ORDER BY id").fetchall()

    if request.method == 'POST':
        f    = request.form
        vals = {field: (1 if field in f else 0) for field in SERVICE_RECORD_BOOL_FIELDS}
        cols = ', '.join(SERVICE_RECORD_BOOL_FIELDS)
        phs  = ', '.join(':' + field for field in SERVICE_RECORD_BOOL_FIELDS)
        conn.execute(f"""
            INSERT INTO service_records
                (patient_id, appointment_id, record_date, therapist_id,
                 comfort_before, comfort_after, content, feedback, next_plan,
                 {cols})
            VALUES
                (:patient_id, :appointment_id, :record_date, :therapist_id,
                 :comfort_before, :comfort_after, :content, :feedback, :next_plan,
                 {phs})
        """, {
            'patient_id':     f['patient_id'],
            'appointment_id': f.get('appointment_id') or None,
            'record_date':    f['record_date'],
            'therapist_id':   f.get('therapist_id') or None,
            'comfort_before': int(f.get('comfort_before', 5)),
            'comfort_after':  int(f.get('comfort_after', 5)),
            'content':        f.get('content', ''),
            'feedback':       f.get('feedback', ''),
            'next_plan':      f.get('next_plan', ''),
            **vals,
        })
        conn.commit()
        pid = f['patient_id']
        conn.close()
        flash('服務紀錄已新增', 'success')
        return redirect(url_for('patient_records', patient_id=pid))

    conn.close()
    return render_template('service_record.html',
        patients=patients,
        therapists=therapists,
        record=None,
        patient_id=request.args.get('patient_id', ''),
        appointment_id=request.args.get('appointment_id', ''),
        today=date.today().isoformat(),
    )


# ─── report ──────────────────────────────────────────────────────────────────

@app.route('/report')
def report():
    period = request.args.get('period', 'day')
    if period not in ('day', 'week', 'month', 'year'):
        period = 'day'
    date_str = request.args.get('date', date.today().isoformat())
    try:
        anchor = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        anchor = date.today()

    # Compute date range and navigation anchors for each period
    if period == 'week':
        week_start   = anchor - timedelta(days=anchor.weekday())
        week_end     = week_start + timedelta(days=4)
        date_from    = week_start
        date_to      = week_end
        prev_anchor  = (week_start - timedelta(days=7)).isoformat()
        next_anchor  = (week_start + timedelta(days=7)).isoformat()
        period_label = (f"{week_start.year}年 "
                        f"{week_start.month}月{week_start.day}日"
                        f" – {week_end.month}月{week_end.day}日")
    elif period == 'month':
        month_start = anchor.replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)
        date_from    = month_start
        date_to      = month_end
        prev_anchor  = (month_start - timedelta(days=1)).replace(day=1).isoformat()
        next_anchor  = (month_end + timedelta(days=1)).isoformat()
        period_label = f"{anchor.year}年{anchor.month}月"
    elif period == 'year':
        date_from    = anchor.replace(month=1, day=1)
        date_to      = anchor.replace(month=12, day=31)
        prev_anchor  = anchor.replace(year=anchor.year - 1).isoformat()
        next_anchor  = anchor.replace(year=anchor.year + 1).isoformat()
        period_label = f"{anchor.year}年"
    else:  # day
        period       = 'day'
        date_from    = anchor
        date_to      = anchor
        prev_anchor  = prev_workday(anchor).isoformat()
        next_anchor  = next_workday(anchor).isoformat()
        period_label = (f"{anchor.year}年{anchor.month}月{anchor.day}日"
                        f"（週{WEEKDAY_ZH[anchor.weekday()]}）")

    conn = get_db()
    therapists = conn.execute("SELECT * FROM therapists ORDER BY id").fetchall()
    rows = conn.execute("""
        SELECT a.*, p.name AS patient_name, t.name AS therapist_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN therapists t ON a.therapist_id = t.id
        WHERE a.date >= ? AND a.date <= ?
        ORDER BY a.date, a.therapist_id, a.start_time
    """, (date_from.isoformat(), date_to.isoformat())).fetchall()
    conn.close()

    active  = [a for a in rows if a['status'] != 'cancelled']
    revenue = sum(a['cost'] for a in rows if a['status'] == 'completed')

    t_stats = {}
    for t in therapists:
        ta = [a for a in rows if a['therapist_id'] == t['id']]
        t_stats[t['id']] = {
            'name':         t['name'],
            'count':        len([a for a in ta if a['status'] != 'cancelled']),
            'completed':    len([a for a in ta if a['status'] == 'completed']),
            'revenue':      sum(a['cost'] for a in ta if a['status'] == 'completed'),
            'appointments': ta,
        }

    # Daily breakdown (week / month views)
    daily_breakdown = []
    if period in ('week', 'month'):
        by_date = defaultdict(list)
        for a in rows:
            by_date[a['date']].append(a)
        d = date_from
        while d <= date_to:
            if d.weekday() < 5:
                da = by_date[d.isoformat()]
                daily_breakdown.append({
                    'date':      d.isoformat(),
                    'weekday':   WEEKDAY_ZH[d.weekday()],
                    'count':     len([a for a in da if a['status'] != 'cancelled']),
                    'completed': len([a for a in da if a['status'] == 'completed']),
                    'revenue':   sum(a['cost'] for a in da if a['status'] == 'completed'),
                })
            d += timedelta(days=1)

    # Monthly breakdown (year view)
    monthly_breakdown = []
    if period == 'year':
        by_month = defaultdict(list)
        for a in rows:
            by_month[a['date'][:7]].append(a)
        for m in range(1, 13):
            key = f"{anchor.year}-{m:02d}"
            ma  = by_month[key]
            monthly_breakdown.append({
                'key':       key,
                'label':     f"{m}月",
                'count':     len([a for a in ma if a['status'] != 'cancelled']),
                'completed': len([a for a in ma if a['status'] == 'completed']),
                'revenue':   sum(a['cost'] for a in ma if a['status'] == 'completed'),
            })

    return render_template('report.html',
        period=period,
        period_label=period_label,
        anchor=anchor,
        date_from=date_from,
        date_to=date_to,
        prev_anchor=prev_anchor,
        next_anchor=next_anchor,
        therapists=therapists,
        appointments=rows,
        t_stats=t_stats,
        total=len(active),
        revenue=revenue,
        report_date=anchor,
        weekday=WEEKDAY_ZH[anchor.weekday()],
        daily_breakdown=daily_breakdown,
        monthly_breakdown=monthly_breakdown,
    )


# ─── therapist profiles ──────────────────────────────────────────────────────

@app.route('/therapists/<int:therapist_id>', methods=['GET', 'POST'])
def therapist_profile(therapist_id):
    conn = get_db()
    t = conn.execute("SELECT * FROM therapists WHERE id = ?", (therapist_id,)).fetchone()
    if not t:
        conn.close()
        flash('找不到治療師', 'danger')
        return redirect(url_for('calendar_view'))

    if request.method == 'POST':
        work_start = request.form.get('work_start', '09:00')
        work_end   = request.form.get('work_end',   '18:00')
        conn.execute(
            "UPDATE therapists SET work_start=?, work_end=? WHERE id=?",
            (work_start, work_end, therapist_id)
        )
        conn.commit()
        conn.close()
        flash('上班時段已更新', 'success')
        return redirect(url_for('therapist_profile', therapist_id=therapist_id))

    # ── Period / date handling (same logic as report route) ──
    period   = request.args.get('period', 'month')
    if period not in ('day', 'week', 'month', 'year'):
        period = 'month'
    date_str = request.args.get('date', date.today().isoformat())
    try:
        anchor = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        anchor = date.today()

    if period == 'week':
        week_start   = anchor - timedelta(days=anchor.weekday())
        week_end     = week_start + timedelta(days=4)
        date_from    = week_start
        date_to      = week_end
        prev_anchor  = (week_start - timedelta(days=7)).isoformat()
        next_anchor  = (week_start + timedelta(days=7)).isoformat()
        period_label = (f"{week_start.year}年 "
                        f"{week_start.month}月{week_start.day}日"
                        f" – {week_end.month}月{week_end.day}日")
    elif period == 'month':
        month_start  = anchor.replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)
        date_from    = month_start
        date_to      = month_end
        prev_anchor  = (month_start - timedelta(days=1)).replace(day=1).isoformat()
        next_anchor  = (month_end + timedelta(days=1)).isoformat()
        period_label = f"{anchor.year}年{anchor.month}月"
    elif period == 'year':
        date_from    = anchor.replace(month=1, day=1)
        date_to      = anchor.replace(month=12, day=31)
        prev_anchor  = anchor.replace(year=anchor.year - 1).isoformat()
        next_anchor  = anchor.replace(year=anchor.year + 1).isoformat()
        period_label = f"{anchor.year}年"
    else:  # day
        date_from    = anchor
        date_to      = anchor
        prev_anchor  = prev_workday(anchor).isoformat()
        next_anchor  = next_workday(anchor).isoformat()
        period_label = (f"{anchor.year}年{anchor.month}月{anchor.day}日"
                        f"（週{WEEKDAY_ZH[anchor.weekday()]}）")

    rows = conn.execute("""
        SELECT a.*, p.name AS patient_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        WHERE a.therapist_id = ? AND a.date >= ? AND a.date <= ?
        ORDER BY a.date, a.start_time
    """, (therapist_id, date_from.isoformat(), date_to.isoformat())).fetchall()
    conn.close()

    active   = [r for r in rows if r['status'] != 'cancelled']
    completed = [r for r in rows if r['status'] == 'completed']
    revenue  = sum(r['cost'] for r in completed)

    # Daily breakdown (week / month)
    daily_breakdown = []
    if period in ('week', 'month'):
        by_date = defaultdict(list)
        for a in rows:
            by_date[a['date']].append(a)
        d = date_from
        while d <= date_to:
            if d.weekday() < 5:
                da = by_date[d.isoformat()]
                daily_breakdown.append({
                    'date':      d.isoformat(),
                    'weekday':   WEEKDAY_ZH[d.weekday()],
                    'count':     len([a for a in da if a['status'] != 'cancelled']),
                    'completed': len([a for a in da if a['status'] == 'completed']),
                    'revenue':   sum(a['cost'] for a in da if a['status'] == 'completed'),
                })
            d += timedelta(days=1)

    # Monthly breakdown (year)
    monthly_breakdown = []
    if period == 'year':
        by_month = defaultdict(list)
        for a in rows:
            by_month[a['date'][:7]].append(a)
        for m in range(1, 13):
            key = f"{anchor.year}-{m:02d}"
            ma  = by_month[key]
            monthly_breakdown.append({
                'key':       key,
                'label':     f"{m}月",
                'count':     len([a for a in ma if a['status'] != 'cancelled']),
                'completed': len([a for a in ma if a['status'] == 'completed']),
                'revenue':   sum(a['cost'] for a in ma if a['status'] == 'completed'),
            })

    return render_template('therapist_profile.html',
        t=dict(t),
        color=THERAPIST_COLORS.get(t['name'], '#6b7280'),
        period=period,
        period_label=period_label,
        anchor=anchor,
        prev_anchor=prev_anchor,
        next_anchor=next_anchor,
        appointments=rows,
        active_count=len(active),
        session_count=len(completed),
        revenue=revenue,
        daily_breakdown=daily_breakdown,
        monthly_breakdown=monthly_breakdown,
    )


# ─── salary ──────────────────────────────────────────────────────────────────

@app.route('/salary')
def salary():
    therapist_id = request.args.get('therapist_id', type=int)
    conn = get_db()
    therapists = conn.execute("SELECT * FROM therapists ORDER BY id").fetchall()

    # No therapist selected → show selector
    if not therapist_id:
        conn.close()
        return render_template('salary_select.html', therapists=therapists)

    t = next((x for x in therapists if x['id'] == therapist_id), None)
    if not t:
        conn.close()
        flash('找不到治療師', 'danger')
        return render_template('salary_select.html', therapists=therapists)

    month_str = request.args.get('month', date.today().strftime('%Y-%m'))
    try:
        month_start = datetime.strptime(month_str + '-01', '%Y-%m-%d').date()
    except ValueError:
        month_start = date.today().replace(day=1)

    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)

    prev_month = (month_start - timedelta(days=1)).strftime('%Y-%m')
    next_month = (month_end  + timedelta(days=1)).strftime('%Y-%m')

    completed = conn.execute("""
        SELECT a.*, p.name AS patient_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        WHERE a.therapist_id = ? AND a.date >= ? AND a.date <= ? AND a.status = 'completed'
        ORDER BY a.date, a.start_time
    """, (t['id'], month_start.isoformat(), month_end.isoformat())).fetchall()
    conn.close()

    total_revenue = sum(r['cost'] for r in completed)
    session_count = len(completed)
    base    = t['base_salary']      or 0
    c_type  = t['commission_type']  or 'percent'
    c_value = t['commission_value'] or 0
    commission = (total_revenue * c_value / 100) if c_type == 'percent' else (session_count * c_value)

    salary_data = {
        'id':               t['id'],
        'name':             t['name'],
        'base_salary':      base,
        'commission_type':  c_type,
        'commission_value': c_value,
        'session_count':    session_count,
        'revenue':          total_revenue,
        'commission':       commission,
        'total_salary':     base + commission,
        'appointments':     [dict(r) for r in completed],
    }

    return render_template('salary.html',
        t=dict(t),
        month_str=month_str,
        month_start=month_start,
        salary_data=salary_data,
        prev_month=prev_month,
        next_month=next_month,
        therapist_id=therapist_id,
        color=THERAPIST_COLORS.get(t['name'], '#6b7280'),
    )


@app.route('/therapists/settings', methods=['GET', 'POST'])
def therapist_settings():
    conn = get_db()
    therapists = conn.execute("SELECT * FROM therapists ORDER BY id").fetchall()

    if request.method == 'POST':
        for t in therapists:
            tid        = t['id']
            base       = float(request.form.get(f'base_{tid}',       0) or 0)
            c_type     = request.form.get(f'ctype_{tid}',   'percent')
            c_value    = float(request.form.get(f'cvalue_{tid}',    0) or 0)
            work_start = request.form.get(f'wstart_{tid}', '09:00')
            work_end   = request.form.get(f'wend_{tid}',   '18:00')
            conn.execute("""
                UPDATE therapists
                SET base_salary=?, commission_type=?, commission_value=?,
                    work_start=?, work_end=?
                WHERE id=?
            """, (base, c_type, c_value, work_start, work_end, tid))
        conn.commit()
        conn.close()
        flash('薪資設定已更新', 'success')
        return redirect(url_for('therapist_settings'))

    conn.close()
    return render_template('therapist_settings.html', therapists=therapists)


# ─── main ────────────────────────────────────────────────────────────────────

# init_db() and migrate_db() are called at import time so WSGI servers
# (PythonAnywhere, Gunicorn) initialise the database without needing __main__.
init_db()
migrate_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
