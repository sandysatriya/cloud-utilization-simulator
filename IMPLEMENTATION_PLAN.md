# Rencana Implementasi — Cloud Utilization & Rightsizing Simulator

Status: **IMPLEMENTED v0.1.0 — MENUNGGU REVIEW**
Tanggal rencana: 2026-11-21
Acuan: `PROJECT_BRIEF.md` (versi Cloud Utilization & Rightsizing Simulator)

Kode sudah diimplementasikan sampai MVP lokal. Dokumen ini tetap menjadi catatan
rencana awal; keputusan yang berubah saat implementasi dicatat di bagian 1.3.
Bukti pengujian ada di `docs/hasil_pengujian.md`. Aplikasi belum dianggap
disetujui sampai review pengguna selesai.

---

## 1. Ringkasan & Prinsip

Aplikasi lokal satu pengguna untuk menganalisis data historis utilization
server, membandingkan periode/baseline, dan menyimulasikan perubahan kapasitas.
Aplikasi hanya membaca data yang diimpor pengguna dan menyimpan hasil analisis
di SQLite lokal. Aplikasi **tidak** terhubung ke cloud, tidak meminta
kredensial, tidak melakukan resize, dan tidak mengeksekusi perintah cloud.

### 1.1 Prinsip yang mengikat desain

1. Data kosong tidak pernah diperlakukan sebagai nol dan gap tidak diisi
   otomatis.
2. Duplikat/konflik selalu ditampilkan; tidak ada pemilihan nilai secara diam-diam.
3. Setiap angka turunan menyertakan jumlah sampel dan metode yang dipakai.
4. Kelengkapan data hanya dihitung jika interval pengamatan diketahui.
5. Statistik sumber (Average/Maximum/lainnya) dan interval tidak dicampur tanpa
   aturan yang jelas; MVP **memblokir** pencampuran metadata yang berbeda.
6. Tidak ada rekomendasi resize otomatis. Hasil simulasi selalu berlabel estimasi
   dengan asumsi beban tetap.
7. KPI tidak dihitung sebelum formula/konfigurasi disetujui pengguna.
8. Tidak ada formula bebas, `eval`, atau eksekusi kode dari input pengguna.
9. Semua teks dari pengguna aman dari formula injection saat export Excel.
10. Semua data contoh adalah dummy; tidak ada vendor, harga, atau kondisi nyata
    yang dikarang.

### 1.2 Kepatuhan terhadap aturan brief

| Aturan brief | Keputusan desain |
|---|---|
| Jangan minta kredensial / koneksi cloud / resize | Tidak ada SDK cloud, kolom kredensial, atau modul jaringan; diverifikasi dengan test impor dan uji manual offline |
| Pisahkan UI, pemrosesan, formula, penyimpanan | Paket `ui`, `services`, `analysis` (pure functions), `db`, `io` dengan aturan dependensi (bagian 2.2) |
| Statistik rata-rata, P95, maksimum | `analysis/stats.py`, P95 interpolasi linear, metode didokumentasikan dan diuji dengan dataset kecil |
| Jangan klaim puncak sesaat untuk data rata-rata per jam | Label otomatis "P95 rata-rata per jam", "maksimum rata-rata per jam" berdasarkan metadata statistik + interval |
| Data tidak cukup ditandai, bukan direkomendasikan | Flag `insufficient_data`, `low_completeness`, `missing_metric`; tidak ada label "recommended" |
| Gabungan antarserver butuh pembobotan jelas | Agregat opsional berbobot kapasitas (vCPU/RAM), rumus dan cakupan ditampilkan; tidak disebut total kapasitas |
| Exemption sebagai konfigurasi | Tabel `scope_rule` + exclusion manual per server, wajib alasan |
| Baseline snapshot | Tabel `baseline*` bersifat immutable, menyimpan scope, metadata batch, statistik, dan versi formula |
| Tandai perubahan scope/kualitas saat perbandingan | Perbandingan menampilkan selisih scope, metadata sumber, jumlah sampel, kelengkapan; delta disupresi bila metadata tidak sebanding |
| Formula resize sederhana, estimasi, >100% warning | `analysis/resize.py`; nilai >100% tidak dipotong; ambang peringatan konfigurasi |
| Biaya hanya jika harga sumber & target konsisten | `analysis/cost.py`; hanya selisih harga per satuan bila mata uang & satuan sama; tanpa konversi/asumsi proporsional |
| KPI "Belum Dikonfigurasi" sampai disetujui | `kpi_definition.status` default `unconfigured`; UI/export menampilkan status, bukan skor karangan |
| Bedakan percentage point vs persen relatif | Dua kolom terpisah dengan rumus dan syarat (bagian 5.3) |
| Export aman dari formula injection | Sanitasi semua sel teks berawalan `=`, `+`, `-`, `@`, TAB, CR |
| Proyek & DB terpisah | Proyek ini berdiri sendiri; DB `data/app.db`; tidak ada kode/DB bersama dengan Cybersecurity Evidence Tracker |

### 1.3 Keputusan yang berubah saat implementasi

| Topik | Keputusan final |
|---|---|
| Metode P95 | Interpolasi linear, posisi `(n-1) x 0,95`, sama dengan pandas/Excel `PERCENTILE.INC`. Nearest-rank tidak dipakai. |
| KPI | Definisi menyimpan kolom `metric` (CPU/memory) selain `measure`, agregasi, operator, target, scope, dan threshold. Hanya enum whitelisted; tanpa `eval`. |
| Snapshot simulasi | Menyimpan snapshot metadata batch sumber (JSON), tipe statistik gabungan CPU/memory, harga target, dan kelengkapan minimum. Snapshot harga sumber tidak disimpan. |
| Tabel KPI | `kpi_definition` memakai `metric` dan `measure`; status `approved` mensyaratkan keduanya terisi. |
| Pengujian | 84 test otomatis: backend + Streamlit `AppTest`; lihat `docs/hasil_pengujian.md`. |
| Database versi lebih baru | Ditolak tanpa mengubah data, bukan dibuka diam-diam sebagai versi lama. |


---

## 2. Keputusan Teknis & Arsitektur

### 2.1 Stack dan versi

- Python: **3.12** (venv `.venv`). Python 3.11 juga didukung. Default `python3`
  di mesin adalah 3.14 dan tidak direkomendasikan karena ketersediaan wheel
  untuk stack analitik belum tentu stabil.
- Streamlit, pandas, openpyxl, Plotly, pytest sesuai brief. SQLite memakai
  modul `sqlite3` standar (tanpa SQLAlchemy).
- Dependensi runtime ditulis sebagai versi **exact pin** di `requirements.txt`
  (hasil freeze saat Phase 0). Dev dependency (pytest) di `requirements-dev.txt`.
- Tidak ada library cloud/AI/HTTP di requirements; kode aplikasi tidak melakukan
  panggilan jaringan.
- `zoneinfo` (stdlib) untuk timezone. Tidak ada library tambahan di luar brief.
- Streamlit dijalankan hanya di `127.0.0.1`; `.streamlit/config.toml`:
  `server.address = "127.0.0.1"` dan `browser.gatherUsageStats = false`.
- Chart memakai `st.plotly_chart` (aset JS disajikan lokal oleh Streamlit),
  tanpa CDN eksternal.
- Repo di-`git init` lokal (tanpa remote) pada Phase 0.

### 2.2 Aturan dependensi lapisan

```
ui/ ──────────► services/ ──────────► db/        (repository SQL, migrasi)
 │                 │
 │                 ├───────────────► analysis/  (pure functions, tanpa IO/DB/UI)
 │                 ├───────────────► io/        (baca/tulis CSV/XLSX, template, sanitasi)
 │                 └───────────────► config     (enum, konstanta, versi formula)
 └──► hanya akses data via services; tidak ada SQL / pandas transformasi bisnis di UI
```

Aturan yang ditegakkan di review dan test statis:
- Hanya modul di `ui/` yang boleh mengimpor `streamlit`.
- `analysis/` tidak mengimpor `sqlite3`, `streamlit`, `pandas` untuk IO, atau modul jaringan.
- Semua query SQL memakai parameter binding; tidak ada string SQL dari input pengguna.
- Tidak ada `eval`, `exec`, `pickle.loads`, atau formula berupa kode bebas.
- Tidak ada modul jaringan/SDK cloud yang diimpor oleh kode aplikasi.

