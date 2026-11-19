# KantinKu Web (Flask)

Aplikasi ini adalah konversi KantinKu dari Streamlit ke web Flask. Fitur: login 3 peran, katalog menu, pemesanan siswa, stok otomatis berkurang, status pesanan, kelola menu, dashboard admin, dan laporan penjualan.

## 1. Persiapan
Install Python 3.10 atau lebih baru. Buka terminal di folder proyek.

## 2. Instalasi
```bash
python -m venv venv
```
Windows:
```bash
venv\Scripts\activate
```
Mac/Linux:
```bash
source venv/bin/activate
```
Lalu:
```bash
pip install -r requirements.txt
```

## 3. Jalankan
```bash
python app.py
```
Buka browser ke: http://127.0.0.1:5000

Database `kantinku.db` akan dibuat otomatis saat aplikasi pertama kali dijalankan.

## Akun demo
- Siswa: `siswa` / `siswa123`
- Penjual: `penjual` / `jual123`
- Admin: `admin` / `admin123`

## Catatan
- Data disimpan di SQLite lokal dalam file `kantinku.db`.
- Akun dan password di atas hanya untuk demo. Sebelum dipublikasikan, ganti password demo dan `SECRET_KEY`, gunakan HTTPS, serta tambahkan perlindungan CSRF dan validasi/otorisasi lebih lanjut.
- Untuk membuat web bisa diakses orang lain melalui internet, aplikasi perlu di-deploy ke layanan hosting yang mendukung Flask.
