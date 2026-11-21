# Formula dan Metode

Dokumen ini menjelaskan perhitungan yang dipakai aplikasi. Semua formula
dipusatkan di `cloudsim/analysis/`; UI dan export hanya menampilkan hasil.
Versi formula yang tersimpan di baseline/simulasi/KPI: `stats-v1`,
`compare-v1`, `resize-v1`, `kpi-config-v1`.

## 1. Statistik per server

Untuk sampel utilization CPU atau memory yang **tersedia** di jendela analisis
`[start, end)`:

- `avg` = rata-rata aritmetika seluruh nilai sampel.
- `P95` = interpolasi linear:
  - urutkan nilai menaik;
  - `posisi = (n - 1) x 0,95`;
  - `P95 = nilai[bawah] + (posisi - bawah) x (nilai[atas] - nilai[bawah])`,
    dengan `bawah = floor(posisi)` dan `atas = ceil(posisi)`.
  - Ini sama dengan pandas `quantile(0.95, interpolation="linear")` dan Excel
    `PERCENTILE.INC`.
- `max` = nilai maksimum sampel yang tersedia.

Contoh `[10, 20, 30, 40]`: `posisi = 3 x 0,95 = 2,85`; P95 =
`30 + 0,85 x (40 - 30) = 38,5`. Rata-rata = 25; maksimum = 40.

Jika tidak ada sampel, statistik bernilai `NULL` dan UI menampilkan
"tidak tersedia". Nilai kosong tidak diubah menjadi 0, dan gap tidak diisi.

Label sumber selalu menyebut metadata batch:

- sumber `average`, interval 1 jam → "P95 rata-rata per jam";
- sumber `maximum` → "P95 dari maksimum per jam";
- sumber `other` → label pengguna, mis. "P95 dari median per jam".

P95 dari data rata-rata per interval **bukan** puncak sesaat.

## 2. Kelengkapan data

```
durasi      = end_utc - start_utc            # detik, half-open
diharapkan  = floor(durasi / interval_seconds)
tersedia    = jumlah sampel valid server + metrik di jendela
kelengkapan = tersedia / diharapkan x 100
```

- Hanya dihitung bila `interval_seconds` diketahui dan `diharapkan > 0`.
- Jika interval tidak diketahui, kelengkapan `NULL`, bukan 0, dan diberi flag
  "Kelengkapan tidak dapat dihitung".
- Nilai di atas 100% tidak dipotong. Nilai tersebut menandakan metadata atau
  grid waktu perlu diperiksa.
- Timestamp yang tidak selaras dengan grid interval diberi peringatan saat
  import, tidak diperbaiki otomatis.
- UI memilih tanggal inklusif; internal memakai `end` = awal hari setelah
  tanggal akhir pada zona waktu tampilan.

Contoh: jendela 6 jam, interval 1 jam, hanya 4 sampel → `4 / 6 x 100 = 66,67%`.
Tidak ada dua sampel sintetis yang ditambahkan.

## 3. Perbandingan periode/baseline

- `delta_pp = B - A` — percentage point, satuan sama dengan utilization (%).
- `perubahan_relatif = ((B - A) / A) x 100%` — hanya jika `A > 0`.
- Jika `A = 0` atau data tidak tersedia, persen relatif `NULL`/"tidak
  terdefinisi"; tidak diganti angka lain.
- Kedua nilai selalu diberi label berbeda.

Contoh: `A = 25%`, `B = 30%` → delta `5 pp`, perubahan relatif `20%`.

Perbandingan juga menandai:

- server masuk/keluar scope dan perubahan exclusion;
- perubahan environment/kapasitas inventaris;
- perubahan jenis statistik, interval, atau versi formula;
- perubahan jumlah sampel, kelengkapan, atau flag kualitas.

Jika metadata berbeda, perbandingan diberi status **tidak sebanding**
(`comparable = false`) dan peringatan ditampilkan. Delta tetap terlihat sebagai
informasi, tetapi tidak boleh dianggap setara.

## 4. Agregasi antarserver

Dua metode eksplisit:

- **Rata-rata sederhana**: `sum(nilai_server) / jumlah_server_yang_punya_nilai`.
  Bukan utilization seluruh kapasitas.
- **Berbobot vCPU**: `sum(nilai_i x vcpu_i) / sum(vcpu_i)`.
- **Berbobot RAM**: `sum(nilai_i x ram_i) / sum(ram_i)`.

