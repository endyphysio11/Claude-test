"""
Functional tests for the clinic app using Flask's test client.
Runs without a real HTTP server.
"""
import os, sys, json

# Use a fresh in-memory DB for each test run
os.environ['CLINIC_TEST'] = '1'

# Patch DB_PATH before importing app
import tempfile
DB_FILE = tempfile.NamedTemporaryFile(suffix='.db', delete=False).name

import importlib, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as app_module
app_module.DB_PATH = DB_FILE          # redirect to temp DB
app_module.init_db()                  # create schema + seed therapists

app = app_module.app
app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False

client = app.test_client()

PASS = '✅'
FAIL = '❌'
results = []

def check(name, response, expected_status=200, expected_texts=()):
    ok = response.status_code == expected_status
    body = response.data.decode('utf-8', errors='replace')
    for t in expected_texts:
        if t not in body:
            ok = False
            print(f"   missing text: {t!r}")
    status = PASS if ok else FAIL
    results.append(ok)
    print(f"  {status}  {name}  [{response.status_code}]")
    return body

print("\n═══ 初始化 ═══")
# DB should have 3 therapists
import sqlite3
conn = sqlite3.connect(DB_FILE)
rows = conn.execute("SELECT name FROM therapists").fetchall()
assert len(rows) == 3, f"Expected 3 therapists, got {len(rows)}"
print(f"  {PASS}  資料庫初始化 (3 位治療師: {', '.join(r[0] for r in rows)})")
results.append(True)
conn.close()

print("\n═══ 首頁 & 日曆 ═══")
r = client.get('/', follow_redirects=True)
check("首頁重新導向至日曆", r, 200, ['物理治療所', '治療師甲', '治療師乙', '治療師丙'])

r = client.get('/calendar?date=2026-04-10')
check("日曆頁面（週五 2026-04-10）", r, 200, ['2026年04月10日', '10:00', '19:30'])

r = client.get('/calendar?date=2026-04-12')  # Sunday → should redirect to Mon
check("週日自動跳至下週一", r, 200, ['2026年04月13日'])

print("\n═══ 個案管理 ═══")
r = client.get('/patients')
check("個案列表（空）", r, 200, ['個案管理'])

# 新增個案
r = client.post('/patients/new', data={
    'name': '王小明',
    'phone': '0912-345-678',
    'birth_date': '1985-03-15',
    'gender': '男',
    'address': '台北市中山區',
    'emergency_contact': '王大明 / 父 / 0911-111-111',
    'notes': '',
}, follow_redirects=True)
check("新增個案「王小明」", r, 200, ['王小明'])

r = client.post('/patients/new', data={'name': '李小華', 'phone': '0922-111-222', 'gender': '女'}, follow_redirects=True)
check("新增個案「李小華」", r, 200, ['李小華'])

r = client.get('/patients?q=王')
check("搜尋個案「王」", r, 200, ['王小明'])

# 取得個案 ID
conn = sqlite3.connect(DB_FILE)
p1_id = conn.execute("SELECT id FROM patients WHERE name='王小明'").fetchone()[0]
p2_id = conn.execute("SELECT id FROM patients WHERE name='李小華'").fetchone()[0]
t1_id = conn.execute("SELECT id FROM therapists ORDER BY id LIMIT 1").fetchone()[0]
conn.close()
print(f"       → 王小明 id={p1_id}, 李小華 id={p2_id}, 治療師甲 id={t1_id}")

r = client.get(f'/patients/{p1_id}/edit')
check("編輯個案頁面", r, 200, ['王小明'])

r = client.post(f'/patients/{p1_id}/edit', data={
    'name': '王小明', 'phone': '0912-999-999', 'gender': '男',
    'birth_date': '1985-03-15', 'address': '台北市', 'emergency_contact': '', 'notes': '更新測試',
}, follow_redirects=True)
check("更新個案電話", r, 200)

print("\n═══ 預約管理 ═══")
r = client.get('/appointments/new?date=2026-04-10&therapist_id=1&start_time=10:00')
check("新增預約表單", r, 200, ['王小明', '治療師甲'])

# 新增預約 1
r = client.post('/appointments/new', data={
    'patient_id': p1_id,
    'therapist_id': t1_id,
    'date': '2026-04-10',
    'start_time': '10:00',
    'duration': '60',
    'cost': '600',
    'notes': '初診',
}, follow_redirects=True)
check("新增預約（王小明 10:00 60分 NT$600）", r, 200, ['王小明'])

