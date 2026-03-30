import sqlite3
import os
import sys
import hashlib
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import DB_PATH

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_ref TEXT NOT NULL UNIQUE,
            user_id INTEGER,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            booking_type TEXT NOT NULL,
            booking_date TEXT NOT NULL,
            booking_time TEXT NOT NULL,
            status TEXT DEFAULT 'confirmed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            chat_type TEXT NOT NULL DEFAULT 'general',
            messages TEXT NOT NULL DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    _seed_users(cur, conn)
    conn.close()

def _seed_users(cur, conn):
    """Insert predefined users if they don't exist."""
    predefined = [
        ("Admin User",        "admin@gmail.com",           "Admin@123",   "admin"),
        ("Lee Khithnunna",    "leekhithnunna369@gmail.com","User@123",    "user"),
        ("Dr. Rishi",         "dr_rishi@gmail.com",        "User@123",    "user"),
        ("Sarah Johnson",     "sarah.j@gmail.com",         "User@123",    "user"),
        ("Mike Chen",         "mike.chen@gmail.com",       "User@123",    "user"),
    ]
    for name, email, pwd, role in predefined:
        cur.execute("SELECT id FROM users WHERE email=?", (email,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO users (name, email, password, role) VALUES (?,?,?,?)",
                (name, email, hash_password(pwd), role)
            )
    conn.commit()

# ── Auth ──────────────────────────────────────────────────────────────────────
def register_user(name: str, email: str, password: str, role: str = "user") -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email=?", (email,))
    if cur.fetchone():
        conn.close()
        raise ValueError("Email already registered.")
    cur.execute(
        "INSERT INTO users (name, email, password, role) VALUES (?,?,?,?)",
        (name, email, hash_password(password), role)
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return {"id": user_id, "name": name, "email": email, "role": role}

def login_user(email: str, password: str) -> dict | None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, email, role FROM users WHERE email=? AND password=?",
        (email, hash_password(password))
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

# ── Bookings ──────────────────────────────────────────────────────────────────
def _gen_booking_ref(booking_id: int) -> str:
    return f"TB-{1000 + booking_id}"

def save_booking(name: str, email: str, phone: str,
                 booking_type: str, booking_date: str, booking_time: str,
                 user_id: int | None = None) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    # Temp insert to get id, then update ref
    cur.execute(
        """INSERT INTO bookings (booking_ref, user_id, name, email, phone,
           booking_type, booking_date, booking_time)
           VALUES (?,?,?,?,?,?,?,?)""",
        ("TEMP", user_id, name, email, phone, booking_type, booking_date, booking_time)
    )
    booking_id = cur.lastrowid
    ref = _gen_booking_ref(booking_id)
    cur.execute("UPDATE bookings SET booking_ref=? WHERE id=?", (ref, booking_id))
    conn.commit()
    conn.close()
    return {"booking_id": booking_id, "booking_ref": ref}

def get_all_bookings():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id as booking_id, booking_ref, name, email, phone,
               booking_type, booking_date, booking_time, status, created_at
        FROM bookings ORDER BY created_at DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_user_bookings(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id as booking_id, booking_ref, name, email, phone,
               booking_type, booking_date, booking_time, status, created_at
        FROM bookings WHERE user_id=? ORDER BY created_at DESC
    """, (user_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def update_booking(booking_id: int, booking_type: str, booking_date: str,
                   booking_time: str, status: str) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE bookings SET booking_type=?, booking_date=?, booking_time=?, status=? WHERE id=?",
        (booking_type, booking_date, booking_time, status, booking_id)
    )
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated

def get_booking_stats():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as total FROM bookings")
    total = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as c FROM bookings WHERE status='confirmed'")
    confirmed = cur.fetchone()["c"]
    cur.execute("SELECT booking_type, COUNT(*) as c FROM bookings GROUP BY booking_type ORDER BY c DESC")
    by_type = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"total": total, "confirmed": confirmed, "by_type": by_type}

# ── Chat Sessions ─────────────────────────────────────────────────────────────
import json as _json

def create_chat_session(user_id: int, title: str, chat_type: str = "general") -> int:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "INSERT INTO chat_sessions (user_id, title, chat_type, messages) VALUES (?,?,?,?)",
        (user_id, title, chat_type, "[]")
    )
    sid = cur.lastrowid
    conn.commit(); conn.close()
    return sid

def save_chat_session(session_id: int, messages: list, title: str | None = None):
    conn = get_connection()
    cur  = conn.cursor()
    if title:
        cur.execute(
            "UPDATE chat_sessions SET messages=?, title=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (_json.dumps(messages), title, session_id)
        )
    else:
        cur.execute(
            "UPDATE chat_sessions SET messages=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (_json.dumps(messages), session_id)
        )
    conn.commit(); conn.close()

def get_chat_sessions(user_id: int, chat_type: str = "general") -> list:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "SELECT id, title, chat_type, updated_at FROM chat_sessions WHERE user_id=? AND chat_type=? ORDER BY updated_at DESC",
        (user_id, chat_type)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def load_chat_session(session_id: int) -> list:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT messages FROM chat_sessions WHERE id=?", (session_id,))
    row = cur.fetchone()
    conn.close()
    return _json.loads(row["messages"]) if row else []

def delete_chat_session(session_id: int):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("DELETE FROM chat_sessions WHERE id=?", (session_id,))
    conn.commit(); conn.close()

def update_smtp_settings(host: str, port: int, user: str, password: str):
    """Store SMTP settings in DB so they persist across restarts."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    for k, v in [("smtp_host", host), ("smtp_port", str(port)),
                 ("smtp_user", user), ("smtp_password", password)]:
        cur.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?,?)", (k, v))
    conn.commit(); conn.close()

def get_smtp_settings() -> dict:
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT key, value FROM app_settings WHERE key LIKE 'smtp_%'")
        rows = {r["key"]: r["value"] for r in cur.fetchall()}
    except Exception:
        rows = {}
    conn.close()
    return rows
