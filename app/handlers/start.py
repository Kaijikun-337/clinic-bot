# app/handlers/start.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.localization import get_user_language, t
from app.db import save_user_language


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start — auto-detect language, show language picker."""
    chat_id = str(update.effective_user.id)
    
    # Auto-detect language
    lang = 'en'
    if update.effective_user.language_code:
        code = update.effective_user.language_code[:2]
        if code in ['ru', 'uz']:
            lang = code
    
    # Save detected language
    save_user_language(chat_id, lang)
    
    keyboard = [
        [
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
            InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang_uz")
        ]
    ]
    
    await update.message.reply_text(
        t(lang, 'welcome') + "\n\n" + t(lang, 'select_language'),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language selection, show main menu."""
    query = update.callback_query
    await query.answer()
    
    chat_id = str(update.effective_user.id)
    lang = query.data.replace('lang_', '')
    
    save_user_language(chat_id, lang)
    
    await query.edit_message_text(
        t(lang, 'language_changed'),
        parse_mode='HTML'
    )
    
    await show_main_menu(query, chat_id, lang)


async def show_main_menu(query_or_message, chat_id: str, lang: str):
    """Show the main menu buttons."""
    keyboard = [
        [InlineKeyboardButton(f"📅 {t(lang, 'book_appointment')}", callback_data="book")],
        [InlineKeyboardButton(f"💊 {t(lang, 'view_services')}", callback_data="services")],
        [InlineKeyboardButton(f"🏥 {t(lang, 'view_operations')}", callback_data="operations")],
        [InlineKeyboardButton(f"🌐 {t(lang, 'change_language')}", callback_data="change_lang")]
    ]
    
    # Send as new message (not edit) so menu persists
    bot = query_or_message._bot if hasattr(query_or_message, '_bot') else query_or_message.get_bot()
    
    await bot.send_message(
        chat_id=chat_id,
        text=t(lang, 'main_menu'),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to main menu."""
    query = update.callback_query
    await query.answer()
    
    chat_id = str(update.effective_user.id)
    lang = get_user_language(chat_id)
    
    keyboard = [
        [InlineKeyboardButton(f"📅 {t(lang, 'book_appointment')}", callback_data="book")],
        [InlineKeyboardButton(f"💊 {t(lang, 'view_services')}", callback_data="services")],
        [InlineKeyboardButton(f"🏥 {t(lang, 'view_operations')}", callback_data="operations")],
        [InlineKeyboardButton(f"🌐 {t(lang, 'change_language')}", callback_data="change_lang")]
    ]
    
    await query.edit_message_text(
        t(lang, 'main_menu'),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )