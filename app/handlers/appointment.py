import logging
from datetime import datetime, timedelta
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

from config import Config
from app.localization import t, get_user_language
from app.db import create_appointment, get_booked_slots

logger = logging.getLogger(__name__)

# Conversation states
ASK_NAME, ASK_PHONE, ASK_PROCEDURE, ASK_DATE, ASK_TIME, CONFIRM = range(6)

tz = pytz.timezone(Config.TIMEZONE)


# ═══════════════════════════════════════════════════════════
# HELPER: Generate available dates (next 7 days)
# ═══════════════════════════════════════════════════════════

def get_available_dates():
    """Generate next 7 days as selectable dates."""
    now = datetime.now(tz)
    dates = []
    
    for i in range(7):
        day = now + timedelta(days=i)
        dates.append({
            'date': day.strftime("%d-%m-%Y"),
            'display': day.strftime("%A %d %B"),
            'day_name': day.strftime("%A")
        })
    
    return dates


def get_available_times(date_str: str):
    """Generate 20-min slots for a given date, minus booked ones."""
    slot_duration = Config.SLOT_DURATION_MINUTES
    
    # Parse the date
    day = datetime.strptime(date_str, "%d-%m-%Y")
    day = tz.localize(day)
    now = datetime.now(tz)
    
    # Working hours: 24/7 means 08:00 - 22:00 (reasonable clinic hours)
    start_hour = 8
    end_hour = 22
    
    # Get already booked slots
    booked = get_booked_slots(date_str)
    
    slots = []
    current = day.replace(hour=start_hour, minute=0, second=0)
    end = day.replace(hour=end_hour, minute=0, second=0)
    
    while current < end:
        time_str = current.strftime("%H:%M")
        
        # Skip past times if today
        if day.date() == now.date() and current <= now:
            current += timedelta(minutes=slot_duration)
            continue
        
        # Skip booked slots
        if time_str not in booked:
            slots.append(time_str)
        
        current += timedelta(minutes=slot_duration)
    
    return slots


# ═══════════════════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════════════════

def dates_keyboard(dates: list, lang: str):
    """Date selection keyboard."""
    buttons = []
    for d in dates:
        buttons.append([
            InlineKeyboardButton(
                f"📅 {d['display']}",
                callback_data=f"apt_date_{d['date']}"
            )
        ])
    buttons.append([
        InlineKeyboardButton(t(lang, 'btn_cancel'), callback_data="apt_cancel")
    ])
    return InlineKeyboardMarkup(buttons)


def times_keyboard(times: list, lang: str):
    """Time selection keyboard (3 per row)."""
    buttons = []
    row = []
    for time_str in times:
        row.append(
            InlineKeyboardButton(time_str, callback_data=f"apt_time_{time_str}")
        )
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    buttons.append([
        InlineKeyboardButton(t(lang, 'btn_back'), callback_data="apt_back_to_dates")
    ])
    buttons.append([
        InlineKeyboardButton(t(lang, 'btn_cancel'), callback_data="apt_cancel")
    ])
    return InlineKeyboardMarkup(buttons)


def procedure_keyboard(lang: str):
    """Let user choose between service or operation."""
    import json, os
    
    buttons = []
    
    # Load services
    services_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'services.json')
    with open(services_path, 'r', encoding='utf-8') as f:
        services = json.load(f)
    
    # Load operations
    ops_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'operations.json')
    with open(ops_path, 'r', encoding='utf-8') as f:
        operations = json.load(f)
    
    for svc in services:
        name = svc.get(f'name_{lang}', svc.get('name'))
        buttons.append([
            InlineKeyboardButton(
                f"💊 {name}",
                callback_data=f"apt_proc_svc_{svc['name']}"
            )
        ])
    
    # Operations (consultation free)
    for op in operations:
        name = op.get(f'name_{lang}', op.get('name'))
        buttons.append([
            InlineKeyboardButton(
                f"🏥 {name}",
                callback_data=f"apt_proc_op_{op['name']}"
            )
        ])
    
    # Consultation option
    buttons.append([
        InlineKeyboardButton(
            f"🩺 {t(lang, 'consultation')}",
            callback_data="apt_proc_consultation"
        )
    ])
    
    buttons.append([
        InlineKeyboardButton(t(lang, 'btn_cancel'), callback_data="apt_cancel")
    ])
    
    return InlineKeyboardMarkup(buttons)


