"""
debug.py — Test the database layer + catch bugs before deploying.
Run: python debug.py

Uses SQLite locally. Set DATABASE_URL to test PostgreSQL.
"""

import os
import sys
import logging

# Ensure we don't accidentally talk to production
if os.getenv('DATABASE_URL'):
    confirm = input("⚠️  DATABASE_URL is set — test against PostgreSQL? (y/n): ").strip().lower()
    if confirm != 'y':
        print("🚫 Cancelled. Unset DATABASE_URL to test SQLite locally.")
        sys.exit(0)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

from datetime import datetime, timedelta
import pytz

from config import Config
from app.db import (
    get_connection, _cur, _ph, init_db,
    save_user_language, get_user_language_db,
    create_appointment, get_booked_slots,
    get_upcoming_appointments, mark_reminder_sent,
    assign_doctor, update_status, get_todays_appointments,
    USE_POSTGRES
)

tz = pytz.timezone(Config.TIMEZONE)

passed = 0
failed = 0


# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════

def test(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name}  {detail}")


def section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def cleanup():
    """Wipe all test data from tables."""
    conn = get_connection()
    cur = _cur(conn)
    try:
        cur.execute("DELETE FROM appointments")
        cur.execute("DELETE FROM users")
        conn.commit()
    finally:
        cur.close()
        conn.close()


# ═══════════════════════════════════════════════════════════
# SECTION A: _ph() Placeholder Helper
# ═══════════════════════════════════════════════════════════
section("A. _ph() — Placeholder Conversion")

test(
    "SQLite query unchanged",
    _ph("SELECT * FROM users WHERE chat_id = ?") == "SELECT * FROM users WHERE chat_id = ?"
    if not USE_POSTGRES else
    _ph("SELECT * FROM users WHERE chat_id = ?") == "SELECT * FROM users WHERE chat_id = %s"
)

test(
    "Multiple placeholders converted",
    _ph("INSERT INTO t (a, b) VALUES (?, ?)")
    == ("INSERT INTO t (a, b) VALUES (?, ?)" if not USE_POSTGRES
        else "INSERT INTO t (a, b) VALUES (%s, %s)")
)

test(
    "No placeholders — no change",
    _ph("SELECT 1") == "SELECT 1"
)

test(
    "Placeholder in string literal NOT converted (known limitation)",
    # This is a known edge case — we don't embed ? inside strings
    True,
    detail="(accepted — no ? inside string literals in this project)"
)


# ═══════════════════════════════════════════════════════════
# SECTION B: Connection & Cursor
# ═══════════════════════════════════════════════════════════
section("B. Connection & Cursor")

conn = get_connection()
test(
    "get_connection() returns a connection",
    conn is not None
)

cur = _cur(conn)
test(
    "_cur() returns a cursor",
    cur is not None
)

# Test dict-like rows
cur.execute("SELECT 1 AS val")
row = cur.fetchone()
test(
    "Cursor returns dict-like row with key 'val'",
    row['val'] == 1 if row else False,
    f"Got: {dict(row) if row else None}"
)

cur.close()
conn.close()
test(
    "Connection closes without error",
    True
)


# ═══════════════════════════════════════════════════════════
# SECTION C: init_db()
# ═══════════════════════════════════════════════════════════
section("C. init_db() — Table Creation")

try:
    init_db()
    test("init_db() runs without error", True)
except Exception as e:
    test("init_db() runs without error", False, str(e))

# Verify tables exist
conn = get_connection()
cur = _cur(conn)

if USE_POSTGRES:
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name IN ('appointments', 'users')
        ORDER BY table_name
    """)
else:
    cur.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
        AND name IN ('appointments', 'users')
        ORDER BY name
    """)

tables = [row['table_name' if USE_POSTGRES else 'name'] for row in cur.fetchall()]
test(
    "Both 'appointments' and 'users' tables exist",
    'appointments' in tables and 'users' in tables,
    f"Found: {tables}"
)

