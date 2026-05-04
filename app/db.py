# app/db.py

import sqlite3
import logging
from datetime import datetime, timedelta
import pytz
from config import Config

logger = logging.getLogger(__name__)
tz = pytz.timezone(Config.TIMEZONE)


def get_connection():
    conn = sqlite3.connect('data.db')
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    
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
            -- This line prevents two appointments at the same time
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
    conn.close()
    logger.info("✅ Database initialized")


def save_user_language(chat_id: str, lang: str):
    """Save or update user language preference."""
    conn = get_connection()
    cur = conn.cursor()
    try:
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
    cur = conn.cursor()
    try:
        cur.execute("SELECT language FROM users WHERE chat_id = ?", (str(chat_id),))
        row = cur.fetchone()
        return row['language'] if row else 'en'
    except Exception as e:
        logger.error(f"❌ get_user_language_db failed: {e}")
        return 'en'
    finally:
        cur.close()
        conn.close()


def create_appointment(full_name, phone, procedure, date, time, chat_id=None):
    """Create new appointment. Returns appointment ID or None if slot is taken."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        # 1. Final check: Is this slot still free?
        cur.execute(
            "SELECT id FROM appointments WHERE date = ? AND time = ? AND status != 'Cancelled'", 
            (date, time)
        )
        if cur.fetchone():
            logger.warning(f"⚠️ Race condition blocked: {date} {time} is already booked.")
            return None

        # 2. If free, insert
        cur.execute("""
            INSERT INTO appointments (chat_id, full_name, phone, procedure, date, time)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (str(chat_id) if chat_id else None, full_name, phone, procedure, date, time))
        
        appointment_id = cur.lastrowid
        conn.commit()
        logger.info(f"✅ Appointment #{appointment_id} created: {full_name} on {date} at {time}")
        return appointment_id

    except sqlite3.IntegrityError:
        # This catches the UNIQUE constraint if the SELECT check somehow missed it
        logger.error(f"❌ Database Integrity Error: Slot {date} {time} already exists.")
        return None
    except Exception as e:
        logger.error(f"❌ create_appointment failed: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def get_booked_slots(date: str) -> list:
    """Get all booked time slots for a date."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT time FROM appointments WHERE date = ? AND status != 'Cancelled'",
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
    cur = conn.cursor()
    try:
        now = datetime.now(tz)
        target = now + timedelta(minutes=minutes_ahead)
        
        target_date = target.strftime("%d-%m-%Y")
        target_time = target.strftime("%H:%M")
        
        cur.execute("""
            SELECT * FROM appointments 
            WHERE date = ? AND time = ? 
            AND reminder_sent = 0 
            AND status = 'Scheduled'
        """, (target_date, target_time))
        
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
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE appointments SET reminder_sent = 1 WHERE id = ?",
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
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE appointments SET doctor = ? WHERE id = ?",
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
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE appointments SET status = ? WHERE id = ?",
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
    cur = conn.cursor()
    try:
        today = datetime.now(tz).strftime("%d-%m-%Y")
        cur.execute(
            "SELECT * FROM appointments WHERE date = ? ORDER BY time",
            (today,)
        )
        return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"❌ get_todays_appointments failed: {e}")
        return []
    finally:
        cur.close()
        conn.close()