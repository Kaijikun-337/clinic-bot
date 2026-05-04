# app/scheduler.py

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz
from config import Config
from app.db import get_upcoming_appointments, mark_reminder_sent
from app.localization import t, get_user_language

logger = logging.getLogger(__name__)
tz = pytz.timezone(Config.TIMEZONE)


async def check_reminders(app):
    """Check for appointments needing 1-hour reminders."""
    appointments = get_upcoming_appointments(minutes_ahead=60)
    
    if not appointments:
        return
    
    logger.info(f"🔔 Found {len(appointments)} appointment(s) needing reminders")
    
    for appt in appointments:
        # Notify patient (if we have their chat_id)
        if appt.get('chat_id'):
            try:
                lang = get_user_language(appt['chat_id'])
                msg = (
                    f"🔔 <b>{t(lang, 'reminder_title')}</b>\n\n"
                    f"👤 {appt['full_name']}\n"
                    f"🏥 {appt['procedure']}\n"
                    f"📅 {appt['date']}\n"
                    f"🕐 {appt['time']}\n"
                    f"👨‍⚕️ {appt['doctor']}"
                )
                await app.bot.send_message(
                    chat_id=appt['chat_id'],
                    text=msg,
                    parse_mode='HTML'
                )
                logger.info(f"✅ Reminder sent to patient {appt['full_name']}")
            except Exception as e:
                logger.error(f"❌ Failed to remind patient: {e}")
        
        # Always notify admins
        for admin_id in Config.ADMIN_IDS:
            try:
                msg = (
                    f"🔔 <b>Upcoming Appointment (1 hour)</b>\n\n"
                    f"👤 {appt['full_name']}\n"
                    f"📞 {appt['phone']}\n"
                    f"🏥 {appt['procedure']}\n"
                    f"🕐 {appt['time']}\n"
                    f"👨‍⚕️ {appt['doctor']}"
                )
                await app.bot.send_message(
                    chat_id=admin_id,
                    text=msg,
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"❌ Failed to remind admin: {e}")
        
        mark_reminder_sent(appt['id'])


def start_scheduler(app):
    """Start the reminder scheduler."""
    scheduler = AsyncIOScheduler(timezone=tz)
    
    # Check every 5 minutes for upcoming appointments
    scheduler.add_job(
        check_reminders,
        'interval',
        minutes=5,
        args=[app],
        id='appointment_reminders',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("🚀 Clinic scheduler started")