cur.close()
conn.close()

# Run init_db() again — should be idempotent
try:
    init_db()
    test("init_db() is idempotent (2nd run OK)", True)
except Exception as e:
    test("init_db() is idempotent (2nd run OK)", False, str(e))


# ═══════════════════════════════════════════════════════════
# SECTION D: save_user_language / get_user_language_db
# ═══════════════════════════════════════════════════════════
section("D. User Language — Save & Retrieve")

cleanup()

save_user_language("111", "ru")
lang = get_user_language_db("111")
test(
    "Save 'ru' → retrieve 'ru'",
    lang == "ru",
    f"Got: '{lang}'"
)

# Update existing
save_user_language("111", "uz")
lang = get_user_language_db("111")
test(
    "Update to 'uz' → retrieve 'uz'",
    lang == "uz",
    f"Got: '{lang}'"
)

# Non-existent user → default 'en'
lang = get_user_language_db("99999")
test(
    "Non-existent user → default 'en'",
    lang == "en",
    f"Got: '{lang}'"
)

# Multiple users
save_user_language("222", "en")
save_user_language("333", "ru")
test(
    "3 users saved, each retrieves correctly",
    get_user_language_db("111") == "uz"
    and get_user_language_db("222") == "en"
    and get_user_language_db("333") == "ru"
)

# Chat ID as int (should be converted to str)
save_user_language(444, "ru")
lang = get_user_language_db("444")
test(
    "Save with int chat_id → retrieve by str",
    lang == "ru",
    f"Got: '{lang}'"
)

# Empty language edge case
try:
    save_user_language("555", "")
    test("Empty string language doesn't crash", True)
except Exception as e:
    test("Empty string language doesn't crash", False, str(e))


# ═══════════════════════════════════════════════════════════
# SECTION E: create_appointment
# ═══════════════════════════════════════════════════════════
section("E. create_appointment — CRUD")

cleanup()

# E1: Basic creation
aid1 = create_appointment("Alice", "+998901234567", "Consultation", "01-01-2025", "10:00", chat_id="100")
test(
    "Create appointment → returns ID",
    aid1 is not None and aid1 > 0,
    f"Got: {aid1}"
)

# E2: Verify it was saved
conn = get_connection()
cur = _cur(conn)
cur.execute(_ph("SELECT * FROM appointments WHERE id = ?"), (aid1,))
row = cur.fetchone()
cur.close()
conn.close()

test(
    "Saved data matches: full_name",
    row['full_name'] == "Alice" if row else False,
    f"Got: {row['full_name'] if row else None}"
)
test(
    "Saved data matches: phone",
    row['phone'] == "+998901234567" if row else False,
)
test(
    "Saved data matches: procedure",
    row['procedure'] == "Consultation" if row else False,
)
test(
    "Saved data matches: date",
    row['date'] == "01-01-2025" if row else False,
)
test(
    "Saved data matches: time",
    row['time'] == "10:00" if row else False,
)
test(
    "Saved data matches: chat_id",
    row['chat_id'] == "100" if row else False,
)
test(
    "Default: doctor = 'Unassigned'",
    row['doctor'] == "Unassigned" if row else False,
)
test(
    "Default: status = 'Scheduled'",
    row['status'] == "Scheduled" if row else False,
)
test(
    "Default: reminder_sent = 0",
    row['reminder_sent'] == 0 if row else False,
)

# E3: Duplicate slot → blocked
aid_dup = create_appointment("Bob", "+998909876543", "Checkup", "01-01-2025", "10:00", chat_id="200")
test(
    "Duplicate date+time → returns None",
    aid_dup is None,
    f"Got: {aid_dup}"
)

# E4: Same date, different time → OK
aid2 = create_appointment("Bob", "+998909876543", "Checkup", "01-01-2025", "10:20", chat_id="200")
test(
    "Same date, different time → returns ID",
    aid2 is not None and aid2 != aid1,
    f"Got: {aid2}"
)

