# Hasil Pengujian

Tanggal pengujian: 2026-11-21

## 1. Environment

| Komponen | Versi |
|---|---|
| Python | 3.12.13 |
| pytest | 9.2.0 |
| Streamlit | 1.67.0 |
| pandas | 3.1.1 |
| openpyxl | 3.1.5 |
| Plotly | 7.1.0 |
| Database | SQLite (stdlib) |

Dependensi runtime dan dev di-pin di `requirements.txt`,
`requirements-dev.txt`, dan `requirements.lock.txt`.

## 2. Ringkasan otomatis

Perintah:

```bash
.venv/bin/python -m pytest -q
```

Hasil terakhir:

```text
84 passed in 1.22s
```

Rincian per file:

| File | Jumlah test | Fokus |
|---|---:|---|
| `tests/test_stats_and_completeness.py` | 8 | Avg/P95 linear/max, label sumber, jendela, kelengkapan, pp vs persen relatif |
| `tests/test_import_validation.py` | 23 | Nilai kosong, range, duplikat, konflik DB, timezone/DST, gap, metadata campuran, tipe batch |
| `tests/test_scope_and_baseline.py` | 10 | Exclusion manual/rule, snapshot immutable, perubahan scope/kualitas/metadata, delta pp |
| `tests/test_resize_and_cost.py` | 14 | Kapasitas tetap/turun, >100%, data kurang, exclusion, harga, snapshot simulasi |
| `tests/test_kpi_config.py` | 11 | Draft/approval, agregasi, between, baseline scope, threshold overlap, revoke |
| `tests/test_export_and_security.py` | 7 | Formula injection, sheet name, no network/cloud import, no eval/exec, socket runtime |
| `tests/test_db_and_settings.py` | 9 | Migrasi idempotent, versi DB, FK, validasi ambang/timezone, larangan hapus server |
| `tests/test_ui_smoke.py` | 2 | 7 halaman Streamlit, form simulator, export download |

## 3. Pemetaan ke kewajiban brief

| Kewajiban | Bukti |
|---|---|
| Dataset kecil dengan statistik terverifikasi manual | P95 `[10,20,30,40] = 38,5`; dicocokkan dengan pandas quantile linear |
| Nilai kosong, gap, duplikat, timezone, periode berbeda | Test import dan analisis; nilai kosong ditolak, gap tidak diimpor ulang |
| Pengecualian server & konsistensi baseline | Exclusion manual+rule; baseline tetap setelah batch sumber dihapus |
| Simulasi tetap, dikurangi, >100% | Kapasitas 4→2 dan 4→1; nilai 350% tidak dipotong |
| Percentage point vs persen relatif | 25%→30% = 5 pp dan 20%; A=0 → relatif tidak terdefinisi |
| Harga tidak tersedia & data tidak cukup | Selisih harga `NULL` dengan alasan; flag data belum cukup |
| Tidak ada panggilan API cloud | Scan AST impor + patch `socket` saat analisis/simulasi/export |
| Formula injection export | Semua sel berbahaya diberi apostrof; tidak ada sel formula, makro, atau external link |
| KPI tidak dikarang | Draft tidak dievaluasi; approval gate; whitelist enum; scan tanpa `eval`/`exec` |
| UI dasar | `AppTest` membuka 7 halaman, menghitung simulasi, dan menghasilkan download Excel |

## 4. Verifikasi seed dummy

Perintah:

```bash
.venv/bin/python -m scripts.seed_dummy --db /tmp/cloudsim_doc_seed.db --reset
```

Hasil:

```text
Inventaris: 12 server (batch #1).
cpu: 8848 sampel (batch #2).
memory: 8089 sampel (batch #3).
Baseline #1: 8 server dalam scope.
KPI sengaja tidak dibuat; modul tetap Belum Dikonfigurasi.
```

Seed memakai jalur service/validasi yang sama dengan aplikasi. Dataset berisi
gap, server tanpa data memory, exclusion manual, dan aturan exclusion dev.

## 5. Uji UI otomatis

`tests/test_ui_smoke.py` memakai `streamlit.testing.v1.AppTest`:

- semua 7 halaman dirender tanpa exception dan judul halaman sesuai;
- form simulator dapat menghitung estimasi untuk server dan target vCPU yang
  dipilih;
- tombol "Buat file Excel" menghasilkan satu tombol download.

Tidak diuji otomatis:

- upload file melalui komponen browser;
- edit sel `data_editor` threshold KPI secara interaktif;
- pembukaan file Excel di aplikasi desktop;
- aplikasi dengan dataset volume besar;
- jaringan benar-benar dimatikan di level OS (pengganti: scan impor dan patch
  socket pada test runtime).

## 6. Bug yang ditemukan dan diperbaiki saat pengujian

- Migrasi tidak menolak database dengan versi lebih baru; sekarang ditolak tanpa
  mengubah data.
- Deduplikasi nama sheet gagal saat menerima set kosong; sekarang memakai set
  yang sama dan menghasilkan `_2`, `_3`, dst.
- Pesan error vCPU kosong terlalu umum; sekarang eksplisit "nilai kosong tidak
  dianggap 0" untuk vCPU dan RAM.
- Validasi ambang pengaturan ditambahkan di service, tidak hanya di UI.
- State widget KPI setelah simpan/approve dan state pilihan setelah penghapusan
  distabilkan dengan pola pending/normalize.
- Peringatan deprecation Streamlit `use_container_width` dihapus.

## 7. Catatan keamanan

- Tidak ada library cloud, HTTP, atau proses eksternal di kode aplikasi.
- Tidak ada kredensial yang diminta atau disimpan.
- Aplikasi tidak menjalankan perintah resize/cloud.
- Telemetry Streamlit dimatikan; server dibatasi ke `127.0.0.1`.
- Export disanitasi terhadap formula injection dan tidak memuat sampel mentah.
- Semua data dummy fiktif; tidak ada nama vendor/harga nyata yang dikarang.

## 8. Kesimpulan

MVP lokal lulus 84 test otomatis dan verifikasi seed dummy. Statusnya siap
direview, bukan siap produksi. Persetujuan formula, ambang, dan cakupan KPI masih
menunggu keputusan pengguna.
