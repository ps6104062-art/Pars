"""Generate a Telethon StringSession for Railway.

Run locally after setting API_ID and API_HASH (and optionally PHONE) in .env:
    python generate_session.py

The printed value is a secret. Put it in Railway as TELEGRAM_SESSION.
"""

import os

from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

api_id = int(os.getenv("API_ID", "0"))
api_hash = os.getenv("API_HASH", "").strip()
phone = os.getenv("PHONE", "").strip()

if not api_id or not api_hash:
    raise SystemExit("Set API_ID and API_HASH in .env before running this script.")

with TelegramClient(StringSession(), api_id, api_hash) as client:
    if phone:
        client.start(phone=phone)
    else:
        client.start()
    print("\nTELEGRAM_SESSION=\n")
    print(client.session.save())
    print("\nCopy the single-line value above into Railway -> Variables -> TELEGRAM_SESSION.")
    print("NEVER publish or send this value to anyone.")