def confirm_keyboard(lang: str):
    """Confirm or cancel booking."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✅ {t(lang, 'btn_confirm')}", callback_data="apt_confirm")],
        [InlineKeyboardButton(f"❌ {t(lang, 'btn_cancel')}", callback_data="apt_cancel")]
    ])


# ═══════════════════════════════════════════════════════════
# CONVERSATION HANDLERS
# ═══════════════════════════════════════════════════════════

async def start_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point: Ask for full name."""
    query = update.callback_query
    if query:
        await query.answer()
        chat_id = str(update.effective_user.id)
        lang = get_user_language(chat_id)
        
        context.user_data['booking'] = {'chat_id': chat_id}
        
        await query.edit_message_text(
            t(lang, 'ask_name'),
            parse_mode='HTML'
        )
    else:
        chat_id = str(update.effective_user.id)
        lang = get_user_language(chat_id)
        
        context.user_data['booking'] = {'chat_id': chat_id}
        
        await update.message.reply_text(
            t(lang, 'ask_name'),
            parse_mode='HTML'
        )
    
    return ASK_NAME


async def name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Got name, ask for phone."""
    chat_id = str(update.effective_user.id)
    lang = get_user_language(chat_id)
    
    name = update.message.text.strip()
    
    if len(name) < 2:
        await update.message.reply_text(t(lang, 'name_too_short'))
        return ASK_NAME
    
    context.user_data['booking']['name'] = name
    
    await update.message.reply_text(
        t(lang, 'ask_phone'),
        parse_mode='HTML'
    )
    
    return ASK_PHONE


async def phone_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Got phone, ask for procedure."""
    chat_id = str(update.effective_user.id)
    lang = get_user_language(chat_id)
    
    phone = update.message.text.strip()
    
    # Basic phone validation
    clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if not clean_phone.isdigit() or len(clean_phone) < 9:
        await update.message.reply_text(t(lang, 'invalid_phone'))
        return ASK_PHONE
    
    context.user_data['booking']['phone'] = phone
    
    await update.message.reply_text(
        t(lang, 'ask_procedure'),
        reply_markup=procedure_keyboard(lang),
        parse_mode='HTML'
    )
    
    return ASK_PROCEDURE


async def procedure_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Got procedure, ask for date."""
    query = update.callback_query
    await query.answer()
    
    chat_id = str(update.effective_user.id)
    lang = get_user_language(chat_id)
    
    data = query.data
    
    if data == "apt_proc_consultation":
        procedure = "Consultation"
    elif data.startswith("apt_proc_svc_"):
        procedure = data.replace("apt_proc_svc_", "")
    elif data.startswith("apt_proc_op_"):
        procedure = data.replace("apt_proc_op_", "")
    else:
        procedure = "General"
    
    context.user_data['booking']['procedure'] = procedure
    
    dates = get_available_dates()
    
    await query.edit_message_text(
        t(lang, 'ask_date'),
        reply_markup=dates_keyboard(dates, lang),
        parse_mode='HTML'
    )
    
    return ASK_DATE


async def date_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Got date, ask for time."""
    query = update.callback_query
    await query.answer()
    
    chat_id = str(update.effective_user.id)
    lang = get_user_language(chat_id)
    
    if query.data == "apt_back_to_dates":
        dates = get_available_dates()
        await query.edit_message_text(
            t(lang, 'ask_date'),
            reply_markup=dates_keyboard(dates, lang),
            parse_mode='HTML'
        )
        return ASK_DATE
    
    date_str = query.data.replace("apt_date_", "")
    context.user_data['booking']['date'] = date_str
    
    times = get_available_times(date_str)
    
    if not times:
        await query.edit_message_text(
            t(lang, 'no_slots_available'),
            reply_markup=dates_keyboard(get_available_dates(), lang),
            parse_mode='HTML'
        )
        return ASK_DATE
    
    await query.edit_message_text(
        t(lang, 'ask_time'),
        reply_markup=times_keyboard(times, lang),
        parse_mode='HTML'
    )
    
    return ASK_TIME