### 2.3 Struktur folder

```
cloud-utilization-simulator/
├── app.py                          # entrypoint Streamlit (navigasi)
├── requirements.txt                # versi exact (runtime)
├── requirements-dev.txt            # pytest (+ pin exact)
├── pyproject.toml                  # konfigurasi pytest
├── .streamlit/config.toml          # localhost, telemetry off
├── .gitignore                      # data/app.db, .venv, __pycache__, dll.
├── README.md
├── PROJECT_BRIEF.md
├── IMPLEMENTATION_PLAN.md
├── data/
│   ├── app.db                      # dibuat saat runtime (tidak di-commit)
│   ├── templates/
│   │   ├── inventaris_v1.xlsx
│   │   └── time_series_v1.csv
│   └── dummy/
│       ├── inventaris_dummy_v1.xlsx
│       ├── cpu_hourly_2026-10.csv
│       ├── memory_hourly_2026-10.csv
│       └── contoh_invalid.csv      # demonstrasi validasi
├── scripts/
│   ├── init_db.py                  # buat/migrasi DB
│   ├── seed_dummy.py               # isi dataset dummy (flag --reset eksplisit)
│   └── make_templates.py           # hasilkan template
├── cloudsim/
│   ├── __init__.py
│   ├── config.py                   # path, default setting, versi formula
│   ├── enums.py                    # kode status + label Indonesia
│   ├── errors.py                   # exception domain
│   ├── clock.py                    # waktu UTC terpusat (mudah diuji)
│   ├── db/
│   │   ├── connection.py           # koneksi per operasi, FK ON, busy_timeout
│   │   ├── schema_v1.sql
│   │   ├── migrate.py              # schema_version
│   │   └── repositories/
│   │       ├── servers.py
│   │       ├── scope_rules.py
│   │       ├── batches.py
│   │       ├── samples.py
│   │       ├── baselines.py
│   │       ├── simulations.py
│   │       ├── kpi.py
│   │       └── settings.py
│   ├── analysis/                   # pure functions + dataclass, tanpa IO
│   │   ├── stats.py                # avg, P95 interpolasi linear, max, label metode
│   │   ├── completeness.py         # sampel diharapkan, gap, kelengkapan
│   │   ├── comparison.py           # delta pp, persen relatif, flag perbandingan
│   │   ├── scope.py                # evaluasi exclusion manual + rules
│   │   ├── resize.py               # formula estimasi + flag ambang
│   │   ├── cost.py                 # syarat perbandingan harga
│   │   ├── kpi.py                  # validasi config + whitelisted aggregation
│   │   └── models.py               # dataclass input/output analisis
│   ├── io/
│   │   ├── csv_reader.py
│   │   ├── excel_reader.py
│   │   ├── column_mapping.py       # target field, mapping, validasi mapping
│   │   ├── parsers.py              # tanggal, angka, timezone, enum
│   │   ├── sanitize.py             # formula injection
│   │   ├── excel_writer.py
│   │   └── template_builder.py
│   ├── services/
│   │   ├── inventory_service.py
│   │   ├── scope_service.py
│   │   ├── inventory_import_service.py
│   │   ├── timeseries_import_service.py
│   │   ├── analysis_service.py     # pilih data, validasi metadata, statistik
│   │   ├── baseline_service.py
│   │   ├── simulation_service.py
│   │   ├── kpi_service.py
│   │   └── export_service.py
│   └── ui/
│       ├── navigation.py
│       ├── context.py              # konteks analisis global (session state)
│       ├── components/
│       │   ├── filters.py
│       │   ├── cards.py            # angka + pembilang/penyebut/pengecualian
│       │   ├── charts.py
│       │   ├── import_wizard.py
│       │   ├── forms_server.py
│       │   ├── forms_scope_rule.py
│       │   └── disclaimers.py
│       └── views/
│           ├── import_view.py
│           ├── inventory_view.py
│           ├── dashboard_view.py
│           ├── comparison_view.py
│           ├── simulator_view.py
│           ├── kpi_view.py
│           └── export_view.py
├── tests/
│   ├── conftest.py                 # tmp DB, fixture dataset kecil
│   ├── unit/
│   │   ├── test_stats.py
│   │   ├── test_completeness.py
│   │   ├── test_comparison.py
│   │   ├── test_scope.py
│   │   ├── test_resize.py
│   │   ├── test_cost.py
│   │   ├── test_parsers.py
│   │   ├── test_sanitize.py
│   │   └── test_kpi_config.py
│   └── integration/
│       ├── test_inventory_import.py
│       ├── test_timeseries_import.py
│       ├── test_analysis_service.py
│       ├── test_baseline.py
│       ├── test_simulation.py
│       ├── test_export.py
│       └── test_no_network_imports.py
└── docs/
    ├── formula_dan_metode.md
    ├── asumsi_dan_batasan.md
    └── hasil_pengujian.md
```

Catatan: Streamlit multipage memakai `st.navigation`/`st.Page` dari `app.py`
(kebutuhan Streamlit >= 1.40), sehingga folder view tidak harus bernama `pages/`.

---

## 3. Skema Database (SQLite)

### 3.1 ERD ringkas

```
server 1 ────< utilization_sample >──── 1 import_batch
   │                                          │
   │ (snapshot teks)                          └──< import_issue
   │
scope_rule (independen, dievaluasi saat analisis)

baseline 1 ──< baseline_server_stat
         1 ──< baseline_exclusion
         1 ──< baseline_source (metadata batch)

simulation 1 ──< simulation_result

kpi_definition 1 ──< kpi_threshold
              └── baseline_id (opsional)
```

Keputusan penting:
- Timestamp sampel disimpan sebagai epoch UTC (`ts_utc INTEGER`), bukan teks,
  agar unik, mudah difilter, dan bebas ambiguitas zona waktu.
- Kunci unik sampel: `(metric, server_id, ts_utc)` lintas batch. Overlap antar
  batch tidak bisa tersimpan diam-diam.
- Baseline, simulasi, dan exclusion menyimpan snapshot nilai teks/numerik
  sehingga tetap terbaca walau batch/server berubah atau dihapus.
- Riwayat versi formula disimpan pada baseline, simulasi, dan export.

