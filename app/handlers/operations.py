# app/handlers/operations.py

import json
import os
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from app.localization import t, get_user_language

logger = logging.getLogger(__name__)


def load_operations():
    path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'operations.json')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


async def show_operations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of operations (no prices — consultation free)."""
    query = update.callback_query
    if query:
        await query.answer()
    
    chat_id = str(update.effective_user.id)
    lang = get_user_language(chat_id)
    
    operations = load_operations()
    
    if not operations:
        text = t(lang, 'no_operations')
        if query:
            await query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return
    
    lines = [f"<b>{t(lang, 'operations_title')}</b>\n"]
    
    for op in operations:
        name = op.get(f'name_{lang}', op.get('name'))
        desc = op.get(f'description_{lang}', op.get('description', ''))
        
        lines.append(f"🏥 <b>{name}</b>")
        if desc:
            lines.append(f"   <i>{desc}</i>")
        lines.append("")
    
    lines.append(f"✅ <b>{t(lang, 'consultation_free')}</b>")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📅 {t(lang, 'book_appointment')}", callback_data="book")],
        [InlineKeyboardButton(t(lang, 'btn_back_menu'), callback_data="main_menu")]
    ])
    
    text = "\n".join(lines)
    
    if query:
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode='HTML')