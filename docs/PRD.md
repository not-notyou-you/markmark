# Markmark PRD

Tanggal: 2026-10-31

## Ringkasan

Markmark adalah aplikasi yang dipasang di laptop pengguna untuk mempercepat pengoreksi menemukan kesalahan pada jawaban siswa, sehingga proses koreksi menjadi lebih cepat dan teliti.

Markmark tidak menentukan nilai. Penilaian tetap di tangan pengoreksi melalui human proof: setiap temuan AI harus diperiksa dan diputuskan oleh pengoreksi.

Tagline: *Every mark has a citation.*

## Masalah

Mengoreksi banyak jawaban siswa setiap minggu memakan waktu dan melelahkan, sehingga kesalahan mudah terlewat dan ketelitian sulit dijaga. AI bisa membantu mencari kesalahan, tetapi temuannya tetap bisa keliru dan perlu diperiksa manusia.

## Tujuan

- Mempercepat pengoreksi menemukan kesalahan pada jawaban siswa.
- Membuat koreksi lebih teliti dan konsisten.
- Menampilkan bukti setiap temuan agar mudah diperiksa.
- Menjaga keputusan penilaian tetap di tangan pengoreksi.

**Di luar cakupan:** Markmark tidak memberi nilai otomatis, bukan LMS, dan bukan detektor plagiarisme atau detektor AI.

## Pengguna

| Pengguna | Kebutuhan utama |
| --- | --- |
| Dosen atau guru | Menemukan kesalahan lebih cepat tanpa kehilangan kendali atas nilai |
| Asisten pengajar | Daftar temuan yang jelas untuk diperiksa |

Setiap pengguna memasang Markmark di laptopnya sendiri dan mengelola datanya sendiri.

## Struktur data

| Objek | Isi dan hubungan |
| --- | --- |
| Pengguna | Memiliki banyak kelas dan banyak mata pelajaran |
| Kelas | Memiliki banyak murid; bisa mengikuti banyak mata pelajaran |
| Mata pelajaran | Bisa diikuti banyak kelas; memiliki banyak minggu |
| Minggu | Bagian dari satu mata pelajaran; memiliki modul dan kunci jawaban |
| Modul | Materi minggu tersebut; opsional |
| Kunci jawaban | Diunggah pengguna atau dibuatkan AI dari modul |
| Jawaban siswa | Milik satu murid, untuk satu minggu pada satu mata pelajaran |
| Temuan | Kesalahan yang ditemukan AI beserta buktinya dan keputusan pengoreksi |

## Alur pengguna

1. Pasang Markmark di laptop.
2. Buat kelas dan masukkan daftar murid.
3. Buat mata pelajaran, lalu hubungkan dengan satu atau beberapa kelas.
4. Buat minggu pada mata pelajaran.
5. Unggah modul jika ada.
6. Unggah kunci jawaban, atau minta AI membuatnya dari modul.
7. Unggah jawaban siswa.
8. Jalankan koreksi.
9. Periksa setiap temuan, lalu tentukan penilaian.

## Aturan utama

- Koreksi hanya bisa dijalankan jika kunci jawaban dan jawaban siswa sudah tersedia.
- Tanpa salah satunya, tombol koreksi nonaktif dan aplikasi menampilkan apa yang kurang.
- Kunci jawaban buatan AI hanya tersedia jika modul sudah ada.
- Kunci jawaban buatan AI harus ditinjau dan disetujui pengguna sebelum dipakai.
- AI hanya menampilkan temuan dan tidak pernah membuat nilai.
- Temuan belum dianggap final sebelum diputuskan pengoreksi.

## Kebutuhan fungsional

| ID | Kebutuhan | Prioritas |
| --- | --- | --- |
| F1 | Membuat, mengubah, dan menghapus kelas | P0 |
| F2 | Mengelola murid per kelas, termasuk impor daftar murid | P0 |
| F3 | Membuat mata pelajaran dan menghubungkannya dengan banyak kelas | P0 |
| F4 | Mengelola minggu pada setiap mata pelajaran | P0 |
| F5 | Mengunggah modul per minggu | P0 |
| F6 | Mengunggah kunci jawaban per minggu | P0 |
| F7 | Membuat draf kunci jawaban dengan AI dari modul | P0 |
| F8 | Mengunggah jawaban siswa dan mencocokkannya dengan murid | P0 |
| F9 | Memblokir koreksi sampai syaratnya terpenuhi | P0 |
| F10 | Menemukan kesalahan dan menyertakan bukti dari jawaban siswa | P0 |
| F11 | Memverifikasi bukti; temuan tanpa bukti ditandai perlu dicek | P0 |
| F12 | Human proof: pengoreksi menerima, menolak, atau mengubah setiap temuan | P0 |
| F13 | Menampilkan bukti di dalam konteks jawaban siswa | P0 |
| F14 | Menyimpan keputusan dan penilaian pengoreksi | P0 |
| F15 | Mengekspor rekap penilaian | P1 |
| F16 | Menghasilkan umpan balik untuk siswa dari temuan yang disetujui | P1 |

## Kebutuhan non-fungsional

| ID | Kebutuhan |
| --- | --- |
| N1 | Instalasi mudah di laptop Windows, macOS, dan Linux |
| N2 | Data kelas, murid, dan jawaban tersimpan di laptop pengguna |
| N3 | Nama dan nomor induk disamarkan sebelum data dikirim ke layanan AI |
| N4 | Isi jawaban siswa diperlakukan sebagai data, bukan perintah untuk AI |
| N5 | API key disimpan dengan aman di laptop pengguna |
| N6 | Proses koreksi bisa dihentikan dan dilanjutkan |
| N7 | Tampilan mendukung Bahasa Indonesia dan Inggris |

## Metrik keberhasilan

Target berikut masih usulan dan perlu dikonfirmasi setelah uji awal.

| Metrik | Target |
| --- | --- |
| Waktu koreksi per jawaban | Turun ≥ 50% dibanding koreksi manual |
| Temuan AI yang benar menurut pengoreksi | ≥ 90% |
| Kesalahan nyata yang berhasil ditemukan AI | ≥ 80% |
| Temuan yang diputuskan pengoreksi sebelum penilaian final | 100% |

## Tahap rilis

1. **Dasar:** instalasi, kelas, murid, mata pelajaran, dan minggu.
2. **Materi:** modul, kunci jawaban, dan jawaban siswa.
3. **Koreksi:** temuan AI, bukti, dan aturan syarat koreksi.
4. **Human proof:** peninjauan temuan dan penyimpanan penilaian.
5. **Lanjutan:** kunci jawaban buatan AI, ekspor, dan umpan balik.

## Risiko

| Risiko | Mitigasi |
| --- | --- |
| Temuan AI keliru | Bukti wajib dan keputusan pengoreksi |
| Pengoreksi menyetujui tanpa membaca | Bukti ditampilkan di konteks, keputusan per temuan |
| Kunci jawaban buatan AI salah | Wajib ditinjau dan disetujui sebelum dipakai |
| Data siswa bocor | Penyimpanan lokal dan penyamaran data |
| Jawaban siswa memanipulasi AI | Isi jawaban dipisahkan dari instruksi AI |

## Keputusan terbuka

- [ ] Konfirmasi hubungan kelas dan mata pelajaran: satu kelas bisa mengikuti banyak mata pelajaran, dan sebaliknya
- [ ] Tentukan layanan AI: API key milik pengguna, model lokal, atau keduanya
- [ ] Tentukan format file jawaban yang didukung pada rilis pertama
- [ ] Cek ketersediaan nama Markmark
