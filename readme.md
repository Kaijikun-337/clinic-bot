# 🏥 Clinic Bot

A Telegram bot for medical clinic appointment management with multi-language support.

## 📋 Overview

Clinic Bot is a feature-rich Telegram bot designed for medical clinics to manage appointments, display services, and provide information about surgical operations. The bot supports multiple languages (English, Russian, Uzbek) and includes automated reminders for upcoming appointments.

## ✨ Features

- 📅 **Appointment Booking** - Patients can book appointments with available time slots
- 🔔 **Automated Reminders** - Sends reminders 1 hour before scheduled appointments
- 🌐 **Multi-language Support** - Available in English, Russian, and Uzbek
- 💉 **Services Display** - Browse available medical services with descriptions
- 🏥 **Operations Info** - View information about surgical operations
- 👤 **Admin Panel** - Manage appointments and view statistics
- 📊 **Google Sheets Integration** - Sync data with Google Sheets (optional)
- ⏰ **Flexible Scheduling** - 20-minute appointment slots with timezone support

## 📁 Project Structure

```
clinic-bot/
├── app/
│   ├── __init__.py
│   ├── db.py              # Database operations (SQLite)
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── appointment.py  # Appointment booking flow
│   │   ├── operations.py   # Operations display
│   │   ├── services.py     # Services display
│   │   └── start.py        # Start command & language selection
│   ├── localization.py     # Multi-language support
│   ├── scheduler.py        # Appointment reminders
│   └── sheets.py           # Google Sheets integration
├── data/
│   ├── operations.json     # Operations data
│   ├── services.json       # Services data
│   └── strings.json        # Localization strings
├── config.py               # Configuration management
├── main.py                 # Bot entry point
└── requirements.txt        # Python dependencies
```

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/Kaijikun-337/clinic-bot.git
cd clinic-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file with your configuration
echo "BOT_TOKEN=your_telegram_bot_token" > .env

# Run the bot
python main.py
```

## 🔧 Configuration

Create a `.env` file in the root directory:

```env
BOT_TOKEN=your_telegram_bot_token
ADMIN_IDS=123456789,987654321
# GOOGLE_SHEETS_ID=your_google_sheets_id
# GOOGLE_CREDENTIALS_FILE=credentials.json
```

### Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `BOT_TOKEN` | Telegram bot token from @BotFather | Required |
| `ADMIN_IDS` | Comma-separated admin Telegram IDs | Empty |
| `TIMEZONE` | Timezone for scheduling | `Asia/Tashkent` |
| `SLOT_DURATION_MINUTES` | Duration per appointment slot | `20` |
| `REMINDER_HOURS_BEFORE` | Hours before appointment to send reminder | `1` |

## 📦 Dependencies

```
python-telegram-bot==20.7   # Telegram Bot API wrapper
python-dotenv==1.0.0        # Environment variable management
apscheduler==3.10.4         # Task scheduling for reminders
gspread==5.12.4             # Google Sheets API client
oauth2client==4.1.3         # OAuth2 authentication
pytz==2023.3                # Timezone handling
```

## 💬 Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Initialize the bot and select language |
| Book Appointment | Select date and time slot |
| View Services | Browse available medical services |
| View Operations | See information about surgical procedures |
| Change Language | Switch between EN/RU/UZ |
| Main Menu | Return to the main menu |

## 🌍 Localization

The bot supports three languages:
- 🇺🇸 English (`en`)
- 🇷🇺 Russian (`ru`)
- 🇺🇿 Uzbek (`uz`)

Translation strings are stored in `data/strings.json`. To add a new language:

1. Add a new language code to `strings.json`
2. Translate all keys
3. Update the language selection in `start.py`

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is open source. Please check the repository for license details.

## 👨‍💻 Author

**Kaijikun-337**

- GitHub: [@Kaijikun-337](https://github.com/Kaijikun-337)
- Repository: [clinic-bot](https://github.com/Kaijikun-337/clinic-bot)

---

Made with 💜