### 3.2 DDL v1

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE schema_version (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE app_setting (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE server (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    server_code        TEXT NOT NULL COLLATE NOCASE,
    name               TEXT,
    environment        TEXT NOT NULL,
    region             TEXT,
    workload           TEXT,
    vcpu               INTEGER NOT NULL CHECK (vcpu > 0),
    ram_gib            REAL NOT NULL CHECK (ram_gib > 0),
    instance_type      TEXT,
    scope_status       TEXT NOT NULL DEFAULT 'in_scope'
                       CHECK (scope_status IN ('in_scope','excluded')),
    exclusion_reason   TEXT,
    price_amount       REAL CHECK (price_amount IS NULL OR price_amount >= 0),
    price_currency     TEXT,
    price_unit         TEXT CHECK (price_unit IS NULL OR price_unit IN
                       ('per_hour','per_month','per_vcpu_hour','per_gib_month','other')),
    price_unit_label   TEXT,
    price_source_date  TEXT,
    notes              TEXT,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL,
    CHECK (scope_status <> 'excluded'
           OR (exclusion_reason IS NOT NULL AND length(trim(exclusion_reason)) > 0)),
    CHECK (price_amount IS NULL OR (price_currency IS NOT NULL
           AND price_unit IS NOT NULL AND price_source_date IS NOT NULL)),
    CHECK (price_amount IS NOT NULL OR (price_currency IS NULL
           AND price_unit IS NULL AND price_unit_label IS NULL
           AND price_source_date IS NULL)),
    CHECK (price_currency IS NULL OR (length(price_currency) = 3
           AND price_currency = upper(price_currency))),
    CHECK (price_unit <> 'other' OR price_unit_label IS NOT NULL)
);

CREATE UNIQUE INDEX ux_server_code ON server(server_code COLLATE NOCASE);
CREATE INDEX ix_server_env ON server(environment);

CREATE TABLE scope_rule (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    dimension    TEXT NOT NULL
                 CHECK (dimension IN ('environment','workload','region','server')),
    match_value  TEXT NOT NULL,
    reason       TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    active       INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE import_batch (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    data_type        TEXT NOT NULL
                     CHECK (data_type IN ('inventory','cpu','memory')),
    file_name        TEXT NOT NULL,
    file_sha256      TEXT NOT NULL,
    timezone         TEXT,          -- IANA, wajib untuk timeseries
    interval_seconds INTEGER CHECK (interval_seconds IS NULL OR interval_seconds > 0),
    statistic_type   TEXT CHECK (statistic_type IN ('average','maximum','other')),
    statistic_label  TEXT,
    period_start_utc INTEGER,
    period_end_utc   INTEGER,
    total_rows       INTEGER NOT NULL DEFAULT 0,
    accepted_rows    INTEGER NOT NULL DEFAULT 0,
    rejected_rows    INTEGER NOT NULL DEFAULT 0,
    imported_at      TEXT NOT NULL,
    notes            TEXT,
    CHECK (data_type = 'inventory' OR timezone IS NOT NULL),
    CHECK (data_type = 'inventory' OR statistic_type IS NOT NULL),
    CHECK (statistic_type <> 'other' OR statistic_label IS NOT NULL)
);

CREATE TABLE utilization_sample (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id  INTEGER NOT NULL REFERENCES import_batch(id) ON DELETE CASCADE,
    server_id INTEGER NOT NULL REFERENCES server(id) ON DELETE RESTRICT,
    metric    TEXT NOT NULL CHECK (metric IN ('cpu','memory')),
    ts_utc    INTEGER NOT NULL,
    value     REAL NOT NULL CHECK (value >= 0 AND value <= 100)
);

CREATE UNIQUE INDEX ux_sample_key ON utilization_sample(metric, server_id, ts_utc);
CREATE INDEX ix_sample_server_time ON utilization_sample(server_id, metric, ts_utc);

CREATE TABLE import_issue (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES import_batch(id) ON DELETE CASCADE,
    severity TEXT NOT NULL CHECK (severity IN ('error','warning')),
    code     TEXT NOT NULL,
    row_ref  TEXT,
    detail   TEXT NOT NULL
);

CREATE TABLE baseline (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    window_start_utc  INTEGER NOT NULL,
    window_end_utc    INTEGER NOT NULL CHECK (window_end_utc > window_start_utc),
    display_timezone  TEXT NOT NULL,
    formula_version   TEXT NOT NULL,
    notes             TEXT
);

CREATE TABLE baseline_source (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    baseline_id      INTEGER NOT NULL REFERENCES baseline(id) ON DELETE CASCADE,
    metric           TEXT NOT NULL CHECK (metric IN ('cpu','memory')),
    batch_id         INTEGER,       -- boleh NULL jika batch kemudian dihapus
    file_name        TEXT NOT NULL,
    file_sha256      TEXT NOT NULL,
    timezone         TEXT NOT NULL,
    interval_seconds INTEGER,
    statistic_type   TEXT NOT NULL,
    statistic_label  TEXT,
    data_start_utc   INTEGER,
    data_end_utc     INTEGER,
    sample_count     INTEGER NOT NULL
);

CREATE TABLE baseline_exclusion (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    baseline_id INTEGER NOT NULL REFERENCES baseline(id) ON DELETE CASCADE,
    server_code TEXT NOT NULL,
    server_name TEXT,
    source      TEXT NOT NULL CHECK (source IN ('manual','rule')),
    rule_name   TEXT,
    reason      TEXT NOT NULL
);

CREATE TABLE baseline_server_stat (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    baseline_id      INTEGER NOT NULL REFERENCES baseline(id) ON DELETE CASCADE,
    server_code      TEXT NOT NULL,
    environment      TEXT,
    workload         TEXT,
    vcpu             INTEGER NOT NULL,
    ram_gib          REAL NOT NULL,
    metric           TEXT NOT NULL CHECK (metric IN ('cpu','memory')),
    sample_count     INTEGER NOT NULL CHECK (sample_count >= 0),
    completeness_pct REAL,          -- NULL bila interval tidak diketahui
    avg_value        REAL,
    p95_value        REAL,
    max_value        REAL,
    quality_flags    TEXT,          -- kode dipisah koma, mis. low_completeness
    UNIQUE (baseline_id, server_code, metric)
);

CREATE TABLE simulation (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    name                  TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    server_code           TEXT NOT NULL,
    server_name           TEXT,
    environment           TEXT,
    region                TEXT,
    workload              TEXT,
    window_start_utc      INTEGER NOT NULL,
    window_end_utc        INTEGER NOT NULL CHECK (window_end_utc > window_start_utc),
    display_timezone      TEXT NOT NULL,
    statistic_type        TEXT NOT NULL,
    statistic_label       TEXT,
    interval_seconds      INTEGER,
    source_batch_snapshot TEXT,     -- JSON: metadata batch (id, file, hash, tz, interval, stat type)
    source_vcpu           INTEGER NOT NULL CHECK (source_vcpu > 0),
    source_ram_gib        REAL NOT NULL CHECK (source_ram_gib > 0),
    target_vcpu           INTEGER NOT NULL CHECK (target_vcpu > 0),
    target_ram_gib        REAL NOT NULL CHECK (target_ram_gib > 0),
    target_instance_type  TEXT,
    warning_threshold_pct REAL NOT NULL CHECK (warning_threshold_pct > 0
                            AND warning_threshold_pct <= 100),
    completeness_pct      REAL,
    data_sufficient       INTEGER NOT NULL CHECK (data_sufficient IN (0,1)),
    formula_version       TEXT NOT NULL,
    target_price_amount   REAL CHECK (target_price_amount IS NULL
                            OR target_price_amount >= 0),
    target_price_currency TEXT,
    target_price_unit     TEXT CHECK (target_price_unit IS NULL
                            OR target_price_unit IN
                            ('per_hour','per_month','per_vcpu_hour','per_gib_month','other')),
    target_price_unit_label TEXT,
    target_price_source_date TEXT,
    notes                 TEXT,
    CHECK (target_price_amount IS NULL OR (target_price_currency IS NOT NULL
           AND target_price_unit IS NOT NULL AND target_price_source_date IS NOT NULL)),
    CHECK (target_price_currency IS NULL OR (length(target_price_currency) = 3
           AND target_price_currency = upper(target_price_currency))),
    CHECK (target_price_unit <> 'other' OR target_price_unit_label IS NOT NULL)
);

CREATE TABLE simulation_result (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    simulation_id INTEGER NOT NULL REFERENCES simulation(id) ON DELETE CASCADE,
    metric        TEXT NOT NULL CHECK (metric IN ('cpu','memory')),
    stat_name     TEXT NOT NULL CHECK (stat_name IN ('avg','p95','max')),
    before_value  REAL,
    after_value   REAL,
    flag          TEXT NOT NULL CHECK (flag IN
                  ('normal','near_threshold','over_100','insufficient_data','not_available')),
    UNIQUE (simulation_id, metric, stat_name)
);

CREATE TABLE kpi_definition (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    description         TEXT,
    status              TEXT NOT NULL DEFAULT 'unconfigured'
                        CHECK (status IN ('unconfigured','draft','approved')),
    metric              TEXT CHECK (metric IN ('cpu','memory')),
    measure             TEXT CHECK (measure IN ('avg','p95','max')),
    aggregate_method    TEXT CHECK (aggregate_method IN
                        ('none','simple_mean','capacity_weighted_vcpu','capacity_weighted_ram')),
    operator            TEXT CHECK (operator IN ('lte','gte','between')),
    target_value        REAL,
    target_value_upper  REAL,
    unit                TEXT NOT NULL DEFAULT 'percent' CHECK (unit = 'percent'),
    scope_mode          TEXT NOT NULL DEFAULT 'current_scope'
                        CHECK (scope_mode IN ('current_scope','baseline_scope')),
    baseline_id         INTEGER REFERENCES baseline(id) ON DELETE SET NULL,
    approved_at         TEXT,
    formula_version     TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    CHECK (status <> 'approved' OR (metric IS NOT NULL AND measure IS NOT NULL
           AND aggregate_method IS NOT NULL AND operator IS NOT NULL
           AND target_value IS NOT NULL AND approved_at IS NOT NULL)),
    CHECK (operator <> 'between' OR target_value_upper IS NOT NULL),
    CHECK (scope_mode <> 'baseline_scope' OR baseline_id IS NOT NULL),
    CHECK (target_value_upper IS NULL OR target_value_upper >= target_value)
);

CREATE TABLE kpi_threshold (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    kpi_id    INTEGER NOT NULL REFERENCES kpi_definition(id) ON DELETE CASCADE,
    label     TEXT NOT NULL,
    min_value REAL,
    max_value REAL,
    meaning   TEXT,
    CHECK (min_value IS NULL OR max_value IS NULL OR min_value <= max_value)
);

CREATE INDEX ix_baseline_source ON baseline_source(baseline_id);
CREATE INDEX ix_baseline_stat ON baseline_server_stat(baseline_id, server_code);
CREATE INDEX ix_simulation_server ON simulation(server_code);
CREATE INDEX ix_issue_batch ON import_issue(batch_id, severity);
```

Seed `app_setting` saat migrasi (nilai awal, dapat diubah pengguna):
`display_timezone=Asia/Jakarta`, `warning_threshold_pct=80`,
`min_completeness_pct=80`, `min_samples=24`.

### 3.3 Aturan integritas & konvensi

- `server_code` unik tanpa membedakan huruf besar/kecil; input time series
  dicocokkan case-insensitive setelah trim.
- Semua timestamp internal UTC epoch detik. Sub-detik ditolak dengan pesan
  jelas (tidak dipotong diam-diam).
- Tanggal kalender (mis. tanggal sumber harga) disimpan `YYYY-MM-DD`.
- Angka utilization disimpan sebagai persen 0–100 (bukan fraksi).
- `data_type` batch timeseries hanya `cpu` atau `memory` (satu metrik per file).
- Hapus server diblokir jika sudah memiliki sampel (FK `RESTRICT`); gunakan
  status excluded agar tetap tercatat.
- Hapus batch menghapus sampel & issue-nya; baseline/simulasi tidak terpengaruh
  karena menyimpan snapshot.
- Migrasi bernomor (`schema_v1.sql`, dst.) dan dicatat di `schema_version`.
- Koneksi dibuka per operasi, `PRAGMA foreign_keys=ON`, `busy_timeout=5000`,
  transaksi eksplisit untuk import/simpan.

---

## 4. Rancangan Halaman

### 4.1 Navigasi dan konteks global

Sidebar:
- Judul aplikasi + penanda "DATA DUMMY".
- Menu: Import & Validasi, Inventaris & Scope, Dashboard Utilization,
  Perbandingan & Baseline, Simulator Resize, Konfigurasi KPI, Export Excel.
- Expander "Konteks Analisis": rentang periode (tanggal inklusif di UI,
  half-open di perhitungan), pilihan batch CPU, pilihan batch memory,
  zona waktu tampilan, cakupan (in-scope saja / termasuk excluded).
  Konteks disimpan di `session_state`; tidak disimpan ke DB.
- Info status: batch terpilih, statistik sumber, interval, peringatan
  kompatibilitas, versi formula, status KPI.

Konteks divalidasi sebelum semua halaman analisis:
- Batch CPU harus bertipe `cpu`, batch memory bertipe `memory`.
- Dalam satu metrik, semua batch harus memiliki `statistic_type` dan interval
  yang sama. Jika berbeda: blokir analisis dengan pesan yang menjelaskan
  batch mana yang berbeda (MVP tidak melakukan normalisasi).
- Interval berbeda antar metrik diperbolehkan, tetapi label & kualitas data
  ditampilkan per metrik.

### 4.2 Detail halaman

**1. Import & Validasi**
- Tab "Inventaris": unggah XLSX/CSV → pilih sheet/delimiter → pemetaan kolom →
  validasi → preview (baris diterima, baris bermasalah, ringkasan) → konfirmasi.
- Tab "Time Series": unggah file CPU atau memory → pilih sheet/delimiter →
  pilih metrik → pemetaan kolom (server, timestamp, nilai) → isi metadata
  (timezone IANA, interval, statistic type/label) → validasi → preview →
  konfirmasi.
- Preview menampilkan: jumlah baris, rentang data, jumlah sampel, kelengkapan
  (hanya jika interval diketahui), nilai di luar 0–100, ID server tidak dikenal,
  duplikat identik, konflik duplikat, timestamp tidak selaras interval.
- Laporan validasi dapat diunduh (CSV) sebelum penyimpanan.
- Tombol simpan baru aktif setelah pengguna memeriksa ringkasan dan
  mencentang persetujuan (untuk import parsial, lihat bagian 6).
- Daftar batch tersimpan: tipe, file, hash, metadata, periode, jumlah
  diterima/ditolak, issue; aksi hapus batch dengan konfirmasi.
- Semua proses preview di memori; tidak ada penulisan DB sebelum konfirmasi.

**2. Inventaris & Scope**
- Tabel server dengan filter environment, region, workload, status scope, kata kunci.
- Form tambah/ubah server: field sesuai brief, vCPU/RAM wajib > 0,
  harga opsional (amount, currency, unit, tanggal sumber), scope + alasan.
- Tab "Aturan Pengecualian": CRUD `scope_rule` (dimensi, nilai, alasan, aktif);
  pratinjau jumlah/daftar server terdampak sebelum menyimpan.
- Tab "Pengecualian Manual": server excluded + alasan; sumber alasan ditampilkan
  (manual/rule).
- Tidak ada penghapusan server yang memiliki sampel; sarannya ubah ke excluded.

**3. Dashboard Utilization & Kualitas Data**
- Kartu ringkasan (setiap angka menampilkan pembilang/penyebut/pengecualian):
  jumlah server in-scope/excluded; server dengan kelengkapan terhitung; server
  di bawah ambang kelengkapan; server tanpa salah satu metrik.
- Tabel statistik per server per metrik: jumlah sampel, kelengkapan, rata-rata,
  P95, maksimum, label sumber statistik, flag kualitas.
- Grafik time series per server (pilih server & metrik): garis dengan gap
  terlihat (tanpa interpolasi), sumbu waktu di zona tampilan. Jika deret sangat
  panjang, ringkas tampilan dan beri catatan bahwa statistik memakai seluruh
  sampel.
- Panel kualitas data: metadata batch, rentang data, gap/duplikat/nilai invalid
  dari riwayat import, peringatan metadata.
- Agregat antarserver (opsional, lihat pertanyaan Q5): hanya dengan metode
  eksplisit; tampilkan rumus, bobot, dan `n/N` server yang dihitung.
- Tidak ada label "rekomendasi", "maturity", atau skor gabungan.

**4. Perbandingan & Baseline**
- Tab "Dua Periode": pilih periode A dan B (batch + rentang), satu zona tampilan.
- Tab "Baseline": buat baseline dari konteks analisis aktif; daftar baseline;
  lihat snapshot; bandingkan konteks aktif dengan baseline.
- Hasil: tabel per server per metrik berisi A, B, delta percentage point,
  perubahan relatif (dengan syarat), jumlah sampel & kelengkapan A/B, label
  sumber statistik, dan flag.
- Sertakan grafik dua panel (periode A dan B) per server/metrik dengan sumbu
  waktu dan label periode yang jelas; deret tidak digabung menjadi satu garis
  tanpa penjelasan.
- Flag perubahan scope: server ditambah/dihapus/berubah status exclusion beserta
  alasan. Flag perubahan kualitas: jumlah sampel, kelengkapan, metadata batch,
  versi formula. Jika statistik sumber/interval berbeda, nilai delta ditandai
  "tidak sebanding" dan tidak diagregasi.
- Ringkasan naratif menyebut pembilang/penyebut/pengecualian secara eksplisit.
- Baseline immutable; penghapusan baseline memerlukan konfirmasi.

**5. Simulator Resize**
- Pilih server + konteks periode/metrik; tampilkan statistik sumber dan status
  kecukupan data.
- Input: target vCPU, target RAM GiB, kandidat tipe instance (teks bebas,
  berlabel "belum tervalidasi"), ambang peringatan (default dari setting),
  harga target opsional (amount, currency, unit, tanggal sumber), catatan.
- Hasil per metrik/statistik: nilai sebelum, estimasi sesudah, selisih, flag
  normal / mendekati ambang / melebihi 100% (tidak dipotong), atau tidak
  tersedia.
- Tabel sebelum–sesudah + catatan risiko kapasitas; peringatan eksplisit
  "asumsi beban tetap" dan "kemampuan per-vCPU sebanding".
- Bagian biaya hanya muncul bila syarat harga terpenuhi; jelaskan alasan jika
  tidak muncul.
- Daftar skenario tersimpan; simpan/hapus dengan konfirmasi.
- Tidak ada tombol/klaim "rekomendasi ukuran".

**6. Konfigurasi KPI**
- Banner status: "Belum Dikonfigurasi" selama belum ada definisi disetujui.
- Form konfigurasi terstruktur: nama, deskripsi, measure (avg/p95/max),
  metode agregasi (none/simple mean/berbobot vCPU/berbobot RAM), operator,
  target, batas capaian, mode scope, baseline opsional.
- Simpan sebagai draf atau setujui secara eksplisit (aksi terpisah dengan
  konfirmasi). Tidak ada ekspresi bebas.
- Setelah disetujui: tampilkan nilai KPI untuk konteks aktif dengan penjelasan
  metode, cakupan `n/N`, pengecualian, dan peringatan kualitas data.
- Status KPI (belum dikonfigurasi/draf/disetujui) ikut tercetak di export.

**7. Export Excel**
- Pilih cakupan export: konteks analisis aktif, perbandingan (jika ada),
  skenario simulasi (pilih), konfigurasi KPI (status).
- Tampilkan daftar sheet sebelum mengunduh.
- Tidak menyertakan raw time series; hanya ringkasan, metadata, statistik,
  kualitas data, perbandingan, simulasi, exclusion, asumsi, peringatan.
- Semua sel teks disanitasi terhadap formula injection.
- Nama file: `utilization_export_YYYYMMDD_HHMM.xlsx`.

Konten setiap halaman menyertakan footer disklaimer:
"Aplikasi lokal; data berasal dari file yang diimpor. Tidak ada koneksi ke
cloud/produksi dan tidak ada perubahan infrastruktur. Hasil simulasi adalah
estimasi, bukan jaminan performa."

---

## 5. Metode & Formula

Semua formula dipusatkan di `cloudsim/analysis/` dan didokumentasikan di
`docs/formula_dan_metode.md`, termasuk contoh perhitungan manual.

### 5.1 Statistik per server

Untuk sampel CPU/memory yang **tersedia** dalam jendela analisis `[start, end)`:

- `avg` = rata-rata aritmetika nilai sampel. Tidak ada pembobotan per server
  di dalam statistik ini; jumlah sampel selalu ditampilkan.
- `P95` = **interpolasi linear**: urutkan nilai menaik, `posisi = (n − 1) × 0,95`,
  lalu interpolasi antara nilai `floor(posisi)` dan `ceil(posisi)`. Ini sama
  dengan pandas `quantile(0.95, interpolation="linear")` dan Excel
  `PERCENTILE.INC`. Contoh `[10, 20, 30, 40]` → posisi 2,85 → `30 + 0,85 × 10 = 38,5`.
- `max` = nilai maksimum sampel yang tersedia.
- Sampel kosong tidak dihitung dan tidak diganti nol. Gap tidak diisi.
- Label otomatis berdasarkan metadata sumber dan interval:
  - sumber Average, interval 1 jam → "rata-rata per jam", "P95 rata-rata per jam",
    "maksimum rata-rata per jam".
  - sumber Maximum → "P95 dari maksimum per interval", "maksimum dari maksimum
    per interval" (tetap bukan klaim puncak sesaat).
  - sumber Other → memakai label yang diisi pengguna, ditambah keterangan
    "dihitung dari sampel yang tersedia".
- Jika `n = 0`: nilai statistik `NULL`, UI menampilkan "tidak tersedia",
  bukan 0.

### 5.2 Kelengkapan data

Hanya dihitung jika interval pengamatan diketahui.

```
durasi        = end_utc - start_utc                  (detik, half-open)
diharapkan    = floor(durasi / interval_seconds)
tersedia      = jumlah sampel valid milik server & metrik di jendela
kelengkapan   = tersedia / diharapkan × 100
```

- Jika `diharapkan = 0` → kelengkapan tidak terdefinisi.
- Jika `tersedia > diharapkan` → tampilkan nilai >100% dan flag
  "interval/metadata tidak konsisten"; nilai tidak dipotong ke 100%.
- Kelengkapan ditampilkan bersama `tersedia`, `diharapkan`, dan jumlah server
  yang dapat dihitung. Server tanpa interval diketahui dikecualikan dan
  dilaporkan sebagai pengecualian.
- Timestamp yang tidak selaras dengan grid interval dianggap peringatan
  kualitas, bukan otomatis diperbaiki.
- Ujung jendela di UI inklusif (mis. 1–31 Okt); konversi ke UTC menghasilkan
  `end` = awal hari setelah tanggal akhir di zona tampilan.

### 5.3 Perbandingan periode/baseline

- `delta_pp = B − A` (percentage point; satuan % utilization).
- `perubahan_relatif = ((B − A) / A) × 100%`, hanya jika `A > 0`; jika `A = 0`
  tampilkan "tidak terdefinisi" dan jangan menghitung/mengganti nilai.
- Kedua angka diberi label berbeda dan tidak pernah disebut sebagai "growth"
  tanpa penjelasan.
- Delta dihitung hanya untuk server yang ada di kedua sisi dan metrik tersedia.
  Server yang hanya ada di satu sisi ditampilkan sebagai perubahan scope.
- Jika statistic type, interval, atau versi formula berbeda: tampilkan nilai
  A/B dengan label, tandai perbandingan "tidak sebanding", tampilkan peringatan
  metadata, dan jangan klaim kedua angka setara. Implementasi tetap menampilkan
  delta sebagai informasi, dengan status `comparable = false`; pengguna harus
  membaca peringatan sebelum memakai delta.
- Perubahan kualitas data (sampel/kelengkapan) selalu ditampilkan per server;
  ringkasan menyebut jumlah server yang kualitasnya berubah.

### 5.4 Simulasi resize

Untuk setiap statistik yang tersedia:

```
estimasi_CPU = nilai_CPU × vCPU_sumber / vCPU_target
estimasi_MEM = nilai_MEM × RAM_sumber  / RAM_target
```

- Nilai >100% ditampilkan apa adanya dengan flag `over_100`.
- `near_threshold` jika nilai estimasi ≥ ambang peringatan dan <100%.
- Nilai = 100% diberi peringatan tepat di batas.
- Estimasi diberi label "estimasi beban tetap" dan tidak menjamin performa,
  latency, throughput, atau penggunaan memory aktual.
- Estimasi CPU hanya ditampilkan dengan catatan relevansi bila kemampuan
  per-vCPU sebanding; aplikasi tidak memvalidasi kesebandingan tersebut.
- I/O, jaringan, lisensi, dan kebutuhan aplikasi dinyatakan "belum dinilai".
- Kandidat tipe instance selalu berlabel "belum tervalidasi".
- Kecukupan data: `min_samples` dan `min_completeness_pct` dari setting.
  Jika tidak terpenuhi, hasil ditandai `insufficient_data`; pengguna harus
  menyetujui peringatan sebelum menyimpan skenario. Tidak ada rekomendasi.
- Harga: hanya jika harga sumber (inventaris) dan target tersedia dengan mata
  uang dan satuan identik (termasuk label untuk `other`). Yang ditampilkan
  adalah selisih harga per satuan yang diisi pengguna; tanpa konversi bulanan,
  tanpa asumsi skala linear, dan bukan klaim penghematan.

### 5.5 Agregat antarserver (opsional)

- Tidak ada angka tunggal "utilization seluruh kapasitas".
- Metode yang diizinkan (dipilih eksplisit):
  - berbobot vCPU untuk CPU: `Σ(nilai_server × vCPU) / Σ(vCPU)`;
  - berbobot RAM untuk memory: `Σ(nilai_server × RAM) / Σ(RAM)`.
- Sertakan server yang dihitung `n/N`, server dikecualikan, dan server tanpa
  metrik.
- Tampilkan rumus di UI dan export.
- Rata-rata sederhana hanya boleh muncul jika diberi label "rata-rata sederhana
  antarserver (tanpa pembobotan), bukan utilization total kapasitas" (pending Q5).

### 5.6 KPI

- Modul default "Belum Dikonfigurasi"; tidak ada nilai ditampilkan sebelum
  definisi disetujui.
- Konfigurasi terstruktur memakai enum (bagian 3.2); tidak ada formula kode.
- Perhitungan (setelah persetujuan) hanya memakai measure × aggregate method
  yang dipilih, dengan cakupan & pengecualian ditampilkan.
- Persetujuan dan pembatalan persetujuan dicatat dengan timestamp.
- Batas capaian (threshold) disimpan terstruktur dan harus tidak tumpang tindih
  saat disetujui.

---

## 6. Import & Validasi

### 6.1 Wizard pemetaan kolom

- Sumber: CSV (UTF-8/BOM; delimiter dipilih eksplisit: koma/titik koma/tab)
  atau XLSX (pilih sheet, nomor baris header).
- Pemetaan target field eksplisit; kolom wajib ditandai. Kolom tak dikenal
  diabaikan dengan peringatan, tidak dipakai diam-diam.
- Format angka dipilih eksplisit (desimal titik vs koma); tidak menebak dari isi.
- Format tanggal dipilih eksplisit (ISO `YYYY-MM-DD`, `dd/mm/yyyy`,
  `mm/dd/yyyy`, `dd-mm-yyyy`, atau tanggal Excel native). Tidak ada auto-guess
  untuk format ambigu.
- Zona waktu IANA wajib untuk time series; divalidasi dengan `zoneinfo`.
  Jika timestamp membawa offset, offset dipakai dan metadata zona waktu
  dicatat; jika offset bertentangan dengan pilihan pengguna, tampilkan
  peringatan.
- Tidak ada "normalisasi otomatis" yang tidak terlihat.

### 6.2 Inventaris

Wajib: `server_code`, `environment`, `vcpu`, `ram_gib`.
Opsional: nama, region, workload, instance type, harga (semua-atau-tidak-sama-sekali),
scope + alasan, catatan.

Validasi:
- kode kosong/duplikat dalam file → error;
- kode sudah ada di DB → error (MVP tidak menimpa; lihat Q7);
- vCPU/RAM harus angka > 0;
- excluded tanpa alasan → error;
- harga tidak lengkap / mata uang bukan 3 huruf kapital / unit `other` tanpa
  label / tanggal tidak valid → error;
- baris dengan error tidak disimpan kecuali pengguna memilih import parsial
  secara eksplisit (lihat 6.5).

### 6.3 Time series

Wajib: `server_code`, `timestamp`, `value`. Satu file = satu metrik (CPU atau
memory); file gabungan diimpor dua kali (lihat Q10).

Validasi:
- ID server harus sudah ada di inventaris; ID tidak dikenal → error.
- Timestamp harus parseable dengan format yang dipilih; waktu lokal ambigu
  (DST) atau tidak ada → error, tidak dipilih diam-diam.
- Nilai harus numerik 0–100; kosong/teks/di luar rentang → error (bukan nol).
- Duplikat dalam file dan duplikat terhadap DB dicek sebelum penyimpanan:
  - identik (nilai sama) → warning, baris dilewati dan dilaporkan;
  - konflik (nilai berbeda) → error, tidak ada pemilihan otomatis.
- Interval opsional; jika kosong, kelengkapan tidak dihitung.
- Peringatan jika timestamp tidak selaras dengan grid interval.
- Peringatan jika hash file sudah pernah diimpor (menampilkan batch lama).

### 6.4 Duplikat & konflik

- Kunci duplikat: `(metric, server_code, ts_utc)`.
- Kebijakan MVP: **tidak pernah menimpa** data lama. Konflik selalu error.
  Untuk mengganti data, pengguna menghapus batch lama lalu mengimpor ulang.
- Tidak ada "pilih nilai A atau B" otomatis; jika ingin resolusi per baris,
  itu di luar MVP.

### 6.5 Penyimpanan hasil import

- Preview selalu sebelum simpan; tidak ada penulisan DB sebelumnya.
- Default: blokir simpan jika ada error.
- Opsi eksplisit "simpan hanya baris valid" dengan centang persetujuan;
  baris error tetap ditampilkan lengkap dan dicatat sebagai `import_issue`.
- Penyimpanan satu transaksi: batch + sampel + issue + update ringkasan batch.
  Gagal di tengah → rollback.
- `import_batch` mencatat file, hash, metadata, jumlah diterima/ditolak,
  periode data yang diterima.
- Daftar issue menyimpan kode dan referensi baris (bukan salinan data sensitif).

---

## 7. Scope, Baseline, dan Perbandingan

- Scope efektif = exclusion manual per server **atau** cocok dengan minimal
  satu `scope_rule` aktif. Alasan yang berlaku (manual dan/atau nama rule)
  ditampilkan. MVP tidak menyediakan override "include" terhadap rule;
  untuk memasukkan server, nonaktifkan rule atau ubah scope-nya (pending Q6).
- Rule adalah konfigurasi di database, bukan hardcode; matching exact
  case-insensitive setelah trim.
- Baseline menyimpan:
  - jendela analisis UTC + zona tampilan;
  - metadata semua batch sumber (file, hash, timezone, interval, tipe
    statistik, periode, jumlah sampel);
  - statistik per server & metrik + jumlah sampel + kelengkapan + flag;
  - daftar exclusion beserta sumber dan alasan;
  - versi formula.
- Baseline tidak berubah ketika data sumber berubah/dihapus.
- Perbandingan dengan baseline selalu menampilkan perubahan scope dan kualitas
  data; versi formula berbeda diberi peringatan eksplisit.
- Tidak ada perbandingan agregat bila scope atau metadata sumber berbeda;
  perbandingan per server tetap ditampilkan dengan flag.

---

## 8. Export Excel (rincian deliverable)

Workbook export minimal berisi sheet:

1. `Ringkasan` — waktu export, parameter analisis, batch & metadata sumber,
   jumlah server included/excluded, status KPI, peringatan utama, versi formula.
2. `Inventaris` — server, environment, region, workload, vCPU, RAM, instance
   type, scope, alasan exclusion, harga + mata uang/satuan/tanggal.
3. `Kualitas_Data` — metadata batch, rentang, jumlah sampel, kelengkapan,
   ringkasan issue (duplikat, konflik, invalid, gap).
4. `Statistik` — per server/metrik: avg, P95, max, jumlah sampel, kelengkapan,
   label metode.
5. `Perbandingan` — opsional, A/B atau baseline vs aktif, delta pp, perubahan
   relatif (dengan syarat), flag scope/kualitas/metadata.
6. `Simulasi` — input, hasil per metrik/statistik, flag >100%, asumsi,
   kecukupan data, catatan harga.
7. `Pengecualian` — server & rule dengan alasan.
8. `KPI` — status; konfigurasi bila ada; tidak ada skor karangan.
9. `Asumsi_Batasan` — teks asumsi dan batasan analisis.

Aturan export:
- Semua sel teks dari input/DB disanitasi: awalan `=`, `+`, `-`, `@`, TAB,
  CR diberi prefix `'` agar tidak dieksekusi sebagai formula.
- Angka statistik tetap numerik; tanggal ditulis ISO dengan label zona waktu.
- Tidak ada makro, tautan eksternal, atau query data saat file dibuka.
- Formula/versi metode dan disclaimer disertakan dalam file.
- Raw time series tidak diekspor (pending Q11).

---

## 9. Tahapan Implementasi

**Status 2026-11-21:** Phase 0–6 selesai untuk MVP lokal. Test otomatis dan
smoke test UI lulus; review pengguna masih diperlukan.

Perkiraan kasar, bukan komitmen tanggal. Setiap tahap diakhiri dengan test lulus
dan demo manual singkat.

### Phase 0 — Fondasi (0,5–1 hari)
- Inisialisasi repo, venv Python 3.12, pin dependency.
- `app.py`, navigasi kosong, config localhost/telemetry off.
- Skema v1 + migrasi + `app_setting` default.
- Readme awal, script init DB, generator template & dummy (kerangka).
- Test harness (`conftest`, tmp DB).
- Halaman KPI placeholder "Belum Dikonfigurasi".

**Kriteria selesai:** aplikasi terbuka di localhost, DB kosong dapat dibuat,
`pytest` hijau, template dapat digenerate.

### Phase 1 — Import & Validasi (2–3 hari)
- Inventaris: import + pemetaan kolom + validasi + preview + simpan transaksional.
- Time series: wizard CPU/memory terpisah, pemetaan, metadata, timezone,
  interval, stat type, parsing angka/tanggal.
- Deteksi duplikat/konflik, out-of-range, unknown ID, gap, kelengkapan.
- Preview + laporan validasi + opsi import parsial eksplisit.
- CRUD inventaris & scope dasar + halaman daftar batch.

**Kriteria selesai:** semua test import lulus; tidak ada data tersimpan sebelum
konfirmasi; konflik/duplikat selalu dilaporkan; rollback bekerja.

### Phase 2 — Statistik & Dashboard (1,5–2 hari)
- `analysis/stats.py`, `completeness.py`, label metode.
- `analysis_service` memvalidasi kompatibilitas batch.
- Dashboard: kartu ringkasan, tabel statistik, grafik per server, panel kualitas.
- Agregat opsional sesuai keputusan Q5.
- Test dataset kecil yang diverifikasi manual.

**Kriteria selesai:** statistik cocok dengan perhitungan manual; gap tidak diisi;
label rata-rata per jam muncul konsisten; data tidak cukup ditandai.

### Phase 3 — Scope, Baseline, Perbandingan (1,5–2 hari)
- CRUD scope rule + evaluasi + pratinjau dampak.
- Snapshot baseline immutable.
- Perbandingan dua periode & vs baseline, delta pp vs persen relatif.
- Flag perubahan scope, kualitas, metadata, versi formula.
- Test konsistensi baseline.

**Kriteria selesai:** baseline tidak berubah saat data sumber berubah; perubahan
scope/kualitas selalu terlihat; delta tidak dihitung saat metadata tidak sebanding.

### Phase 4 — Simulator Resize (1–1,5 hari)
- Form input + validasi; perhitungan di `analysis/resize.py`.
- Flag >100%, ambang, kecukupan data, kandidat instance belum tervalidasi.
- Aturan biaya di `analysis/cost.py`.
- Simpan/daftar/hapus skenario + hasil.

**Kriteria selesai:** test kapasitas tetap, turun, naik, dan >100% lulus; tidak
ada nilai dipotong; tidak ada label rekomendasi.

### Phase 5 — Konfigurasi KPI (0,5–1 hari)
- Form konfigurasi terstruktur, draft, approve/reject eksplisit.
- Modul tetap "Belum Dikonfigurasi" default.
- Perhitungan hanya setelah approval, sesuai keputusan Q4.
- Test tidak ada `eval`/formula bebas dan KPI tidak tampil sebelum disetujui.

### Phase 6 — Export, Dokumentasi, Pengujian Akhir (1,5–2 hari)
- Export Excel semua sheet wajib + sanitasi formula.
- README, docs formula, asumsi/batasan, hasil pengujian.
- Dataset dummy final & template final.
- Manual QA seluruh halaman + verifikasi offline/tanpa jaringan.
- Perbaikan bug, freeze dependency final.

**Total perkiraan: 9–12 hari kerja (kasar).**

Urutan mengikuti brief: import/validasi → statistik → scope/baseline →
simulasi → export/testing; KPI ditunda sampai formula disetujui.

---

## 10. Rencana Pengujian

### 10.1 Pemetaan ke pengujian minimum brief

| Kewajiban brief | Test |
|---|---|
| Dataset kecil dengan statistik terverifikasi manual | `test_stats_and_completeness.py` (avg, P95 interpolasi linear, max; dicocokkan dengan pandas) |
| Nilai kosong, gap, duplikat, timezone, periode berbeda | `test_import_validation.py`, `test_stats_and_completeness.py`, `test_scope_and_baseline.py` |
| Pengecualian server & konsistensi baseline | `test_scope_and_baseline.py` (snapshot tetap setelah batch dihapus dan scope berubah) |
| Simulasi tetap, dikurangi, >100% | `test_resize_and_cost.py` (termasuk nilai tepat 100%) |
| Percentage point vs persen relatif | `test_scope_and_baseline.py` (termasuk A=0 → tidak terdefinisi) |
| Harga tidak tersedia & data tidak cukup | `test_resize_and_cost.py` |
| Tidak ada panggilan API cloud | `test_export_and_security.py` (scan impor + patch socket saat runtime) |
| Formula injection export | `test_export_and_security.py` (`=`, `+`, `-`, `@`, TAB, CR) |
| UI dasar | `test_ui_smoke.py` (7 halaman + form simulator + export download) |

### 10.2 Test tambahan

- Timezone: timestamp naive + IANA, timestamp ber-offset, DST ambigu/nonexistent
  (contoh zona DST), konsistensi antar batch.
- Duplikat: identik vs konflik di dalam file dan terhadap DB; tidak ada overwrite.
- Import parsial hanya dengan persetujuan eksplisit; rollback saat error.
- Validasi mapping kolom: field wajib belum dipetakan, mapping ganda, tipe salah.
- Kelengkapan: interval diketahui vs tidak, hasil >100%, `expected = 0`.
- Scope rules: matching case-insensitive, beberapa rule, alasan tercatat,
  baseline menyimpan exclusion hasil evaluasi.
- Perbandingan: perubahan scope, kualitas, stat type/interval → delta disupresi.
- Simulasi: metrik hilang, data tidak cukup, ambang dikonfigurasi, biaya dengan
  mata uang/satuan berbeda → tidak tampil.
- KPI: default unconfigured, tidak bisa dihitung sebelum approved, whitelist
  metode, tidak ada `eval`, threshold tumpang tindih ditolak.
- Export: sheet wajib ada, angka tetap numerik, teks sensitif disanitasi,
  label metode/versi tercantum.
- Regresi: batch dihapus → baseline/simulasi tetap terbaca; server tidak bisa
  dihapus jika punya sampel.

### 10.3 Bukti & laporan

- Jalankan `pytest -q` di environment bersih (Python 3.12, dependency pinned).
- `docs/hasil_pengujian.md`: tanggal, versi paket, jumlah test lulus/gagal,
  ringkasan manual checklist, bukti verifikasi offline, dan catatan bug.
- Manual checklist mencakup alur pengguna utama di setiap halaman serta
  pembukaan file export di Excel.

---

## 11. Deliverable & Dokumentasi

| Deliverable | Lokasi |
|---|---|
| Source code + dependency pinned | repo, `requirements*.txt` |
| README (instalasi, menjalankan, testing, batasan) | `README.md` |
| Template inventaris & time series | `data/templates/`, dibuat `scripts/make_templates.py` |
| Dataset dummy | `data/dummy/`, dibuat `scripts/seed_dummy.py` |
| Automated tests + hasil | `tests/`, `docs/hasil_pengujian.md` |
| Dokumentasi formula & metode | `docs/formula_dan_metode.md` |
| Dokumentasi asumsi & batasan | `docs/asumsi_dan_batasan.md` |
| Rencana ini | `IMPLEMENTATION_PLAN.md` |

Dokumentasi formula wajib memuat: definisi avg, P95 interpolasi linear (dengan contoh),
max, label statistik sumber, rumus kelengkapan, half-open window, delta pp vs
persen relatif, rumus resize, syarat biaya, metode agregat, dan skema KPI.

---

## 12. Asumsi Default

Asumsi berikut saya pakai kecuali Anda mengoreksi. Banyak di antaranya juga
muncul sebagai pertanyaan di bagian 13.

| No | Asumsi |
|---|---|
| A1 | Python 3.12 di venv; dependency exact pin; tanpa library tambahan di luar brief |
| A2 | Nama paket `cloudsim`, DB `data/app.db` (dapat dioverride via env untuk test) |
| A3 | Time series hanya bisa diimpor untuk server yang sudah ada di inventaris |
| A4 | Satu file time series = satu metrik (CPU atau memory); file gabungan diimpor dua kali |
| A5 | P95 interpolasi linear; rata-rata aritmetika; max dari sampel tersedia |
| A6 | Jendela analisis half-open di belakang layar; UI menampilkan tanggal inklusif |
| A7 | Timestamp internal UTC epoch; default tampilan Asia/Jakarta (dapat diubah) |
| A8 | Duplikat identik dilewati dengan laporan; konflik selalu error; tidak ada overwrite |
| A9 | Import parsial hanya jika pengguna mencentang persetujuan |
| A10 | Exclusion manual + rule bersifat OR; alasan wajib; tidak ada override include |
| A11 | Baseline immutable dan menyimpan snapshot, bukan referensi hidup |
| A12 | Simulasi per server; disimpan eksplisit; tipe instance bebas tanpa validasi katalog |
| A13 | Biaya = selisih harga sumber & target per satuan bila mata uang+satuan sama; tanpa konversi |
| A14 | KPI tidak dihitung sampai konfigurasi disetujui; hanya enum/metode whitelisted |
| A15 | Export tidak menyertakan raw time series |
| A16 | Tidak ada fitur backup/restore (tidak diminta brief); file DB dapat disalin manual saat aplikasi berhenti |
| A17 | Tanpa login/multi-user; localhost; telemetry Streamlit dimatikan |
| A18 | Environment/region/workload berupa teks bebas, filter memakai nilai unik yang ada |
| A19 | Ambang awal: kelengkapan 80%, minimal 24 sampel, peringatan simulasi 80% |
| A20 | Data dummy: ±12 server, data per jam selama 31 hari, beban sintetis, beberapa kasus gap/konflik |
| A21 | Repo di-`git init` lokal tanpa remote |
| A22 | Tidak ada dashboard "fleet utilization" tunggal; agregat hanya lewat metode eksplisit |

---

## 13. Pertanyaan yang Perlu Dikonfirmasi

### Wajib dikonfirmasi sebelum implementasi

**Q1. Metode P95 — DIPUTUSKAN**
Implementasi memakai interpolasi linear `(n-1) x 0,95`, setara pandas/Excel
`PERCENTILE.INC`. Nearest-rank tidak dipakai.

**Q2. Jendela analisis & kelengkapan**
Usulan: UI memilih tanggal inklusif; internal half-open; `expected =
floor(durasi/interval)`; hasil >100% ditampilkan sebagai peringatan, tidak
dipotong. Setuju?

**Q3. Duplikat & overwrite**
Usulan: duplikat identik dilewati dengan laporan; konflik selalu error; tidak ada
mode overwrite di MVP (hapus batch lama lalu impor ulang). Setuju?

**Q4. Cakupan KPI di versi pertama**
Usulan: sediakan konfigurasi terstruktur + approval gate, dan hitung KPI hanya
setelah disetujui, memakai metode whitelisted (tanpa formula karangan).
Alternatif: konfigurasi saja, perhitungan ditunda. Pilihan Anda: ?

**Q5. Agregat antarserver**
Usulan: tidak ada satu angka "utilization total kapasitas"; tampilkan per server,
plus agregat opsional berbobot vCPU/RAM dengan rumus dan `n/N` terlihat.
Apakah rata-rata sederhana antarserver juga perlu ditampilkan (dengan label
khusus), atau dihilangkan?

### Perlu konfirmasi, dapat memakai default

**Q6. Precedence scope**
Usulan: exclusion manual dan rule bersifat OR; tidak ada override include;
alasan wajib. Apakah perlu pengecualian per server terhadap rule (manual include)?

**Q7. Re-import inventaris**
Usulan: server_code yang sudah ada → error; perubahan data dilakukan lewat UI.
Apakah Anda memerlukan mode update eksplisit dengan preview perubahan?

**Q8. Import dengan baris error**
Usulan: default blokir; boleh "simpan hanya baris valid" hanya dengan centang.
Setuju?

**Q9. Simulasi saat data tidak cukup**
Usulan: tetap boleh dijalankan dengan peringatan menonjol dan persetujuan
eksplisit; hasil ditandai `insufficient_data`, bukan rekomendasi. Setuju?

**Q10. File gabungan CPU+memory**
Usulan: satu metrik per import. Apakah perlu dukungan satu file berisi dua metrik?

**Q11. Export raw samples**
Usulan: tidak menyertakan raw time series; hanya ringkasan/statistik/metadata.
Apakah raw data perlu sebagai sheet opsional?

**Q12. Ambang default**
Usulan awal: minimal 24 sampel, kelengkapan minimal 80%, ambang peringatan
resize 80% (semua dapat diubah). Angka lain?

**Q13. Satuan harga**
Usulan enum: per jam, per bulan, per vCPU-jam, per GiB-bulan, lainnya. Biaya hanya
selisih harga input dengan mata uang & satuan sama; tanpa konversi bulanan dan
tanpa asumsi harga proporsional. Setuju?

**Q14. Format angka & tanggal**
Usulan: dipilih eksplisit di wizard (desimal titik/koma; format tanggal daftar
tertentu); tidak menebak format ambigu. Setuju?

**Q15. Dataset dummy**
Usulan: ±12 server, 31 hari, interval 1 jam, dua region/environment, beberapa
server excluded/di-rule, gap, metrik hilang, dan satu high-utilization untuk
skenario >100%. Cukup representatif?

**Q16. Zona waktu tampilan**
Usulan default `Asia/Jakarta`, dapat diubah; sumber timezone per batch dicatat.
Setuju?

**Q17. Backup/restore**
Brief tidak meminta. Usulan: tidak dibuat; dokumentasikan cara menyalin
`data/app.db` saat aplikasi berhenti. Perlu fitur backup di versi ini?

**Q18. Klasifikasi environment/workload**
Usulan teks bebas + saran dari nilai yang sudah ada; rule exclusion memakai
exact match case-insensitive. Apakah perlu daftar nilai tetap (dropdown)
yang dapat dikonfigurasi?

---

## 14. Risiko & Mitigasi

| Risiko | Mitigasi |
|---|---|
| Timezone/DST salah tafsir | Wizard eksplisit, simpan UTC, tolak waktu ambigu, test DST, metadata per batch |
| P95 berbeda dari ekspektasi pemangku kepentingan | Metode didokumentasikan dengan contoh dan diuji; mudah diganti setelah keputusan Q1 |
| Data gap dianggap nol | Validasi menolak nilai kosong; UI menampilkan gap; test eksplisit |
| Pencampuran statistik/interval | Diblokir di `analysis_service`; label sumber di setiap tabel/export |
| Duplikat tersimpan diam-diam | Unique index + validasi pre-save + konflik error + test |
| Angka agregat menyesatkan | Tanpa skor tunggal; metode & bobot eksplisit; label "bukan total kapasitas" |
| Simulasi dianggap jaminan performa | Disclaimer tetap di UI, export, dan hasil tersimpan |
| Formula injection | Sanitasi terpusat + test karakter berbahaya |
| Ketergantungan tersembunyi ke cloud/telemetry | Config telemetry off, scan impor/dependency, QA offline |
| Volume data besar memperlambat dashboard | Index SQL, filter per jendela, ringkasan grafik dengan catatan; statistik tetap dari seluruh sampel |
| Scope creep (integrasi cloud, recommender otomatis) | Batas MVP ditulis; perubahan hanya dengan persetujuan |

---

## 15. Di Luar Cakupan MVP

- Koneksi/otorisasi cloud, pengambilan metrik otomatis, resize, atau eksekusi
  perintah cloud.
- Prediksi beban, machine learning, atau rekomendasi ukuran otomatis.
- Katalog harga/instance vendor, konversi mata uang, asumsi harga proporsional.
- Multi-tenant, login, role, kolaborasi.
- Backup/restore bawaan (pending Q17).
- Normalisasi statistik/interval yang berbeda (pending kebutuhan).
- AI, API eksternal, telemetri, atau layanan cloud saat runtime.
- Laporan KPI dengan formula yang belum disetujui pengguna.

---

## 16. Checklist Persetujuan

Implementasi MVP sudah tersedia; checklist di bawah adalah keputusan yang perlu
direview pengguna sebelum dianggap final:

- [x] Q1 metode P95 (interpolasi linear)
- [x] Q2 jendela & kelengkapan (default diimplementasikan)
- [x] Q3 kebijakan duplikat/overwrite (default diimplementasikan)
- [x] Q4 cakupan KPI (konfigurasi + approval gate diimplementasikan)
- [x] Q5 agregat antarserver (sederhana + berbobot vCPU/RAM)
- [x] Q6–Q18 (default diimplementasikan)
- [x] Struktur folder & nama paket `cloudsim`
- [x] Skema database bagian 3.2 (dengan kolom `metric` KPI)
- [x] Rancangan halaman bagian 4
- [x] Tahapan implementasi bagian 9

Review pengguna: ubah checklist menjadi persetujuan final setelah memeriksa
`README.md`, `docs/formula_dan_metode.md`, dan `docs/hasil_pengujian.md`.
