import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import Config

logger = logging.getLogger(__name__)

SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]


def get_sheet():
    """Connect to Google Sheets."""
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            Config.GOOGLE_CREDENTIALS_FILE, SCOPE
        )
        client = gspread.authorize(creds)
        sheet = client.open_by_key(Config.GOOGLE_SHEETS_ID).sheet1
        return sheet
    except Exception as e:
        logger.error(f"❌ Google Sheets connection failed: {e}")
        return None


def append_appointment(appointment: dict):
    """Add appointment row to Google Sheet."""
    sheet = get_sheet()
    if not sheet:
        logger.warning("⚠️ Skipping Google Sheets — not connected")
        return False

    try:
        row = [
            appointment.get('full_name', ''),
            appointment.get('procedure', ''),
            appointment.get('doctor', 'Unassigned'),
            appointment.get('phone', ''),
            appointment.get('status', 'Scheduled'),
            f"{appointment.get('date', '')} {appointment.get('time', '')}"
        ]

        sheet.append_row(row)
        logger.info(f"✅ Appointment added to Google Sheets")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to append to Sheets: {e}")
        return False