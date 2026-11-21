Bertindak sebagai software engineer. Bangun aplikasi lokal bernama
“Cloud Utilization & Rightsizing Simulator”.

TUJUAN
Menganalisis data historis utilization server, membandingkan periode,
dan menyimulasikan perubahan kapasitas. Aplikasi membantu rekomendasi
serta perhitungan KPI, bukan melakukan perubahan infrastruktur.

PENGGUNA DAN BATASAN
- Versi pertama untuk satu analis infrastruktur/arsitektur.
- Bahasa antarmuka Indonesia.
- Proyek dan database terpisah dari Cybersecurity Evidence Tracker.
- Gunakan data dummy selama pengembangan.
- Jangan meminta kredensial cloud, menghubungkan akun produksi,
  menjalankan resize, atau mengeksekusi perintah cloud.

TEKNOLOGI
- Python, Streamlit, SQLite, pandas, openpyxl, Plotly, pytest.
- Pisahkan UI, pemrosesan data, formula, dan penyimpanan.
- Berjalan di localhost tanpa API AI atau layanan cloud saat runtime.

INPUT
1. Inventaris server:
   - ID server, nama/alias, lingkungan, region, workload.
   - Jumlah vCPU, RAM GiB, dan tipe instance jika tersedia.
   - Status masuk scope serta alasan pengecualian.
   - Harga opsional, beserta mata uang, satuan, dan tanggal sumber harga.

2. Time series:
   - ID server, timestamp, CPU utilization %, memory utilization %.
   - Metadata zona waktu, interval, periode,
     serta jenis statistik sumber: Average/Maximum/lainnya.
   - Dukung template CSV standar dan wizard pemetaan kolom.
   - Jangan mengasumsikan format export CloudMonitor sudah diketahui.
   - Dukung data CPU dan memory dari file terpisah.

VALIDASI DATA
- Preview sebelum import disimpan.
- Periksa ID, timestamp, zona waktu, nilai di luar 0–100, dan duplikasi.
- Duplikat yang berkonflik harus ditandai, bukan dipilih diam-diam.
- Nilai kosong bukan nol. Jangan mengisi gap tanpa persetujuan.
- Tampilkan rentang data, jumlah sampel, dan persentase kelengkapan.
- Kelengkapan hanya dihitung jika interval pengamatan diketahui.
- Jangan mencampur statistik sumber atau interval berbeda tanpa
  aturan normalisasi yang jelas dan dapat diperiksa.

ANALISIS
- Statistik per server: rata-rata, P95, dan maksimum CPU/memory.
- Grafik time series serta perbandingan dua periode.
- Jelaskan metode rata-rata dan percentile yang digunakan.
- Jika sumbernya rata-rata per jam, labeli “P95 rata-rata per jam”
  dan “maksimum rata-rata per jam”; jangan mengklaim puncak sesaat.
- Tandai data yang tidak cukup, bukan otomatis merekomendasikan resize.
- Statistik gabungan antarserver harus memiliki metode pembobotan
  yang jelas; jangan menyebut rata-rata sederhana sebagai
  utilization seluruh kapasitas.

SCOPE DAN BASELINE
- Pengguna dapat mengecualikan server/workload beserta alasannya.
- Aturan pengecualian bersifat konfigurasi, bukan hardcode.
- Simpan snapshot baseline: daftar server, periode, statistik,
pengecualian, serta versi formula.
- Perbandingan harus menandai jika scope atau kualitas datanya berubah.

SIMULASI RESIZE
- Pengguna memasukkan kandidat kapasitas vCPU dan RAM baru.
- Estimasi sederhana:
  CPU baru = CPU lama × vCPU lama / vCPU baru.
  Memory baru = memory lama × RAM lama / RAM baru.
- Labeli sebagai estimasi dengan asumsi beban tetap.
- Estimasi CPU hanya relevan jika kemampuan per-vCPU sebanding.
- Tidak menjamin performa aplikasi, latency, throughput,
  maupun penggunaan memory aktual setelah resize.
- Nilai estimasi di atas 100% harus ditampilkan sebagai peringatan,
  bukan dipotong menjadi 100%.
- Ambang peringatan dapat dikonfigurasi.
- Tampilkan sebelum–sesudah beserta risiko kapasitas.
- Kandidat tipe instance belum tervalidasi harus diberi label jelas.
- Nyatakan bahwa I/O, jaringan, lisensi, dan kebutuhan aplikasi
  belum dinilai jika datanya tidak tersedia.

KPI DAN BIAYA
- Jangan mengarang formula KPI utilization.
- Siapkan konfigurasi terstruktur untuk baseline, target,
  pembobotan, aturan scope, dan batas capaian.
- Jangan menggunakan eval atau menjalankan formula berupa kode bebas.
- Modul KPI tetap “Belum Dikonfigurasi” sampai formula disetujui pengguna.
- Bedakan perubahan percentage point dari pertumbuhan relatif persen.
- Estimasi biaya hanya muncul jika harga sumber dan target tersedia
  dengan satuan serta mata uang yang konsisten.
- Jangan mengasumsikan harga turun proporsional dengan ukuran instance.

HALAMAN MVP
1. Import dan validasi data.
2. Inventaris dan pengaturan scope.
3. Dashboard utilization dan kualitas data.
4. Perbandingan periode/baseline.
5. Simulator resize.
6. Konfigurasi KPI.
7. Export Excel berisi data ringkasan, pengecualian,
   simulasi, asumsi, dan peringatan.

PENGUJIAN MINIMUM
- Dataset kecil dengan hasil statistik yang bisa diverifikasi manual.
- Nilai kosong, gap, duplikat, zona waktu, dan periode berbeda.
- Pengecualian server dan konsistensi baseline.
- Simulasi kapasitas tetap, dikurangi, dan estimasi melebihi 100%.
- Perbedaan percentage point versus persen relatif.
- Harga tidak tersedia dan data tidak cukup.
- Tidak ada panggilan ke API cloud saat aplikasi digunakan.
- Penanganan formula injection pada export Excel.

DELIVERABLE
- Source code, dependensi dengan versi terkontrol, README.
- Template inventaris dan time series, plus dataset dummy.
- Automated tests dan hasilnya.
- Dokumentasi formula, asumsi, serta batasan analisis.
- Petunjuk menjalankan aplikasi secara lokal.

CARA KERJA
Mulai dengan rencana, skema data, rancangan halaman, dan daftar keputusan
yang diperlukan. Tunggu persetujuan sebelum implementasi.
Kerjakan bertahap:
import/validasi → statistik → scope/baseline → simulasi → export/testing.
Tunda perhitungan KPI sampai formulanya disepakati.
Jangan menambah integrasi produksi atau fitur di luar MVP.
