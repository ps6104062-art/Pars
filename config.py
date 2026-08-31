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

# TON resale filter. Only gifts listed for TON resale and priced below this value are accepted.
MAX_TON_PRICE = float(os.getenv("MAX_TON_PRICE", "10"))
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

# Seller filters
FILTER_ARABIC_TEXT = os.getenv("FILTER_ARABIC_TEXT", "true").lower() in {"1", "true", "yes", "on"}
MAX_SELLER_LEVEL = int(os.getenv("MAX_SELLER_LEVEL", "2"))
SKIP_UNKNOWN_SELLER_LEVEL = os.getenv("SKIP_UNKNOWN_SELLER_LEVEL", "true").lower() in {"1", "true", "yes", "on"}
MAX_PROFILE_NFTS = max(0, int(os.getenv("MAX_PROFILE_NFTS", "5")))

# Forum topics in the destination group.
MALE_THREAD_ID = int(os.getenv("MALE_THREAD_ID", "2"))
FEMALE_THREAD_ID = int(os.getenv("FEMALE_THREAD_ID", "3"))

# Female-name / cat-like username heuristic. Everything else goes to the male topic.
FEMALE_NAMES = {
    x.strip().lower() for x in os.getenv(
        "FEMALE_NAMES",
        "anna,anastasia,alina,alena,alisa,alexandra,angelina,anastasiya,arina,barbara,camila,carina,carolina,christina,daria,dayana,elena,elizaveta,eliza,evа,eva,irina,julia,juliana,katya,katerina,kira,ksenia,larisa,lena,liza,maria,marina,mila,milana,nadezhda,natalia,natasha,oksana,olga,polina,sofia,sofiya,tatiana,veronika,victoria,vika,valeria,valeriya,alina,svetlana,yana,yulia,юлия,юля,анна,анастасия,алина,алёна,алена,алиса,александра,ангелина,арина,варвара,дарья,даша,диана,елена,елизавета,лиза,ева,ирина,катя,екатерина,кира,ксения,лариса,лена,мария,марина,мила,милана,надя,надежда,наталья,наташа,оксана,ольга,полина,софия,софья,татьяна,вероника,виктория,валерия,вика,светлана,яна,юлия"
    ).split(",") if x.strip()
}
CAT_PATTERNS = {
    x.strip().lower() for x in os.getenv(
        "CAT_PATTERNS",
        "cat,kitty,kittie,kitten,meow,mew,nya,nyan,purr,pussy,кот,кошка,кошечка,котик,мяу,мур,murka,murca"
    ).split(",") if x.strip()
}

GIFT_IDS = {int(x.strip()) for x in os.getenv("GIFT_IDS", "").split(",") if x.strip().isdigit()}

if not API_ID or not API_HASH:
    raise RuntimeError("Set API_ID and API_HASH in Railway Variables (or .env locally)")
if not TELEGRAM_SESSION:
    raise RuntimeError("Set TELEGRAM_SESSION in Railway Variables. Generate it locally with: python generate_session.py")
if not DESTINATION_CHAT and not (BOT_TOKEN and BOT_CHAT_ID) and not DRY_RUN:
    raise RuntimeError("Set DESTINATION_CHAT, or BOT_TOKEN + BOT_CHAT_ID in Railway Variables")

BOT_DELETE_ENABLED = os.getenv("BOT_DELETE_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
