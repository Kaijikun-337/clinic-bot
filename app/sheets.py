# app/sheets.py

import os
import logging
import gspread
from datetime import datetime
import pytz

from config import Config

logger = logging.getLogger(__name__)
tz = pytz.timezone(Config.TIMEZONE)

# Lazy-loaded client
_sheets_client = None
_workbook = None

# ── Russian translations for sheets ──
HEADERS_RU = [
    "ID", "ФИО", "Телефон", "Процедура",
    "Дата", "Время", "Врач", "Статус",
    "Создано"
]

STATUS_RU = {
    'Scheduled': 'Запланировано',
    'Cancelled': 'Отменено',
    'Completed': 'Завершено',
    'In Progress': 'В процессе',
    'No-Show': 'Не явился',
}

DOCTOR_RU = {
    'Unassigned': 'Не назначен',
}


def _translate_status(status: str) -> str:
    return STATUS_RU.get(status, status)


def _translate_doctor(doctor: str) -> str:
    return DOCTOR_RU.get(doctor, doctor)


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
    """Make sure the sheet has Russian headers in row 1."""
    try:
        first_row = sheet.row_values(1)
    except Exception:
        first_row = []

    if first_row == HEADERS_RU:
        return

    sheet.update(range_name="A1:I1", values=[HEADERS_RU])
    sheet.format("A1:I1", {
        "textFormat": {"bold": True},
        "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.6},
        "horizontalAlignment": "CENTER"
    })
    logger.info("✅ Sheet headers written (Russian)")


def _get_sheet():
    """Get the 'Записи' sheet (creates if missing)."""
    wb = _get_workbook()

    try:
        sheet = wb.worksheet("Записи")
    except gspread.WorksheetNotFound:
        sheet = wb.add_worksheet(
            title="Записи",
            rows=1000,
            cols=9
        )
        logger.info("✅ Created 'Записи' worksheet")

    _ensure_headers(sheet)
    return sheet


def append_appointment(data: dict):
    """Append a single appointment row to Google Sheets (Russian)."""
    sheet = _get_sheet()

    now = datetime.now(tz).strftime("%d-%m-%Y %H:%M")

    row = [
        data.get('id', ''),
        data.get('full_name', ''),
        data.get('phone', ''),
        data.get('procedure', ''),
        data.get('date', ''),
        data.get('time', ''),
        _translate_doctor(data.get('doctor', 'Unassigned')),
        _translate_status(data.get('status', 'Scheduled')),
        now
    ]

    sheet.append_row(row, value_input_option="USER_ENTERED")
    logger.info(f"✅ Row appended to Google Sheets: {data.get('full_name')}")


def update_appointment_status(appointment_id: int, status: str):
    """Find a row by ID and update its Status column (H) in Russian."""
    sheet = _get_sheet()

    cell = sheet.find(str(appointment_id), in_column=1)
    if cell:
        sheet.update_cell(cell.row, 8, _translate_status(status))
        logger.info(f"✅ Status updated in Sheets: #{appointment_id} → {_translate_status(status)}")
    else:
        logger.warning(f"⚠️ Appointment #{appointment_id} not found in Sheets")


def update_appointment_doctor(appointment_id: int, doctor_name: str):
    """Find a row by ID and update its Doctor column (G)."""
    sheet = _get_sheet()

    cell = sheet.find(str(appointment_id), in_column=1)
    if cell:
        sheet.update_cell(cell.row, 7, _translate_doctor(doctor_name))
        logger.info(f"✅ Doctor updated in Sheets: #{appointment_id} → {_translate_doctor(doctor_name)}")
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