async def time_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Got time, show confirmation."""
    query = update.callback_query
    await query.answer()
    
    chat_id = str(update.effective_user.id)
    lang = get_user_language(chat_id)
    
    if query.data == "apt_back_to_dates":
        dates = get_available_dates()
        await query.edit_message_text(
            t(lang, 'ask_date'),
            reply_markup=dates_keyboard(dates, lang),
            parse_mode='HTML'
        )
        return ASK_DATE
    
    time_str = query.data.replace("apt_time_", "")
    context.user_data['booking']['time'] = time_str
    
    booking = context.user_data['booking']
    
    summary = (
        f"📋 <b>{t(lang, 'booking_summary')}</b>\n\n"
        f"👤 {t(lang, 'field_name')}: <b>{booking['name']}</b>\n"
        f"📞 {t(lang, 'field_phone')}: <b>{booking['phone']}</b>\n"
        f"🏥 {t(lang, 'field_procedure')}: <b>{booking['procedure']}</b>\n"
        f"📅 {t(lang, 'field_date')}: <b>{booking['date']}</b>\n"
        f"🕐 {t(lang, 'field_time')}: <b>{booking['time']}</b>\n\n"
        f"{t(lang, 'confirm_booking_prompt')}"
    )
    
    await query.edit_message_text(
        summary,
        reply_markup=confirm_keyboard(lang),
        parse_mode='HTML'
    )
    
    return CONFIRM


async def booking_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save booking to DB and Google Sheets, notify admin."""
    query = update.callback_query
    await query.answer()
    
    chat_id = str(update.effective_user.id)
    lang = get_user_language(chat_id)
    
    booking = context.user_data.get('booking', {})
    
    # 1. Save to SQLite
    appointment_id = create_appointment(
        full_name=booking['name'],
        phone=booking['phone'],
        procedure=booking['procedure'],
        date=booking['date'],
        time=booking['time']
    )
    
    if not appointment_id:
        await query.edit_message_text(t(lang, 'booking_error'))
        return ConversationHandler.END
    
    # 2. Save to Google Sheets
    try:
        from app.sheets import append_appointment
        append_appointment({
            'full_name': booking['name'],
            'procedure': booking['procedure'],
            'doctor': 'Unassigned',
            'phone': booking['phone'],
            'status': 'Scheduled',
            'date': booking['date'],
            'time': booking['time']
        })
        logger.info(f"✅ Appointment saved to Google Sheets")
    except Exception as e:
        logger.error(f"⚠️ Google Sheets failed (appointment still saved locally): {e}")
    
    # 3. Notify admins
    admin_msg = t('en', 'admin_new_booking').format(
        name=booking['name'],
        phone=booking['phone'],
        procedure=booking['procedure'],
        date=booking['date'],
        time=booking['time']
    )
    
    for admin_id in Config.ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_msg,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    # 4. Confirm to patient
    await query.edit_message_text(
        t(lang, 'booking_confirmed'),
        parse_mode='HTML'
    )
    
    # Cleanup
    context.user_data.pop('booking', None)
    
    return ConversationHandler.END


async def cancel_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel booking flow."""
    query = update.callback_query
    if query:
        await query.answer()
        chat_id = str(update.effective_user.id)
        lang = get_user_language(chat_id)
        await query.edit_message_text(t(lang, 'booking_cancelled'))
    else:
        chat_id = str(update.effective_user.id)
        lang = get_user_language(chat_id)
        await update.message.reply_text(t(lang, 'booking_cancelled'))
    
    context.user_data.pop('booking', None)
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════
# CONVERSATION HANDLER BUILDER
# ═══════════════════════════════════════════════════════════

def get_appointment_handler():
    """Build and return the appointment ConversationHandler."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_booking, pattern='^book$'),
            CommandHandler('book', start_booking)
        ],
        states={
            ASK_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, name_received)
            ],
            ASK_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, phone_received)
            ],
            ASK_PROCEDURE: [
                CallbackQueryHandler(procedure_selected, pattern='^apt_proc_'),
                CallbackQueryHandler(cancel_booking, pattern='^apt_cancel$')
            ],
            ASK_DATE: [
                CallbackQueryHandler(date_selected, pattern='^apt_date_'),
                CallbackQueryHandler(cancel_booking, pattern='^apt_cancel$')
            ],
            ASK_TIME: [
                CallbackQueryHandler(time_selected, pattern='^apt_time_'),
                CallbackQueryHandler(date_selected, pattern='^apt_back_to_dates$'),
                CallbackQueryHandler(cancel_booking, pattern='^apt_cancel$')
            ],
            CONFIRM: [
                CallbackQueryHandler(booking_confirmed, pattern='^apt_confirm$'),
                CallbackQueryHandler(cancel_booking, pattern='^apt_cancel$')
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_booking),
            CallbackQueryHandler(cancel_booking, pattern='^apt_cancel$')
        ],
        name="appointment_booking",
        persistent=False
    )