# app/sheets.py

import os
import logging
from datetime import datetime
import pytz

from config import Config

logger = logging.getLogger(__name__)
tz = pytz.timezone(Config.TIMEZONE)

# Lazy-loaded client
_sheets_client = None
_workbook = None


def _get_client():
    """Lazy-init gspread client."""
    global _sheets_client
    if _sheets_client is not None:
        return _sheets_client

    creds_path = Config.GOOGLE_CREDENTIALS_FILE
    if not creds_path or not os.path.exists(creds_path):
        raise FileNotFoundError(
            f"Credentials file not found: {creds_path}. "
            f"Place your service account JSON in the project root."
        )

    import gspread
    _sheets_client = gspread.service_account(filename=creds_path)
    logger.info("✅ Google Sheets client initialized")
    return _sheets_client


def _get_workbook():
    """Lazy-init workbook connection."""
    global _workbook
    if _workbook is not None:
        return _workbook

    sheets_id = Config.GOOGLE_SHEETS_ID
    if not sheets_id:
        raise ValueError("GOOGLE_SHEETS_ID not set in .env")

    client = _get_client()
    _workbook = client.open_by_key(sheets_id)
    logger.info(f"✅ Google Sheets workbook opened: {sheets_id}")
    return _workbook


def _ensure_headers(sheet):
    """Make sure the sheet has headers in row 1."""
    expected = [
        "ID", "Full Name", "Phone", "Procedure",
        "Date", "Time", "Doctor", "Status",
        "Created At"
    ]

    try:
        first_row = sheet.row_values(1)
    except Exception:
        first_row = []

    # If headers already match, skip
    if first_row == expected:
        return

    # Otherwise write them
    sheet.update(range_name="A1:I1", values=[expected])
    sheet.format("A1:I1", {
        "bold": True,
        "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.6},
        "horizontalAlignment": "CENTER"
    })
    logger.info("✅ Sheet headers written")


def _get_sheet():
    """Get the 'Appointments' sheet (creates if missing)."""
    wb = _get_workbook()

    try:
        sheet = wb.worksheet("Appointments")
    except gspread.WorksheetNotFound:
        sheet = wb.add_worksheet(
            title="Appointments",
            rows=1000,
            cols=9
        )
        logger.info("✅ Created 'Appointments' worksheet")

    _ensure_headers(sheet)
    return sheet


def append_appointment(data: dict):
    """Append a single appointment row to Google Sheets."""
    sheet = _get_sheet()

    now = datetime.now(tz).strftime("%d-%m-%Y %H:%M")

    row = [
        data.get('id', ''),
        data.get('full_name', ''),  
        data.get('phone', ''),
        data.get('procedure', ''),
        data.get('date', ''),
        data.get('time', ''),
        data.get('doctor', 'Unassigned'),
        data.get('status', 'Scheduled'),
        now
    ]

    sheet.append_row(row, value_input_option="USER_ENTERED")
    logger.info(f"✅ Row appended to Google Sheets: {data.get('full_name')}")


def update_appointment_status(appointment_id: int, status: str):
    """Find a row by ID and update its Status column (H)."""
    sheet = _get_sheet()

    # Find the row with matching ID (column A)
    cell = sheet.find(str(appointment_id), in_column=1)
    if cell:
        sheet.update_cell(cell.row, 8, status)  # H = column 8
        logger.info(f"✅ Status updated in Sheets: #{appointment_id} → {status}")
    else:
        logger.warning(f"⚠️ Appointment #{appointment_id} not found in Sheets")


def update_appointment_doctor(appointment_id: int, doctor_name: str):
    """Find a row by ID and update its Doctor column (G)."""
    sheet = _get_sheet()

    cell = sheet.find(str(appointment_id), in_column=1)
    if cell:
        sheet.update_cell(cell.row, 7, doctor_name)  # G = column 7
        logger.info(f"✅ Doctor updated in Sheets: #{appointment_id} → {doctor_name}")
    else:
        logger.warning(f"⚠️ Appointment #{appointment_id} not found in Sheets")


def get_all_appointments():
    """Read all appointments from the sheet (for stats/backup)."""
    sheet = _get_sheet()
    records = sheet.get_all_records()
    return records


def reset_connection():
    """Force re-connect (useful after errors)."""
    global _sheets_client, _workbook
    _sheets_client = None
    _workbook = None