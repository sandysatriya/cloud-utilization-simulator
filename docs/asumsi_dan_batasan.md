# Asumsi dan Batasan

Dokumen ini mencatat asumsi yang dipakai implementasi MVP serta hal yang belum
boleh disimpulkan dari aplikasi.

## 1. Data dan sumber

- Aplikasi hanya membaca file yang diimpor pengguna. Tidak ada koneksi ke cloud,
  akun produksi, API eksternal, AI API, atau telemetry aplikasi.
- Inventaris harus diimpor sebelum time series; ID server harus sudah ada.
- Satu file time series berisi satu metrik (CPU atau memory). File gabungan
  diimpor dua kali.
- Timestamp internal adalah epoch UTC. Zona waktu sumber dicatat per batch dan
  dipakai saat import; zona waktu tampilan dapat diubah.
- Timestamp lokal tanpa offset divalidasi. Waktu yang ambigu atau tidak ada saat
  transisi DST ditolak, bukan ditebak.
- Utilization wajib berada di 0–100. Nilai kosong, non-angka, atau di luar
  rentang adalah error baris, bukan 0.
- Nilai kosong tidak diisi. Gap dibiarkan dan memengaruhi kelengkapan.
- Batch dengan jenis statistik atau interval berbeda tidak digabung. Analisis
  diblokir sampai pengguna memilih metadata yang seragam.
- Sumber `average`, `maximum`, dan `other` diberi label eksplisit. P95 dari data
  rata-rata per jam bukan puncak sesaat.
- Duplikat identik dilewati dengan peringatan; konflik nilai selalu error dan
  tidak menimpa data lama. Tidak ada mode overwrite di MVP.
- Import dengan baris bermasalah diblokir kecuali pengguna memilih import parsial
  secara eksplisit.
- File dengan hash sama diberi peringatan, tetapi tetap divalidasi per baris.

## 2. Statistik dan kualitas

- Statistik dihitung dari sampel yang tersedia di jendela `[start, end)`.
- Rata-rata adalah rata-rata aritmetika nilai sampel, bukan rata-rata berbobot
  waktu bila ada gap.
- P95 memakai interpolasi linear; bukan nearest-rank dan bukan jaminan puncak
  sesaat.
- Kelengkapan hanya dihitung bila interval diketahui. Tanpa interval,
  kelengkapan `NULL`, bukan 0.
- Nilai kelengkapan di atas 100% tidak dipotong; periksa metadata/grid waktu.
- `min_samples` dan `min_completeness_pct` adalah ambang konfigurasi, bukan
  kebenaran statistik. Data di bawah ambang ditandai, bukan dihapus.
- Statistik agregat hanya mencakup server yang memiliki nilai untuk metrik
  tersebut. Rata-rata sederhana bukan utilization seluruh kapasitas.
- Kapasitas berbobot memakai kapasitas inventaris saat ini untuk evaluasi
  periode aktif, dan kapasitas snapshot untuk scope baseline.

## 3. Scope dan baseline

- Exclusion manual dan aturan scope bersifat OR; alasan wajib.
- Tidak ada override "include" untuk server yang cocok dengan aturan exclusion.
- Aturan memakai exact match case-insensitive pada environment, workload,
  region, atau kode server.
- Server yang dikecualikan tidak dihitung dalam analisis dan tidak dapat
  disimulasikan.
- Server dengan data time series tidak dapat dihapus; gunakan status
  dikecualikan agar jejak data tetap ada.
- Baseline adalah snapshot immutable: statistik, metadata sumber, scope, dan
  exclusion disimpan saat pembuatan. Perubahan data/inventaris setelahnya tidak
  mengubah baseline.
- Perbandingan selalu menandai perubahan scope, exclusion, inventaris, metadata,
  dan kualitas. Jika metadata berbeda, hasil ditandai tidak sebanding; delta
  tetap ditampilkan sebagai informasi dan tidak boleh dianggap setara.
- Menghapus batch sumber tidak menghapus baseline, tetapi batch tersebut tidak
  lagi tersedia untuk analisis baru.

