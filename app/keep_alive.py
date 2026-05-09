# app/keep_alive.py

import threading
from flask import Flask

app = Flask(__name__)


@app.route('/')
def home():
    return "🏥 Clinic Bot is alive!", 200


@app.route('/health')
def health():
    return {"status": "ok"}, 200


def run_keep_alive():
    port = int(__import__('os').getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port)


def start_keep_alive():
    thread = threading.Thread(target=run_keep_alive, daemon=True)
    thread.start()