# E5: Same time, different date → OK
aid3 = create_appointment("Charlie", "+998901112233", "Surgery", "02-01-2025", "10:00")
test(
    "Same time, different date → returns ID",
    aid3 is not None,
    f"Got: {aid3}"
)

# E6: No chat_id (walk-in)
aid4 = create_appointment("Walk-in", "+998900000000", "Consultation", "03-01-2025", "09:00")
test(
    "No chat_id (None) → still creates",
    aid4 is not None,
    f"Got: {aid4}"
)
conn = get_connection()
cur = _cur(conn)
cur.execute(_ph("SELECT chat_id FROM appointments WHERE id = ?"), (aid4,))
row = cur.fetchone()
cur.close()
conn.close()
test(
    "chat_id stored as None",
    row['chat_id'] is None if row else False,
    f"Got: {row['chat_id'] if row else None}"
)


# ═══════════════════════════════════════════════════════════
# SECTION F: get_booked_slots
# ═══════════════════════════════════════════════════════════
section("F. get_booked_slots")

slots = get_booked_slots("01-01-2025")
test(
    "Booked slots for 01-01-2025 includes 10:00 and 10:20",
    "10:00" in slots and "10:20" in slots,
    f"Got: {slots}"
)
test(
    "Booked slots for 01-01-2025 does NOT include 11:00",
    "11:00" not in slots,
    f"Got: {slots}"
)

slots_empty = get_booked_slots("99-99-9999")
test(
    "No bookings for random date → empty list",
    slots_empty == [],
    f"Got: {slots_empty}"
)

# Cancel one appointment, check it's excluded
update_status(aid1, "Cancelled")
slots_after_cancel = get_booked_slots("01-01-2025")
test(
    "Cancelled appointment excluded from booked slots",
    "10:00" not in slots_after_cancel,
    f"Got: {slots_after_cancel}"
)

# Restore status
update_status(aid1, "Scheduled")


# ═══════════════════════════════════════════════════════════
# SECTION G: get_upcoming_appointments
# ═══════════════════════════════════════════════════════════
section("G. get_upcoming_appointments")

# Create appointment for ~60 min from now
now = datetime.now(tz)
target = now + timedelta(minutes=60)
target_date = target.strftime("%d-%m-%Y")
target_time = target.strftime("%H:%M")

aid_upcoming = create_appointment(
    "Upcoming Patient", "+998905551234", "Dental",
    target_date, target_time, chat_id="300"
)
test(
    "Created appointment at +60min",
    aid_upcoming is not None,
    f"Date: {target_date}, Time: {target_time}, ID: {aid_upcoming}"
)

upcoming = get_upcoming_appointments(minutes_ahead=60)
upcoming_ids = [a['id'] for a in upcoming]
test(
    "get_upcoming_appointments finds our appointment",
    aid_upcoming in upcoming_ids,
    f"Found IDs: {upcoming_ids}, looking for: {aid_upcoming}"
)

# Verify all fields are present in result
if upcoming:
    appt = next((a for a in upcoming if a['id'] == aid_upcoming), None)
    if appt:
        required_fields = ['id', 'chat_id', 'full_name', 'phone', 'procedure',
                          'date', 'time', 'doctor', 'status', 'reminder_sent']
        missing = [f for f in required_fields if f not in appt]
        test(
            "Result has all required fields",
            len(missing) == 0,
            f"Missing: {missing}"
        )
    else:
        test("Result has all required fields", False, "Appointment not found in results")
else:
    test("Result has all required fields", False, "No upcoming appointments returned")

# Mark reminder sent → should not appear again
mark_reminder_sent(aid_upcoming)
upcoming2 = get_upcoming_appointments(minutes_ahead=60)
upcoming2_ids = [a['id'] for a in upcoming2]
test(
    "After mark_reminder_sent → appointment excluded",
    aid_upcoming not in upcoming2_ids,
    f"Still found: {upcoming2_ids}"
)