## 4. Simulasi resize

- Estimasi memakai asumsi beban tetap:
  `nilai_lama x kapasitas_sumber / kapasitas_target`.
- Asumsi ini tidak menjamin performa, latency, throughput, atau memory aktual.
- I/O, jaringan, lisensi, dan kebutuhan aplikasi belum dinilai.
- Tipe instance target hanya teks bebas dan tidak divalidasi terhadap katalog
  vendor.
- Tidak ada rekomendasi resize otomatis. Semua hasil berlabel estimasi.
- Estimasi di atas 100% tidak dipotong dan diberi flag.
- Data yang tidak cukup tetap dapat ditampilkan, tetapi diberi flag dan
  peringatan; aplikasi tidak menyimpulkan "aman".
- Snapshot simulasi menyimpan input, hasil, metadata batch, ambang, harga target,
  dan kelengkapan minimum. Snapshot harga sumber tidak disimpan, sehingga
  selisih harga tidak dihitung ulang dari simulasi tersimpan.

## 5. Biaya

- Harga bersifat input pengguna dan harus memiliki mata uang, satuan, serta
  tanggal sumber.
- Selisih harga hanya dihitung bila mata uang dan satuan sama. Tidak ada
  konversi mata uang atau asumsi harga proporsional.
- Selisih harga **bukan** estimasi penghematan bulanan dan tidak memperhitungkan
  diskon, komitmen, pajak, atau biaya lain.
- Data harga dummy bersifat fiktif dan tidak mewakili vendor nyata.

## 6. KPI

- KPI default "Belum Dikonfigurasi".
- Draft tidak dievaluasi. Evaluasi hanya untuk definisi berstatus `approved`.
- Hanya metrik, measure, agregasi, dan operator whitelisted. Tidak ada formula
  bebas, `eval`, atau eksekusi kode.
- Target dan operator ditentukan pengguna; aplikasi tidak mengarang formula KPI.
- Threshold capaian hanya dokumentasi dan tidak dipakai untuk menentukan
  lulus/gagal.
- Mode scope baseline memakai snapshot baseline; mode periode aktif memakai
  analisis yang sedang dipilih.
- KPI tidak boleh disetujui tanpa metrik, measure, agregasi, operator, dan
  target yang lengkap. Batas atas wajib untuk operator `between`.

## 7. Export dan keamanan

- Export tidak menyertakan data sampel mentah.
- Teks berawalan `=`, `+`, `-`, `@`, TAB, atau CR disanitasi agar tidak menjadi
  formula Excel.
- Nama sheet dibersihkan dan dibatasi 31 karakter; tidak ada makro atau tautan
  eksternal.
- File hasil export tetap harus diperiksa pengguna sebelum dibagikan.
- Aplikasi berjalan di localhost, tanpa login. Jangan mengekspos port ke jaringan
  publik.
- Tidak ada backup/restore bawaan. Salin `data/app.db` saat aplikasi berhenti.

## 8. Batasan teknis dan cakupan

- SQLite lokal, satu pengguna, tanpa multi-tenant/role/kolaborasi.
- Skema database v1 belum memiliki migrasi otomatis antarversi. Database versi
  lebih lama atau lebih baru ditolak dengan pesan yang aman.
- Tidak ada integrasi cloud, prediksi beban, machine learning, atau recommender
  otomatis.
- Tidak ada normalisasi otomatis untuk statistik/interval berbeda.
- Tidak ada katalog harga/instance vendor.
- Performa untuk dataset sangat besar belum diuji; indeks SQL dan filter jendela
  sudah tersedia.
- Test UI memakai Streamlit `AppTest` untuk render halaman, form simulator, dan
  export. Upload file melalui komponen browser, pembukaan file Excel di aplikasi
  desktop, dan uji jaringan terputus tetap perlu QA manual.
- Belum ada persetujuan formal pengguna atas formula/ambang. Perubahan setelah
  review harus disertai versi formula baru dan pengujian ulang.