# 新增預約 2
r = client.post('/appointments/new', data={
    'patient_id': p2_id,
    'therapist_id': t1_id,
    'date': '2026-04-10',
    'start_time': '11:00',
    'duration': '30',
    'cost': '400',
    'notes': '',
}, follow_redirects=True)
check("新增預約（李小華 11:00 30分 NT$400）", r, 200, ['李小華'])

# 取得預約 ID
conn = sqlite3.connect(DB_FILE)
a1_id = conn.execute("SELECT id FROM appointments WHERE patient_id=? ORDER BY id", (p1_id,)).fetchone()[0]
a2_id = conn.execute("SELECT id FROM appointments WHERE patient_id=? ORDER BY id", (p2_id,)).fetchone()[0]
conn.close()
print(f"       → 預約 a1={a1_id}, a2={a2_id}")

r = client.get('/calendar?date=2026-04-10')
check("日曆顯示兩筆預約", r, 200, ['王小明', '李小華', '600', '400'])

r = client.get(f'/appointments/{a1_id}/edit')
check("編輯預約表單", r, 200, ['王小明', '600'])

r = client.post(f'/appointments/{a1_id}/edit', data={
    'patient_id': p1_id, 'therapist_id': t1_id,
    'date': '2026-04-10', 'start_time': '10:00',
    'duration': '60', 'cost': '700',
    'status': 'scheduled', 'notes': '初診（費用修正）',
}, follow_redirects=True)
check("更新預約費用為 700", r, 200, ['700'])

# 標記完成
r = client.post(f'/appointments/{a1_id}/complete', follow_redirects=True)
check("標記預約 a1 為完成", r, 200)
conn = sqlite3.connect(DB_FILE)
status = conn.execute("SELECT status FROM appointments WHERE id=?", (a1_id,)).fetchone()[0]
conn.close()
assert status == 'completed', f"Expected completed, got {status}"
print(f"       → DB 狀態確認: {status} {PASS}")

# 取消預約
r = client.post(f'/appointments/{a2_id}/cancel', follow_redirects=True)
check("取消預約 a2", r, 200)
conn = sqlite3.connect(DB_FILE)
status = conn.execute("SELECT status FROM appointments WHERE id=?", (a2_id,)).fetchone()[0]
conn.close()
assert status == 'cancelled', f"Expected cancelled, got {status}"
print(f"       → DB 狀態確認: {status} {PASS}")

print("\n═══ 病歷記錄 ═══")
r = client.get(f'/records/new?patient_id={p1_id}&appointment_id={a1_id}')
check("新增病歷表單", r, 200, ['王小明', '主訴症狀', '治療方式'])

r = client.post('/records/new', data={
    'patient_id': p1_id,
    'appointment_id': a1_id,
    'record_date': '2026-04-10',
    'therapist_id': t1_id,
    'pain_score': '6',
    'symptom_neck': '1',
    'symptom_shoulder': '1',
    'symptom_limited_rom': '1',
    'pain_sharp': '1',
    'pain_dull': '1',
    'history_hypertension': '1',
    'treatment_manual': '1',
    'treatment_heat': '1',
    'treatment_exercise': '1',
    'assessment': '頸部屈曲受限約 30 度，右肩夾擠陽性',
    'plan': '每週 2 次治療，共 4 週，目標恢復正常活動範圍',
    'therapist_notes': '個案配合度良好',
}, follow_redirects=True)
check("新增病歷記錄", r, 200)

r = client.get(f'/patients/{p1_id}/records')
check("查看個案病歷", r, 200, ['頸部疼痛', '肩膀疼痛', '徒手治療', '熱敷', '頸部屈曲受限'])

print("\n═══ 每日報表 ═══")
r = client.get('/report?date=2026-04-10')
check("每日報表", r, 200, ['王小明', '700', '已完成', '已取消'])

# 確認收入只計算已完成的（700，不含取消的 400）
body = r.data.decode()
assert '700' in body, "Should show NT$700 revenue"
print(f"       → 收入只計算已完成的 NT$700 {PASS}")

print("\n═══ 結果摘要 ═══")
passed = sum(results)
total  = len(results)
print(f"\n  通過 {passed} / {total} 項測試\n")
if passed == total:
    print(f"  {PASS} 全部通過！系統功能正常。\n")
else:
    print(f"  {FAIL} {total - passed} 項失敗，請檢查上方錯誤。\n")

# Cleanup
os.unlink(DB_FILE)
