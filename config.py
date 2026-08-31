import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "").strip()
PHONE = os.getenv("PHONE", "").strip()
TELEGRAM_SESSION = os.getenv("TELEGRAM_SESSION", "").strip()

DESTINATION_CHAT = os.getenv("DESTINATION_CHAT", "").strip()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
BOT_CHAT_ID = os.getenv("BOT_CHAT_ID", "").strip()

# Resale filter is now based on Telegram Stars.
# Gifts cheaper than the threshold go to the low-price topic,
# gifts more expensive than the threshold go to the high-price topic.
STAR_PRICE_THRESHOLD = float(os.getenv("STAR_PRICE_THRESHOLD", "2000"))
LOW_STAR_THREAD_ID = int(os.getenv("LOW_STAR_THREAD_ID", "2"))
HIGH_STAR_THREAD_ID = int(os.getenv("HIGH_STAR_THREAD_ID", "3"))
SCAN_INTERVAL = max(30.0, float(os.getenv("SCAN_INTERVAL", "180")))
CONCURRENCY = max(1, min(2, int(os.getenv("CONCURRENCY", "1"))))
REQUEST_DELAY = max(0.0, float(os.getenv("REQUEST_DELAY", "2.5")))
MIN_API_REQUEST_INTERVAL = max(0.5, float(os.getenv("MIN_API_REQUEST_INTERVAL", "2.5")))
API_REQUEST_TIMEOUT = max(10.0, float(os.getenv("API_REQUEST_TIMEOUT", "45")))
PAGE_LIMIT = min(max(1, int(os.getenv("PAGE_LIMIT", "25"))), 100)
MAX_PAGES_PER_GIFT = max(1, min(2, int(os.getenv("MAX_PAGES_PER_GIFT", "1"))))
GIFT_TYPES_REFRESH_SECONDS = max(60, int(os.getenv("GIFT_TYPES_REFRESH_SECONDS", "1800")))
ALERT_EXISTING_ON_START = os.getenv("ALERT_EXISTING_ON_START", "true").lower() in {"1", "true", "yes", "on"}
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in {"1", "true", "yes", "on"}

# Seller filters retained from the previous setup.
FILTER_ARABIC_TEXT = os.getenv("FILTER_ARABIC_TEXT", "true").lower() in {"1", "true", "yes", "on"}
MAX_SELLER_LEVEL = int(os.getenv("MAX_SELLER_LEVEL", "2"))
SKIP_UNKNOWN_SELLER_LEVEL = os.getenv("SKIP_UNKNOWN_SELLER_LEVEL", "true").lower() in {"1", "true", "yes", "on"}
MAX_PROFILE_NFTS = max(0, int(os.getenv("MAX_PROFILE_NFTS", "5")))

# Backward-compatible names: old Railway variables can stay, but are no longer
# used for gender classification.
MALE_THREAD_ID = LOW_STAR_THREAD_ID
FEMALE_THREAD_ID = HIGH_STAR_THREAD_ID

# Kept only so an old environment does not break; the female-name/cat filter is removed.
GIFT_IDS = {int(x.strip()) for x in os.getenv("GIFT_IDS", "").split(",") if x.strip().isdigit()}

if not API_ID or not API_HASH:
    raise RuntimeError("Set API_ID and API_HASH in Railway Variables (or .env locally)")
if not TELEGRAM_SESSION:
    raise RuntimeError("Set TELEGRAM_SESSION in Railway Variables. Generate it locally with: python generate_session.py")
if not DESTINATION_CHAT and not (BOT_TOKEN and BOT_CHAT_ID) and not DRY_RUN:
    raise RuntimeError("Set DESTINATION_CHAT, or BOT_TOKEN + BOT_CHAT_ID in Railway Variables")

BOT_DELETE_ENABLED = os.getenv("BOT_DELETE_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
