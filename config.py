import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "").strip()
PHONE = os.getenv("PHONE", "").strip()
# Railway-friendly authentication: keep the Telethon StringSession in an environment variable.
TELEGRAM_SESSION = os.getenv("TELEGRAM_SESSION", "").strip()

DESTINATION_CHAT = os.getenv("DESTINATION_CHAT", "").strip()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
BOT_CHAT_ID = os.getenv("BOT_CHAT_ID", "").strip()

MAX_PRICE = float(os.getenv("MAX_PRICE", "7000"))
SCAN_INTERVAL = max(30.0, float(os.getenv("SCAN_INTERVAL", "180")))
CONCURRENCY = max(1, min(2, int(os.getenv("CONCURRENCY", "1"))))
REQUEST_DELAY = max(0.0, float(os.getenv("REQUEST_DELAY", "2.5")))
# Minimum gap between Telegram API requests. Keep this conservative for a new account.
MIN_API_REQUEST_INTERVAL = max(0.5, float(os.getenv("MIN_API_REQUEST_INTERVAL", "2.5")))
# Per-request timeout so one stalled Telegram request cannot freeze the whole scan.
API_REQUEST_TIMEOUT = max(10.0, float(os.getenv("API_REQUEST_TIMEOUT", "45")))
PAGE_LIMIT = min(max(1, int(os.getenv("PAGE_LIMIT", "25"))), 100)
MAX_PAGES_PER_GIFT = max(1, min(2, int(os.getenv("MAX_PAGES_PER_GIFT", "1"))))
GIFT_TYPES_REFRESH_SECONDS = max(60, int(os.getenv("GIFT_TYPES_REFRESH_SECONDS", "1800")))
ALERT_EXISTING_ON_START = os.getenv("ALERT_EXISTING_ON_START", "false").lower() in {"1", "true", "yes", "on"}
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in {"1", "true", "yes", "on"}

# Seller filters
FILTER_ARABIC_TEXT = os.getenv("FILTER_ARABIC_TEXT", "true").lower() in {"1", "true", "yes", "on"}
MAX_SELLER_LEVEL = int(os.getenv("MAX_SELLER_LEVEL", "2"))
SKIP_UNKNOWN_SELLER_LEVEL = os.getenv("SKIP_UNKNOWN_SELLER_LEVEL", "true").lower() in {"1", "true", "yes", "on"}

# Optional comma-separated base gift IDs. Empty = all resale-enabled types.
GIFT_IDS = {
    int(x.strip()) for x in os.getenv("GIFT_IDS", "").split(",") if x.strip().isdigit()
}

if not API_ID or not API_HASH:
    raise RuntimeError("Set API_ID and API_HASH in Railway Variables (or .env locally)")
if not TELEGRAM_SESSION:
    raise RuntimeError("Set TELEGRAM_SESSION in Railway Variables. Generate it locally with: python generate_session.py")
if not DESTINATION_CHAT and not (BOT_TOKEN and BOT_CHAT_ID) and not DRY_RUN:
    raise RuntimeError("Set DESTINATION_CHAT, or BOT_TOKEN + BOT_CHAT_ID in Railway Variables")

# Optional: bot that sends the messages and handles the worker's "delete" button.
# The bot must be an administrator in the destination channel/chat with permission to delete messages.
BOT_DELETE_ENABLED = os.getenv("BOT_DELETE_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
