# app/db.py

import os
import logging
from datetime import datetime, timedelta
import pytz
from config import Config

logger = logging.getLogger(__name__)
tz = pytz.timezone(Config.TIMEZONE)

# ── Backend Detection ──
DATABASE_URL = os.getenv('DATABASE_URL')
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    # Render gives postgres:// but psycopg2 needs postgresql://
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    import psycopg2
    from psycopg2.extras import RealDictCursor
    from psycopg2.errors import UniqueViolation
    logger.info("🐘 Using PostgreSQL")
else:
    import sqlite3
    logger.info("📦 Using SQLite (local dev)")


# ── Connection Helpers ──

def get_connection():
    """Get a database connection (PostgreSQL or SQLite)."""
    if USE_POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    else:
        conn = sqlite3.connect('data.db')
        conn.row_factory = sqlite3.Row
        return conn


def _cur(conn):
    """Get a dict-returning cursor for either backend."""
    if USE_POSTGRES:
        return conn.cursor(cursor_factory=RealDictCursor)
    return conn.cursor()


def _ph(query: str) -> str:
    """Convert ? → %s for PostgreSQL. No-op for SQLite."""
    if USE_POSTGRES:
        return query.replace('?', '%s')
    return query


# ── Initialization ──

def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    cur = _cur(conn)

    if USE_POSTGRES:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id SERIAL PRIMARY KEY,
                chat_id TEXT,
                full_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                procedure TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                doctor TEXT DEFAULT 'Unassigned',
                status TEXT DEFAULT 'Scheduled',
                reminder_sent INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, time)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id TEXT PRIMARY KEY,
                language TEXT NOT NULL DEFAULT 'en'
            )
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT,
                full_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                procedure TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                doctor TEXT DEFAULT 'Unassigned',
                status TEXT DEFAULT 'Scheduled',
                reminder_sent INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, time)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id TEXT PRIMARY KEY,
                language TEXT NOT NULL DEFAULT 'en'
            )
        """)

    conn.commit()
    cur.close()
    conn.close()
    logger.info("✅ Database initialized")


# ── User Language ──

def save_user_language(chat_id: str, lang: str):
    """Save or update user language preference."""
    conn = get_connection()
    cur = _cur(conn)
    try:
        if USE_POSTGRES:
            cur.execute(
                """INSERT INTO users (chat_id, language) VALUES (%s, %s)
                   ON CONFLICT (chat_id) DO UPDATE SET language = EXCLUDED.language""",
                (str(chat_id), lang)
            )
        else:
            cur.execute(
                "INSERT OR REPLACE INTO users (chat_id, language) VALUES (?, ?)",
                (str(chat_id), lang)
            )
        conn.commit()
    except Exception as e:
        logger.error(f"❌ save_user_language failed: {e}")
    finally:
        cur.close()
        conn.close()


def get_user_language_db(chat_id: str) -> str:
    """Get user's saved language."""
    conn = get_connection()
    cur = _cur(conn)
    try:
        cur.execute(
            _ph("SELECT language FROM users WHERE chat_id = ?"),
            (str(chat_id),)
        )
        row = cur.fetchone()
        return row['language'] if row else 'en'
    except Exception as e:
        logger.error(f"❌ get_user_language_db failed: {e}")
        return 'en'
    finally:
        cur.close()
        conn.close()


# ── Appointments ──

def create_appointment(full_name, phone, procedure, date, time, chat_id=None):
    """Create new appointment. Returns ID or None if slot taken."""
    conn = get_connection()
    cur = _cur(conn)
    try:
        # Final check: is slot still free?
        cur.execute(
            _ph("SELECT id FROM appointments WHERE date = ? AND time = ? AND status != 'Cancelled'"),
            (date, time)
        )
        if cur.fetchone():
            logger.warning(f"⚠️ Slot taken: {date} {time}")
            return None

        if USE_POSTGRES:
            cur.execute(
                """INSERT INTO appointments (chat_id, full_name, phone, procedure, date, time)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (str(chat_id) if chat_id else None, full_name, phone, procedure, date, time)
            )
            appointment_id = cur.fetchone()['id']
        else:
            cur.execute(
                """INSERT INTO appointments (chat_id, full_name, phone, procedure, date, time)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (str(chat_id) if chat_id else None, full_name, phone, procedure, date, time)
            )
            appointment_id = cur.lastrowid

        conn.commit()
        logger.info(f"✅ Appointment #{appointment_id} created: {full_name} on {date} at {time}")
        return appointment_id

    except Exception as e:
        if USE_POSTGRES and isinstance(e, UniqueViolation):
            logger.error(f"❌ Integrity: Slot {date} {time} already exists.")
            return None
        elif not USE_POSTGRES and isinstance(e, sqlite3.IntegrityError):
            logger.error(f"❌ Integrity: Slot {date} {time} already exists.")
            return None
        logger.error(f"❌ create_appointment failed: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def get_booked_slots(date: str) -> list:
    """Get all booked time slots for a date."""
    conn = get_connection()
    cur = _cur(conn)
    try:
        cur.execute(
            _ph("SELECT time FROM appointments WHERE date = ? AND status != 'Cancelled'"),
            (date,)
        )
        return [row['time'] for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"❌ get_booked_slots failed: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def get_upcoming_appointments(minutes_ahead: int = 60) -> list:
    """Get appointments that need reminders."""
    conn = get_connection()
    cur = _cur(conn)
    try:
        now = datetime.now(tz)
        target = now + timedelta(minutes=minutes_ahead)
        target_date = target.strftime("%d-%m-%Y")
        target_time = target.strftime("%H:%M")

        cur.execute(
            _ph("""SELECT * FROM appointments
                    WHERE date = ? AND time = ?
                    AND reminder_sent = 0
                    AND status = 'Scheduled'"""),
            (target_date, target_time)
        )
        return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"❌ get_upcoming_appointments failed: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def mark_reminder_sent(appointment_id: int):
    """Mark appointment reminder as sent."""
    conn = get_connection()
    cur = _cur(conn)
    try:
        cur.execute(
            _ph("UPDATE appointments SET reminder_sent = 1 WHERE id = ?"),
            (appointment_id,)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"❌ mark_reminder_sent failed: {e}")
    finally:
        cur.close()
        conn.close()


def assign_doctor(appointment_id: int, doctor_name: str):
    """Admin assigns a doctor to an appointment."""
    conn = get_connection()
    cur = _cur(conn)
    try:
        cur.execute(
            _ph("UPDATE appointments SET doctor = ? WHERE id = ?"),
            (doctor_name, appointment_id)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"❌ assign_doctor failed: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def update_status(appointment_id: int, status: str):
    """Update appointment status."""
    conn = get_connection()
    cur = _cur(conn)
    try:
        cur.execute(
            _ph("UPDATE appointments SET status = ? WHERE id = ?"),
            (status, appointment_id)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"❌ update_status failed: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def get_todays_appointments() -> list:
    """Get all appointments for today."""
    conn = get_connection()
    cur = _cur(conn)
    try:
        today = datetime.now(tz).strftime("%d-%m-%Y")
        cur.execute(
            _ph("SELECT * FROM appointments WHERE date = ? ORDER BY time"),
            (today,)
        )
        return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"❌ get_todays_appointments failed: {e}")
        return []
    finally:
        cur.close()
        conn.close()