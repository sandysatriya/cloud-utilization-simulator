# Cloud Utilization & Rightsizing Simulator

Aplikasi lokal satu pengguna untuk menganalisis data utilization CPU/memory dari
file yang diimpor, membandingkan periode atau baseline, dan menyimulasikan
perubahan kapasitas. Semua data tersimpan di SQLite lokal.

Aplikasi **tidak** terhubung ke cloud atau akun produksi, **tidak** meminta
kredensial, **tidak** menjalankan resize, dan **tidak** menghasilkan rekomendasi
resize otomatis. Hasil simulasi adalah estimasi dengan asumsi beban tetap.

## Kemampuan MVP

- Import inventaris dan time series CSV/XLSX dengan pemetaan kolom, preview,
  validasi, deteksi duplikat/konflik, serta import parsial eksplisit.
- Statistik per server: rata-rata, P95, maksimum, jumlah sampel, kelengkapan,
  dan flag kualitas data.
- Dashboard utilization dengan grafik per server dan agregasi eksplisit
  (rata-rata sederhana atau berbobot vCPU/RAM).
- Scope server manual dan berbasis aturan (environment, workload, region,
  server), dengan alasan wajib.
- Baseline immutable dan perbandingan yang menandai perubahan scope, metadata,
  inventaris, dan kualitas data. Delta percentage point dan persen relatif
  dipisahkan.
- Simulator resize sederhana dengan flag normal/mendekati ambang/melebihi 100%/
  data belum cukup. Nilai di atas 100% tidak dipotong.
- Perbandingan harga input hanya bila mata uang dan satuan sama; tanpa konversi
  dan tanpa klaim penghematan bulanan.
- Konfigurasi KPI terstruktur dengan draft, persetujuan eksplisit, dan evaluasi
  hanya setelah disetujui.
- Export Excel berisi ringkasan, statistik, pengecualian, sumber data, baseline,
  simulasi, KPI, asumsi, dan peringatan. Data sampel mentah tidak diekspor.

## Struktur singkat

```text
app.py                  Entry point Streamlit
cloudsim/
  analysis/             Formula murni: statistik, kelengkapan, scope, resize, biaya, KPI
  db/                   Skema v1, koneksi, migrasi, repository
  io/                   Pembaca file, parser, sanitasi, penulis Excel
  services/             Alur import, analisis, baseline, simulasi, KPI, export
  ui/                   Navigasi, filter, format, dan 7 halaman Streamlit
scripts/                Init DB, seed dummy, generator data, template
tests/                  Test backend dan smoke test Streamlit
docs/                   Formula, asumsi/batasan, hasil pengujian
dummy_data/             Dataset fiktif deterministik
templates/              Template import
```

## Menjalankan aplikasi

Prasyarat: Python 3.12 (disarankan) dan `venv`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Seed database dummy (membuat ulang database bila `--reset` dipakai):

```bash
python -m scripts.seed_dummy --reset
```

Atau buat database kosong:

```bash
python -m scripts.init_db
```

Jalankan:

```bash
streamlit run app.py
```

Streamlit dibatasi ke `127.0.0.1` dan telemetry dimatikan melalui
`.streamlit/config.toml`.

Database default: `data/app.db`. Untuk memakai lokasi lain:

```bash
CLOUDSIM_DB_PATH=/path/ke/app.db streamlit run app.py
```

## Alur penggunaan

1. **Import & Validasi** — impor inventaris terlebih dahulu, lalu time series
   CPU dan memory. Periksa preview dan issue sebelum menyimpan.
2. **Inventaris & Scope** — lengkapi harga (opsional), atur server yang
   dikecualikan, aturan scope, dan ambang kualitas data.
3. **Dashboard Utilization** — pilih periode dan batch pada sidebar, lalu
   periksa statistik, kelengkapan, dan grafik.
4. **Perbandingan & Baseline** — buat baseline immutable dan bandingkan dengan
   periode aktif. Baca peringatan perubahan scope/metadata/kualitas.
5. **Simulator Resize** — pilih server dan kapasitas target. Periksa flag,
   asumsi, dan kecukupan data sebelum menyimpan skenario.
6. **Konfigurasi KPI** — susun definisi, simpan sebagai draft, lalu setujui.
   KPI tetap "Belum Dikonfigurasi" sampai disetujui.
7. **Export Excel** — pilih baseline/simulasi opsional, buat file, lalu unduh.

## Metode utama

- P95 memakai interpolasi linear `(n-1) x 0,95`, setara pandas/Excel
  `PERCENTILE.INC` — bukan nearest-rank dan bukan klaim puncak sesaat.
- Nilai kosong bukan nol; gap tidak diisi. Kelengkapan hanya dihitung bila
  interval sumber diketahui.
- Batch dengan jenis statistik atau interval berbeda tidak digabung; analisis
  diblokir sampai metadata seragam.
- Estimasi resize: `nilai_lama x kapasitas_sumber / kapasitas_target`, dengan
  asumsi beban tetap.
- Persentase poin (`B - A`) dan persen relatif (`(B - A) / A x 100`, hanya bila
  `A > 0`) adalah dua besaran berbeda.

Rincian rumus dan contoh: [`docs/formula_dan_metode.md`](docs/formula_dan_metode.md).
Asumsi dan batasan: [`docs/asumsi_dan_batasan.md`](docs/asumsi_dan_batasan.md).

## Pengujian

```bash
python -m pytest -q
```

Status terakhir: **84 test lulus**. Cakupan dan batas pengujian dijelaskan di
[`docs/hasil_pengujian.md`](docs/hasil_pengujian.md).

## Data dummy

`dummy_data/` berisi 12 server fiktif, data per jam selama 31 hari, beberapa gap,
satu server tanpa data memory, satu exclusion manual, dan satu aturan exclusion
environment. Semua harga dan nilai utilization fiktif. Lihat
`dummy_data/baca_saya.txt`.

## Batasan penting

- Hanya SQLite lokal, satu pengguna, tanpa login; bukan aplikasi multi-tenant.
- Skema database v1. Database dengan versi lebih baru ditolak, bukan diubah.
- Tidak ada backup/restore bawaan; salin `data/app.db` saat aplikasi berhenti.
- Tidak ada koneksi cloud, SDK cloud, AI API, atau telemetry aplikasi.
- Tipe instance target tidak divalidasi terhadap katalog vendor.
- Agregasi antarserver bukan utilization seluruh kapasitas kecuali bobotnya
  dijelaskan.
- Export tidak menyertakan sampel mentah.
