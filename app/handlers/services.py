# app/handlers/services.py

import json
import os
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from app.localization import t, get_user_language

logger = logging.getLogger(__name__)


def load_services():
    path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'services.json')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


async def show_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of services with prices."""
    query = update.callback_query
    if query:
        await query.answer()
    
    chat_id = str(update.effective_user.id)
    lang = get_user_language(chat_id)
    
    services = load_services()
    
    if not services:
        text = t(lang, 'no_services')
        if query:
            await query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return
    
    lines = [f"<b>{t(lang, 'services_title')}</b>\n"]
    
    for svc in services:
        name = svc.get(f'name_{lang}', svc.get('name'))
        desc = svc.get(f'description_{lang}', svc.get('description', ''))
        
        if desc:
            lines.append(f"   <i>{desc}</i>")
        lines.append("")
    
    # Back to menu button
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📅 {t(lang, 'book_appointment')}", callback_data="book")],
        [InlineKeyboardButton(t(lang, 'btn_back_menu'), callback_data="main_menu")]
    ])
    
    text = "\n".join(lines)
    
    if query:
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode='HTML')