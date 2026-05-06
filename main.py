import logging
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler
)
import httpx

from config import Config
from app.db import init_db
from app.scheduler import start_scheduler
from app.handlers.start import start, language_callback, main_menu_callback
from app.handlers.appointment import get_appointment_handler
from app.handlers.services import show_services
from app.handlers.operations import show_operations
from app.keep_alive import start_keep_alive

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    # Initialize
    init_db()
    
    # Build bot
    app = ApplicationBuilder().token(Config.BOT_TOKEN).build()
    
    # Conversation handlers (must be added BEFORE simple handlers)
    app.add_handler(get_appointment_handler())
    
    # Commands
    app.add_handler(CommandHandler('start', start))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(language_callback, pattern='^lang_'))
    app.add_handler(CallbackQueryHandler(show_services, pattern='^services$'))
    app.add_handler(CallbackQueryHandler(show_operations, pattern='^operations$'))
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern='^main_menu$'))
    app.add_handler(CallbackQueryHandler(language_callback, pattern='^change_lang$'))
    
    # Start scheduler
    start_scheduler(app)
    start_keep_alive()
    
    logger.info("🏥 Clinic Bot starting...")
    app.run_polling()


if __name__ == '__main__':
    main()