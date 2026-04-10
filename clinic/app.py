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
        WHERE a.date >= ? AND a.date < ?
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
                'patient_id':     a['patient_id'],
                'therapist_id':   a['therapist_id'],
                'therapist_name': a['therapist_name'],
                'cost':         int(a['cost']),
                'duration':     a['duration'],
                'notes':        a['notes'] or '',
                'status':       a['status'],
                'service_type': a['service_type'] or 'full_treatment',
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
        is_designated   = 1 if f.get('is_designated') == '1' else 0
        referral_source = f.get('referral_source', '') if not is_designated else ''
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
        is_designated   = 1 if f.get('is_designated') == '1' else 0
        referral_source = f.get('referral_source', '') if not is_designated else ''
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


# ─── salary ──────────────────────────────────────────────────────────────────

@app.route('/salary')
def salary():
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

    conn = get_db()
    therapists = conn.execute("SELECT * FROM therapists ORDER BY id").fetchall()

    salary_data = []
    for t in therapists:
        completed = conn.execute("""
            SELECT * FROM appointments
            WHERE therapist_id = ? AND date >= ? AND date <= ? AND status = 'completed'
        """, (t['id'], month_start.isoformat(), month_end.isoformat())).fetchall()

        total_revenue = sum(r['cost'] for r in completed)
        session_count = len(completed)
        base    = t['base_salary']      or 0
        c_type  = t['commission_type']  or 'percent'
        c_value = t['commission_value'] or 0

        if c_type == 'percent':
            commission = total_revenue * c_value / 100
        else:  # per_session
            commission = session_count * c_value

        salary_data.append({
            'id':               t['id'],
            'name':             t['name'],
            'base_salary':      base,
            'commission_type':  c_type,
            'commission_value': c_value,
            'session_count':    session_count,
            'revenue':          total_revenue,
            'commission':       commission,
            'total_salary':     base + commission,
        })

    conn.close()
    return render_template('salary.html',
        month_str=month_str,
        month_start=month_start,
        salary_data=salary_data,
        prev_month=prev_month,
        next_month=next_month,
    )


@app.route('/therapists/settings', methods=['GET', 'POST'])
def therapist_settings():
    conn = get_db()
    therapists = conn.execute("SELECT * FROM therapists ORDER BY id").fetchall()

    if request.method == 'POST':
        for t in therapists:
            tid     = t['id']
            base    = float(request.form.get(f'base_{tid}',   0) or 0)
            c_type  = request.form.get(f'ctype_{tid}',  'percent')
            c_value = float(request.form.get(f'cvalue_{tid}', 0) or 0)
            conn.execute("""
                UPDATE therapists
                SET base_salary=?, commission_type=?, commission_value=?
                WHERE id=?
            """, (base, c_type, c_value, tid))
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
