# CLAUDE.md

This file provides guidance to AI assistants working with this repository.

---

## 專案概覽

**鉑適物理治療診所管理系統**（The Platinum Physical Therapy & Wellness Center）

- **Repository:** `endyphysio11/Claude-test`
- **Default branch:** `main`
- **部署平台:** PythonAnywhere（免費 Beginner 方案）
- **技術棧:** Flask 3.x · SQLite（stdlib sqlite3）· Bootstrap 5.3.2 · FullCalendar 6.1.11

### 更新到 PythonAnywhere 的方法
```bash
# 在 PythonAnywhere Bash 執行：
cd ~/Claude-test && git pull origin main
# 然後到 Web 頁籤按 Reload
```

---

## 目錄結構

```
Claude-test/
├── CLAUDE.md
├── README.md
└── clinic/
    ├── app.py                  # Flask 主程式（所有路由）
    ├── clinic.db               # SQLite 資料庫（PythonAnywhere 上）
    ├── wsgi.py                 # PythonAnywhere WSGI 入口
    ├── setup.sh                # 首次部署腳本
    ├── update.sh               # 更新腳本
    ├── static/
    │   ├── style.css           # 全域樣式（品牌設計系統）
    │   └── script.js           # 共用 JS
    └── templates/
        ├── base.html           # 共用版型（含 SVG logo、導覽列）
        ├── calendar.html       # 預約行事曆（FullCalendar）
        ├── appointment_form.html  # 新增 / 編輯預約
        ├── patients.html       # 個案列表
        ├── patient_form.html   # 新增 / 編輯個案
        ├── patient_records.html   # 個案病歷列表
        ├── medical_record.html    # 新增病歷（勾選表單）
        ├── report.html         # 報表（日 / 週 / 月 / 年）
        ├── salary.html         # 薪資計算
        └── therapist_settings.html  # 薪資公式設定
```

---

## 資料庫結構

### therapists
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | INTEGER PK | |
| name | TEXT | |
| base_salary | REAL | 底薪 |
| commission_type | TEXT | `percent` 或 `per_session` |
| commission_value | REAL | 抽成比例(%)或每診次金額 |

**目前治療師：** Endy、Jeffrey、Diana、Rex、Alison

### patients
name、phone、birth_date、gender、address、emergency_contact、notes、created_at

### appointments
| 欄位 | 說明 |
|------|------|
| patient_id / therapist_id | FK |
| date / start_time / duration | 時間相關 |
| cost | 費用 |
| status | `scheduled` / `completed` / `cancelled` |
| service_type | 見下方服務項目清單 |
| is_designated | 1=指定治療師 0=非指定 |
| referral_source | 非指定時的來源渠道 |
| notes | 備註 |

### medical_records
patient_id、appointment_id、record_date、therapist_id、pain_score、
14個症狀欄位（symptom_*）、4個疼痛性質（pain_*）、8個病史（history_*）、
10個治療方式（treatment_*）、assessment、plan、therapist_notes

---

## 服務項目（SERVICE_TYPES）

| value | 顯示名稱 | 預設費用 |
|-------|---------|---------|
| `assessment` | 單純評估衛教 | NT$1,500 |
| `full_treatment` | 完整治療 | NT$2,500 / 2,800 |
| `exercise` | 運動訓練 | NT$2,500 / 2,800 |
| `winback` | 高階儀器 — Winback | NT$1,500 |
| `shockwave` | 高階儀器 — 震波 | NT$1,500 |
| `space_rental` | 場租 | NT$300 |

---

## 主要路由

| 路由 | 功能 |
|------|------|
| `GET /` | 導向行事曆 |
| `GET /calendar` | FullCalendar 主畫面 |
| `GET /appointments/api` | JSON feed（FullCalendar 用） |
| `POST /appointments/<id>/move` | 拖曳 / 縮放儲存 |
| `GET/POST /appointments/new` | 新增預約 |
| `GET/POST /appointments/<id>/edit` | 編輯預約 |
| `POST /appointments/<id>/complete` | 標記完成 |
| `POST /appointments/<id>/cancel` | 取消預約 |
| `GET /patients` | 個案列表（支援搜尋） |
| `GET/POST /patients/new` | 新增個案 |
| `GET/POST /patients/<id>/edit` | 編輯個案 |
| `GET /patients/<id>/records` | 個案病歷列表 |
| `GET/POST /records/new` | 新增病歷 |
| `GET /report` | 報表（?period=day/week/month/year&date=YYYY-MM-DD） |
| `GET /salary` | 薪資計算（?month=YYYY-MM） |
| `GET/POST /therapists/settings` | 薪資公式設定 |

---

## 設計系統（style.css）

品牌色彩（鉑適物理治療官方品牌色）：
- `--brand-dark: #1a4f72`（深藍綠，標題、主按鈕）
- `--gold: #2e7faa`（中藍綠，強調色、連結）
- `--gold-light: #e8f4f9`（淡藍，背景色塊）
- `--gold-mid: #6db3ce`（中藍，邊框）
- `--radius: 14px`、按鈕全部 `border-radius: 50px`（膠囊形）

治療師行事曆顏色：
- Endy `#4a6fa5` · Jeffrey `#4a9070` · Diana `#b8976c`
- Rex `#7a5fa0` · Alison `#b85c78`

---

## 待開發功能（已規劃，尚未實作）

- **自動通知 / 追蹤**：預約前提醒、治療後追蹤。需選擇管道（LINE Messaging API 最適合台灣用戶，或 Email）並設定 PythonAnywhere Scheduled Task。

---

## Git 規範

```bash
# 提交
git add <specific-files>
git commit -m "imperative mood message"
git push origin main

# 不可直接 push 到 main 以外的 branch（除非被指定）
# 不可 amend 已 push 的 commit
```

Commit message 使用祈使句：Add / Fix / Update / Remove

---

## 開發原則

- 修改現有檔案優先，非必要不新增檔案
- 不加超出需求的功能或抽象層
- 只在邏輯不自明時才加註解
- 不 commit `.env`、credentials 或 `clinic.db`
- 系統邊界（使用者輸入）才做驗證，不過度防禦