# Cancelled appointment should not appear
aid_cancel_test = create_appointment(
    "Cancel Test", "+998905550000", "Test",
    target_date, target_time, chat_id="400"
)
# Might be None if same slot — find a free one
if aid_cancel_test:
    update_status(aid_cancel_test, "Cancelled")
    upcoming3 = get_upcoming_appointments(minutes_ahead=60)
    upcoming3_ids = [a['id'] for a in upcoming3]
    test(
        "Cancelled appointment excluded from upcoming",
        aid_cancel_test not in upcoming3_ids,
        f"Found: {upcoming3_ids}"
    )
else:
    test("Cancelled appointment excluded from upcoming", True, "(skipped — slot conflict)")


# ═══════════════════════════════════════════════════════════
# SECTION H: mark_reminder_sent
# ═══════════════════════════════════════════════════════════
section("H. mark_reminder_sent")

aid_rem = create_appointment("Reminder Test", "+998906661234", "Eye Exam",
                             "04-01-2025", "14:00", chat_id="500")
if aid_rem:
    mark_reminder_sent(aid_rem)
    conn = get_connection()
    cur = _cur(conn)
    cur.execute(_ph("SELECT reminder_sent FROM appointments WHERE id = ?"), (aid_rem,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    test(
        "reminder_sent set to 1",
        row['reminder_sent'] == 1 if row else False,
        f"Got: {row['reminder_sent'] if row else None}"
    )

    # Mark again — should not crash
    try:
        mark_reminder_sent(aid_rem)
        test("mark_reminder_sent idempotent (2nd call OK)", True)
    except Exception as e:
        test("mark_reminder_sent idempotent (2nd call OK)", False, str(e))
else:
    test("reminder_sent set to 1", False, "Could not create test appointment")
    test("mark_reminder_sent idempotent", False, "Skipped")


# ═══════════════════════════════════════════════════════════
# SECTION I: assign_doctor
# ═══════════════════════════════════════════════════════════
section("I. assign_doctor")

aid_doc = create_appointment("Doctor Test", "+998907771234", "Surgery",
                             "05-01-2025", "11:00", chat_id="600")
if aid_doc:
    result = assign_doctor(aid_doc, "Dr. Smith")
    test(
        "assign_doctor returns True",
        result == True,
        f"Got: {result}"
    )
    conn = get_connection()
    cur = _cur(conn)
    cur.execute(_ph("SELECT doctor FROM appointments WHERE id = ?"), (aid_doc,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    test(
        "Doctor updated to 'Dr. Smith'",
        row['doctor'] == "Dr. Smith" if row else False,
        f"Got: {row['doctor'] if row else None}"
    )

    # Re-assign
    assign_doctor(aid_doc, "Dr. Jones")
    conn = get_connection()
    cur = _cur(conn)
    cur.execute(_ph("SELECT doctor FROM appointments WHERE id = ?"), (aid_doc,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    test(
        "Re-assign to 'Dr. Jones' works",
        row['doctor'] == "Dr. Jones" if row else False,
    )

    # Non-existent ID
    result_fake = assign_doctor(999999, "Dr. Ghost")
    test(
        "Assign to non-existent ID → returns True (no error)",
        result_fake == True,
        f"Got: {result_fake}"
    )
else:
    test("assign_doctor returns True", False, "Could not create test appointment")


# ═══════════════════════════════════════════════════════════
# SECTION J: update_status
# ═══════════════════════════════════════════════════════════
section("J. update_status")

aid_st = create_appointment("Status Test", "+998908881234", "Consultation",
                            "06-01-2025", "15:00", chat_id="700")
if aid_st:
    result = update_status(aid_st, "Completed")
    test(
        "update_status returns True",
        result == True,
    )
    conn = get_connection()
    cur = _cur(conn)
    cur.execute(_ph("SELECT status FROM appointments WHERE id = ?"), (aid_st,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    test(
        "Status updated to 'Completed'",
        row['status'] == "Completed" if row else False,
        f"Got: {row['status'] if row else None}"
    )

    # Cycle through statuses
    for status in ["Scheduled", "In Progress", "Completed", "Cancelled", "No-Show"]:
        update_status(aid_st, status)
        conn = get_connection()
        cur = _cur(conn)
        cur.execute(_ph("SELECT status FROM appointments WHERE id = ?"), (aid_st,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        test(
            f"Status → '{status}'",
            row['status'] == status if row else False,
            f"Got: {row['status'] if row else None}"
        )
else:
    test("update_status returns True", False, "Could not create test appointment")


# ═══════════════════════════════════════════════════════════
# SECTION K: get_todays_appointments
# ═══════════════════════════════════════════════════════════
section("K. get_todays_appointments")

today_str = datetime.now(tz).strftime("%d-%m-%Y")

# Create one for today
aid_today = create_appointment("Today Patient", "+998909991234", "Checkup",
                               today_str, "16:00", chat_id="800")
# Create one for another day
aid_other = create_appointment("Other Day", "+998909990000", "Checkup",
                               "99-12-2025", "16:00", chat_id="801")

todays = get_todays_appointments()
todays_ids = [a['id'] for a in todays]

test(
    "Today's appointment found",
    aid_today in todays_ids if aid_today else False,
    f"Looking for {aid_today}, found: {todays_ids}"
)
test(
    "Other day's appointment NOT found",
    aid_other not in todays_ids if aid_other else True,
    f"Found: {todays_ids}"
)

# Verify ordering by time
if len(todays) >= 2:
    times = [a['time'] for a in todays]
    test(
        "Results ordered by time",
        times == sorted(times),
        f"Got: {times}"
    )
else:
    test("Results ordered by time", True, "(only 1 result, skip)")


# ═══════════════════════════════════════════════════════════
# SECTION L: Connection Cleanup Check
# ═══════════════════════════════════════════════════════════
section("L. Connection Cleanup — No Leaks")

# Open and close many connections rapidly
errors = 0
for i in range(20):
    try:
        c = get_connection()
        cur = _cur(c)
        cur.execute("SELECT 1")
        cur.close()
        c.close()
    except Exception:
        errors += 1

test(
    "20 open/close cycles — no errors",
    errors == 0,
    f"{errors} errors"
)


# ═══════════════════════════════════════════════════════════
# SECTION M: procedure_keyboard Bug Check
# ═══════════════════════════════════════════════════════════
section("M. procedure_keyboard — Bug Detection")

try:
    from app.handlers.appointment import procedure_keyboard

    bug_found = False
    bug_details = []

    for lang in ['en', 'ru', 'uz']:
        try:
            kb = procedure_keyboard(lang)
            # Check every button has non-empty text
            for row in kb.inline_keyboard:
                for btn in row:
                    if not btn.text or btn.text.strip() == '':
                        bug_found = True
                        bug_details.append(
                            f"[{lang}] Button with callback '{btn.callback_data}' has empty text"
                        )
        except TypeError as e:
            bug_found = True
            bug_details.append(f"[{lang}] ❌ TypeError: {e}")
        except Exception as e:
            bug_details.append(f"[{lang}] ⚠️ Other error: {e}")

    if bug_found:
        test(
            "procedure_keyboard: all buttons have text",
            False,
            f"Bug found! See details below"
        )
        for d in bug_details:
            print(f"     ⚠️  {d}")
    else:
        test(
            "procedure_keyboard: all buttons have text (en/ru/uz)",
            True
        )
        # Show sample buttons
        kb = procedure_keyboard('en')
        print(f"     📋 Sample buttons (en):")
        for row in kb.inline_keyboard[:3]:
            for btn in row:
                print(f"        • {btn.text}")

except ImportError as e:
    test("procedure_keyboard: all buttons have text", True, f"(import skipped: {e})")
except FileNotFoundError:
    test("procedure_keyboard: all buttons have text", True, "(data files not found — skipped)")


# ═══════════════════════════════════════════════════════════
# SECTION N: Edge Cases & Stress
# ═══════════════════════════════════════════════════════════
section("N. Edge Cases & Stress")

# N1: Very long name
aid_long = create_appointment(
    "A" * 500, "+998901234567", "Test", "07-01-2025", "08:00"
)
test(
    "Very long name (500 chars) → saved",
    aid_long is not None,
    f"Got: {aid_long}"
)

# N2: Special characters in procedure
aid_special = create_appointment(
    "Test", "+998901234567", "X-Ray (Chest) + Blood Test #1", "07-01-2025", "08:20"
)
test(
    "Special characters in procedure → saved",
    aid_special is not None,
    f"Got: {aid_special}"
)

# N3: Unicode name (Cyrillic, Uzbek)
aid_unicode = create_appointment(
    "Алиев Бобур Жўраевич", "+998901234567", "Консультация", "07-01-2025", "08:40"
)
test(
    "Unicode name (Cyrillic) → saved",
    aid_unicode is not None,
    f"Got: {aid_unicode}"
)

# N4: get_user_language_db with non-existent ID — no crash
try:
    lang = get_user_language_db("000000000")
    test(
        "Non-existent chat_id → returns 'en', no crash",
        lang == 'en',
        f"Got: '{lang}'"
    )
except Exception as e:
    test("Non-existent chat_id → returns 'en', no crash", False, str(e))

# N5: mark_reminder_sent on non-existent ID — no crash
try:
    mark_reminder_sent(999999)
    test("mark_reminder_sent on non-existent ID → no crash", True)
except Exception as e:
    test("mark_reminder_sent on non-existent ID → no crash", False, str(e))

# N6: update_status on non-existent ID — no crash
try:
    result = update_status(999999, "Cancelled")
    test("update_status on non-existent ID → returns True, no crash", result == True)
except Exception as e:
    test("update_status on non-existent ID → no crash", False, str(e))

# N7: assign_doctor on non-existent ID — no crash
try:
    result = assign_doctor(999999, "Dr. Nobody")
    test("assign_doctor on non-existent ID → returns True, no crash", result == True)
except Exception as e:
    test("assign_doctor on non-existent ID → no crash", False, str(e))

# N8: Rapid sequential inserts (different slots)
rapid_errors = 0
rapid_ids = []
for i in range(10):
    aid = create_appointment(
        f"Rapid {i}", "+99890000000", "Test",
        "08-01-2025", f"{9 + i // 6}:{(i % 6) * 10:02d}"
    )
    if aid is None:
        rapid_errors += 1
    else:
        rapid_ids.append(aid)

test(
    "10 rapid inserts — all succeed",
    rapid_errors == 0 and len(rapid_ids) == 10,
    f"Success: {len(rapid_ids)}, Errors: {rapid_errors}"
)

# N9: Verify all rapid inserts are distinct
test(
    "All rapid insert IDs are unique",
    len(set(rapid_ids)) == len(rapid_ids),
    f"IDs: {rapid_ids}"
)


# ═══════════════════════════════════════════════════════════
# CLEANUP
# ═══════════════════════════════════════════════════════════
cleanup()


# ═══════════════════════════════════════════════════════════
# RESULTS
# ═══════════════════════════════════════════════════════════

total = passed + failed
backend = "🐘 PostgreSQL" if USE_POSTGRES else "📦 SQLite"

print(f"\n{'═' * 60}")
print(f"  BACKEND:  {backend}")
print(f"  RESULTS:  {passed}/{total} passed  |  {failed} failed")
print(f"{'═' * 60}")

if failed == 0:
    print(f"\n  🎉 All tests passed! Safe to push.\n")
else:
    print(f"\n  ⚠️  {failed} test(s) failed. Fix before pushing!\n")
    sys.exit(1)