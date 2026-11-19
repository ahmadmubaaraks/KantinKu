import os, sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "ganti-secret-key-ini-untuk-deployment")
DB = os.path.join(os.path.dirname(__file__), "kantinku.db")

def connect():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            nama TEXT NOT NULL,
            role TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS menu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            kategori TEXT NOT NULL,
            harga INTEGER NOT NULL,
            stok INTEGER NOT NULL DEFAULT 0,
            aktif INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            waktu TEXT NOT NULL,
            total INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Menunggu',
            catatan TEXT DEFAULT '',
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            menu_nama TEXT NOT NULL,
            jumlah INTEGER NOT NULL,
            harga INTEGER NOT NULL,
            subtotal INTEGER NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id)
        );
        """)
        if con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            users = [
                ("siswa", generate_password_hash("siswa123"), "Siswa Demo", "siswa"),
                ("penjual", generate_password_hash("jual123"), "Penjual Kantin", "penjual"),
                ("admin", generate_password_hash("admin123"), "Administrator", "admin")
            ]
            con.executemany("INSERT INTO users(username,password,nama,role) VALUES(?,?,?,?)", users)
        if con.execute("SELECT COUNT(*) FROM menu").fetchone()[0] == 0:
            menus = [
                ("Nasi Goreng","Makanan",12000,10,1), ("Mie Ayam","Makanan",10000,10,1),
                ("Bakso","Makanan",12000,8,1), ("Soto Ayam","Makanan",15000,7,1),
                ("Es Teh","Minuman",5000,15,1), ("Jus Jeruk","Minuman",8000,10,1)
            ]
            con.executemany("INSERT INTO menu(nama,kategori,harga,stok,aktif) VALUES(?,?,?,?,?)", menus)

def login_required(role=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("login"))
            if role and session.get("role") not in ([role] if isinstance(role, str) else role):
                flash("Kamu tidak memiliki akses ke halaman tersebut.", "error")
                return redirect(url_for("index"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def rupiah(value):
    return "Rp" + f"{int(value):,}".replace(",", ".")
app.jinja_env.filters["rupiah"] = rupiah

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with connect() as con:
            user = con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if user and check_password_hash(user["password"], password):
            session.clear()
            session.update(user_id=user["id"], username=user["username"], nama=user["nama"], role=user["role"])
            return redirect(url_for("index"))
        flash("Username atau password salah.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Kamu sudah keluar dari akun.", "success")
    return redirect(url_for("login"))

@app.route("/")
@login_required()
def index():
    role = session["role"]
    with connect() as con:
        if role == "siswa":
            menus = con.execute("SELECT * FROM menu WHERE aktif=1 ORDER BY kategori,nama").fetchall()
            orders = con.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (session["user_id"],)).fetchall()
            order_items = {}
            for o in orders:
                order_items[o["id"]] = con.execute("SELECT * FROM order_items WHERE order_id=?", (o["id"],)).fetchall()
            return render_template("index.html", page="siswa", menus=menus, orders=orders, order_items=order_items)
        if role == "penjual":
            orders = con.execute("""SELECT orders.*, users.nama AS siswa FROM orders
                                    JOIN users ON users.id=orders.user_id ORDER BY orders.id DESC""").fetchall()
            items = {o["id"]: con.execute("SELECT * FROM order_items WHERE order_id=?", (o["id"],)).fetchall() for o in orders}
            menus = con.execute("SELECT * FROM menu ORDER BY id DESC").fetchall()
            done = con.execute("SELECT COUNT(*) n, COALESCE(SUM(total),0) total FROM orders WHERE status='Selesai'").fetchone()
            return render_template("index.html", page="penjual", orders=orders, order_items=items, menus=menus, done=done)
        users = con.execute("SELECT username,nama,role FROM users ORDER BY id").fetchall()
        menus = con.execute("SELECT * FROM menu ORDER BY id DESC").fetchall()
        orders = con.execute("""SELECT orders.*, users.nama AS siswa FROM orders
                                JOIN users ON users.id=orders.user_id ORDER BY orders.id DESC""").fetchall()
        done = con.execute("SELECT COALESCE(SUM(total),0) total FROM orders WHERE status='Selesai'").fetchone()["total"]
        return render_template("index.html", page="admin", users=users, menus=menus, orders=orders, done=done)

@app.route("/order", methods=["POST"])
@login_required("siswa")
def order():
    quantities = request.form
    note = quantities.get("catatan", "").strip()
    with connect() as con:
        selected = []
        total = 0
        for key, value in quantities.items():
            if not key.startswith("qty_"):
                continue
            try:
                mid, qty = int(key[4:]), int(value)
            except ValueError:
                continue
            if qty <= 0:
                continue
            item = con.execute("SELECT * FROM menu WHERE id=? AND aktif=1", (mid,)).fetchone()
            if not item or qty > item["stok"]:
                flash("Stok salah satu menu tidak mencukupi. Periksa kembali pesanan.", "error")
                return redirect(url_for("index"))
            selected.append((item, qty))
            total += item["harga"] * qty
        if not selected:
            flash("Pilih minimal satu menu dengan jumlah lebih dari nol.", "error")
            return redirect(url_for("index"))
        cur = con.execute("INSERT INTO orders(user_id,waktu,total,status,catatan) VALUES(?,?,?,?,?)",
                          (session["user_id"], datetime.now().strftime("%d-%m-%Y %H:%M"), total, "Menunggu", note))
        oid = cur.lastrowid
        for item, qty in selected:
            con.execute("INSERT INTO order_items(order_id,menu_nama,jumlah,harga,subtotal) VALUES(?,?,?,?,?)",
                        (oid, item["nama"], qty, item["harga"], item["harga"] * qty))
            con.execute("UPDATE menu SET stok=stok-? WHERE id=?", (qty, item["id"]))
    flash(f"Pesanan #{oid} berhasil dibuat!", "success")
    return redirect(url_for("index"))

@app.route("/status/<int:oid>", methods=["POST"])
@login_required("penjual")
def update_status(oid):
    status = request.form.get("status")
    allowed = ["Menunggu", "Sedang diproses", "Siap diambil", "Selesai", "Dibatalkan"]
    if status not in allowed:
        flash("Status tidak valid.", "error")
    else:
        with connect() as con:
            con.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
        flash("Status pesanan diperbarui.", "success")
    return redirect(url_for("index"))

@app.route("/menu/tambah", methods=["POST"])
@login_required(["penjual", "admin"])
def add_menu():
    nama = request.form.get("nama", "").strip()
    kategori = request.form.get("kategori")
    try:
        harga, stok = int(request.form.get("harga", 0)), int(request.form.get("stok", 0))
    except ValueError:
        harga, stok = -1, -1
    if not nama or kategori not in ["Makanan", "Minuman"] or harga < 0 or stok < 0:
        flash("Data menu tidak valid.", "error")
    else:
        with connect() as con:
            con.execute("INSERT INTO menu(nama,kategori,harga,stok,aktif) VALUES(?,?,?,?,1)", (nama,kategori,harga,stok))
        flash("Menu berhasil ditambahkan.", "success")
    return redirect(url_for("index"))

@app.route("/menu/edit/<int:mid>", methods=["POST"])
@login_required(["penjual", "admin"])
def edit_menu(mid):
    try:
        harga, stok = int(request.form.get("harga", 0)), int(request.form.get("stok", 0))
    except ValueError:
        harga, stok = -1, -1
    aktif = 1 if request.form.get("aktif") == "on" else 0
    if harga < 0 or stok < 0:
        flash("Harga dan stok tidak boleh negatif.", "error")
    else:
        with connect() as con:
            con.execute("UPDATE menu SET harga=?,stok=?,aktif=? WHERE id=?", (harga,stok,aktif,mid))
        flash("Perubahan menu disimpan.", "success")
    return redirect(url_for("index"))

@app.route("/laporan")
@login_required(["penjual", "admin"])
def report():
    with connect() as con:
        rows = con.execute("""SELECT orders.id, users.nama AS pemesan, orders.waktu, orders.total
                              FROM orders JOIN users ON users.id=orders.user_id
                              WHERE orders.status='Selesai' ORDER BY orders.id DESC""").fetchall()
    return render_template("report.html", rows=rows, total=sum(r["total"] for r in rows))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
