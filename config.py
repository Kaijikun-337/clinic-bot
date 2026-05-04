import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    #GOOGLE_SHEETS_ID = os.getenv('GOOGLE_SHEETS_ID')
    #GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')
    TIMEZONE = 'Asia/Tashkent'
    SLOT_DURATION_MINUTES = 20
    REMINDER_HOURS_BEFORE = 1

    # Parse ADMIN_IDS safely
    _admin_raw = os.getenv('ADMIN_IDS', '')
    ADMIN_IDS = []
    if _admin_raw:
        try:
            ADMIN_IDS = [int(x.strip()) for x in _admin_raw.split(',') if x.strip()]
        except ValueError:
            pass