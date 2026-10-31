# Markmark

*Every mark has a citation.*

Markmark membantu pengoreksi menemukan kesalahan pada jawaban siswa lebih cepat dan lebih teliti. Markmark tidak menentukan nilai: setiap temuan AI diperiksa pengoreksi melalui human proof, dan penilaian tetap di tangan pengoreksi.

## Pasang dan jalankan

Butuh [Python 3.10 atau lebih baru](https://www.python.org/downloads/). Saat memasang di Windows, centang **Add Python to PATH**.

1. Unduh repo ini, lalu ekstrak.
2. Jalankan:
   - **Windows:** klik dua kali `run.bat`
   - **macOS atau Linux:** `sh run.sh`
3. Markmark terbuka di browser. Pemasangan pertama butuh internet dan beberapa menit.

## Atur layanan AI

Buka **Pengaturan**, pilih layanan, lalu isi nama model dan API key.

| Layanan | Catatan |
| --- | --- |
| Gemini atau OpenAI | Butuh API key milik sendiri |
| Ollama | Model berjalan di laptop, jadi jawaban tidak keluar dari laptop dan tidak perlu API key |
| Layanan lain | Bisa dipakai jika kompatibel dengan API OpenAI |

## Cara pakai

1. Buat kelas dan isi daftar murid.
2. Buat mata pelajaran, lalu centang kelas yang mengikutinya.
3. Tambah minggu dan unggah modul jika ada.
4. Unggah kunci jawaban, atau buat dengan AI dari modul lalu setujui.
5. Unggah jawaban siswa, satu per satu atau dalam zip. File dicocokkan lewat nomor atau nama murid pada nama file atau folder.
6. Klik **Mulai koreksi**. Tombol ini aktif jika kunci jawaban dan jawaban siswa sudah tersedia.
7. Periksa setiap temuan: terima, tolak, atau ubah. Nilai baru bisa disimpan setelah semua temuan diputuskan.
8. Ekspor rekap ke CSV.

## Format file

- **Terbaca:** PDF berteks, DOCX, ipynb, teks, kode, dan zip berisi file tersebut.
- **Belum terbaca:** gambar dan PDF hasil scan. File ini dilewati dan disebutkan saat diunggah.
- Gambar output pada notebook tidak dilihat AI.

## Data dan privasi

Semua data disimpan di folder `.markmark` pada direktori pengguna. Sebelum dikirim ke layanan AI, nama dan nomor murid disamarkan. Penyamaran ini tidak bisa menangkap nama orang lain di dalam jawaban, jadi tetap periksa kebijakan data layanan yang dipakai, terutama tier gratis.

API key disimpan di keychain sistem. Jika keychain tidak tersedia, key disimpan di file `.markmark/api_key`.

## Pengembangan

```sh
python -m venv .venv
.venv/bin/pip install -e ".[dev]"    # Windows: .venv\Scripts\pip
.venv/bin/pytest
```

Kebutuhan produk ada di [docs/PRD.md](docs/PRD.md).