Server tanpa nilai untuk metrik tersebut tidak disertakan. Jumlah yang
dihitung dan total server ditampilkan.

Contoh berbobot vCPU: A `P95 = 38,5`, 4 vCPU; B `P95 = 48,5`, 8 vCPU →
`(38,5 x 4 + 48,5 x 8) / 12 = 45,1667`.

Tidak ada satu angka "utilization total fleet" tanpa penjelasan metode dan
cakupan.

## 5. Estimasi resize

Untuk setiap statistik yang tersedia:

```
estimasi_setelah = nilai_sebelum x kapasitas_sumber / kapasitas_target
```

- Kapasitas CPU memakai vCPU; memory memakai GiB.
- Asumsi: beban tetap, kemampuan per-vCPU sebanding, dan distribusi beban tidak
  berubah.
- Tidak menjamin performa, latency, throughput, atau memory aktual.
- I/O, jaringan, lisensi, dan kebutuhan aplikasi belum dinilai.
- Tipe instance target tidak divalidasi terhadap katalog vendor.
- Hasil bukan rekomendasi resize otomatis.

Klasifikasi flag:

- `normal`: estimasi < ambang peringatan.
- `near_threshold`: estimasi >= ambang peringatan dan <= 100%.
- `over_100`: estimasi > 100%; **tidak dipotong**.
- `insufficient_data`: sampel/kelengkapan di bawah ambang.
- `not_available`: statistik sumber tidak tersedia.

Kecukupan data memakai ambang `min_samples` dan `min_completeness_pct` dari
pengaturan, serta batas per metrik. Kelengkapan minimum simulasi adalah nilai
terendah dari metrik yang tersedia.

Contoh: CPU rata-rata 25%, sumber 4 vCPU, target 2 vCPU → 50%. Target 1 vCPU →
100%, flag "mendekati ambang", bukan "melebihi 100%". Memory 87,5% dari 8 GiB ke
2 GiB → 350% dan flag `over_100`.

## 6. Biaya

Aplikasi hanya menghitung selisih harga input:

```
selisih = harga_target - harga_sumber
```

Syarat:

- harga sumber dan target sama-sama tersedia;
- mata uang sama;
- satuan sama (`per_hour`, `per_month`, `per_vcpu_hour`, `per_gib_month`, atau
  `other` dengan label sama).

Jika salah satu syarat tidak terpenuhi, selisih tidak dihitung dan alasannya
ditampilkan. Tidak ada konversi mata uang, asumsi harga proporsional, atau
klaim penghematan bulanan.

## 7. KPI

Definisi KPI menyimpan:

- `metric`: `cpu` atau `memory`;
- `measure`: `avg`, `p95`, atau `max`;
- `aggregate_method`: `none`, `simple_mean`, `capacity_weighted_vcpu`, atau
  `capacity_weighted_ram`;
- `operator`: `lte`, `gte`, atau `between`;
- target dan batas atas (untuk `between`);
- scope: periode aktif atau snapshot baseline;
- threshold capaian (dokumentasi).

Evaluasi hanya berjalan bila status `approved`. Nilai dihitung dari statistik
yang sudah ada, memakai agregasi di bagian 4. Operator dibandingkan dengan
target pengguna. Tidak ada formula bebas, `eval`, atau kode dari input.

`threshold` capaian tidak dipakai untuk menghitung lulus/gagal; evaluasi memakai
target dan operator. Threshold hanya dokumentasi sampai ada keputusan formula
bertingkat.

KPI yang belum disetujui selalu "Belum Dikonfigurasi" dan tidak menghasilkan
skor.

## 8. Keamanan export

Semua teks yang diawali `=`, `+`, `-`, `@`, TAB, atau CR diberi awalan apostrof
saat ditulis ke Excel. Nama sheet dibersihkan dari karakter terlarang dan
dibatasi 31 karakter. File tidak berisi makro atau tautan eksternal. Data
sampel mentah tidak diekspor.

## 9. Batasan interpretasi

- Rata-rata dari sampel adalah rata-rata nilai yang tersedia, bukan rata-rata
  berbobot waktu jika sampel tidak lengkap.
- Utilization 0–100% adalah utilization yang dilaporkan sumber, bukan hasil
  pengukuran ulang aplikasi.
- Semua hasil bergantung pada kualitas dan metadata file yang diimpor.
