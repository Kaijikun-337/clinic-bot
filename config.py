import os
import json
from dotenv import load_dotenv

load_dotenv()


class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    DATABASE_URL = os.getenv('DATABASE_URL')
    GOOGLE_SHEETS_ID = os.getenv('GOOGLE_SHEETS_ID')
    TIMEZONE = 'Asia/Tashkent'
    SLOT_DURATION_MINUTES = 20
    REMINDER_HOURS_BEFORE = 1

    # Google credentials — file locally, env var on Render
    _creds_env = os.getenv('GOOGLE_CREDENTIALS_JSON')
    if _creds_env:
        # Write env var to a temp file for gspread
        _creds_path = '/tmp/credentials.json'
        with open(_creds_path, 'w') as f:
            f.write(_creds_env)
        GOOGLE_CREDENTIALS_FILE = _creds_path
    else:
        GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')

    # Parse ADMIN_IDS safely
    _admin_raw = os.getenv('ADMIN_IDS', '')
    ADMIN_IDS = []
    if _admin_raw:
        try:
            ADMIN_IDS = [int(x.strip()) for x in _admin_raw.split(',') if x.strip()]
        except ValueError:
            pass