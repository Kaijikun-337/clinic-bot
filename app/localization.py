# app/localization.py

import json
import os
import logging

logger = logging.getLogger(__name__)

strings = {}


def load_strings():
    global strings
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'strings.json')
    with open(path, 'r', encoding='utf-8') as f:
        strings = json.load(f)
    logger.info(f"✅ Loaded strings for {list(strings.keys())}")


def get_user_language(chat_id: str) -> str:
    """Get user language from DB."""
    try:
        from app.db import get_user_language_db
        return get_user_language_db(str(chat_id))
    except Exception:
        return 'en'


def t(lang: str, key: str, **kwargs) -> str:
    """Get translated text."""
    text = strings.get(lang, {}).get(key)
    
    if text is None:
        # Fallback to English
        text = strings.get('en', {}).get(key)
    
    if text is None:
        # Key not found anywhere
        return key
    
    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing format key {e} in '{key}'")
            return text
    
    return text


# Load on import
load_strings()