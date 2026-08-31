import sqlite3
from pathlib import Path

DB_PATH = Path("gifts.db")
DATA_VERSION = 2  # Stars-price/topic routing replaces the previous TON/gender mode.

SCHEMA = '''
CREATE TABLE IF NOT EXISTS listings (
    gift_id INTEGER PRIMARY KEY,
    base_gift_id INTEGER NOT NULL,
    title TEXT,
    slug TEXT,
    number INTEGER,
    price REAL NOT NULL,
    seller_id TEXT,
    seller_username TEXT,
    seller_name TEXT,
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    alerted INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_listings_base_gift_id ON listings(base_gift_id);
CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price);
CREATE INDEX IF NOT EXISTS idx_listings_seller_id ON listings(seller_id);

CREATE TABLE IF NOT EXISTS seen_sellers (
    seller_id TEXT PRIMARY KEY,
    seller_username TEXT,
    seller_name TEXT,
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
'''

def connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)

    # If a database from the previous TON/gender version is present, start
    # this Stars/price-topic version with a clean baseline. This prevents old
    # seen sellers/listings from blocking the new routing rules.
    conn.execute("CREATE TABLE IF NOT EXISTS bot_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    row = conn.execute("SELECT value FROM bot_meta WHERE key='data_version'").fetchone()
    if row is None or int(row[0]) != DATA_VERSION:
        conn.execute("DELETE FROM listings")
        conn.execute("DELETE FROM seen_sellers")
        conn.execute(
            "INSERT INTO bot_meta (key, value) VALUES ('data_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(DATA_VERSION),),
        )
        conn.commit()
    return conn

def is_alerted(conn, gift_id: int) -> bool:
    row = conn.execute("SELECT alerted FROM listings WHERE gift_id=?", (gift_id,)).fetchone()
    return bool(row and row["alerted"])

def exists(conn, gift_id: int) -> bool:
    row = conn.execute("SELECT 1 FROM listings WHERE gift_id=?", (gift_id,)).fetchone()
    return row is not None

def seller_seen(conn, seller_id: str) -> bool:
    if not seller_id:
        return False
    row = conn.execute("SELECT 1 FROM seen_sellers WHERE seller_id=?", (seller_id,)).fetchone()
    return row is not None

def mark_seller_seen(conn, seller_id: str, username: str = "", name: str = ""):
    if not seller_id:
        return
    conn.execute(
        "INSERT OR IGNORE INTO seen_sellers (seller_id, seller_username, seller_name) VALUES (?, ?, ?)",
        (seller_id, username, name),
    )
    conn.commit()

def upsert_seen(conn, data: dict, alerted: bool = False):
    conn.execute(
        '''INSERT INTO listings
           (gift_id, base_gift_id, title, slug, number, price,
            seller_id, seller_username, seller_name, alerted)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(gift_id) DO UPDATE SET
             price=excluded.price,
             seller_id=excluded.seller_id,
             seller_username=excluded.seller_username,
             seller_name=excluded.seller_name,
             last_seen_at=CURRENT_TIMESTAMP,
             alerted=MAX(listings.alerted, excluded.alerted)''',
        (data["gift_id"], data["base_gift_id"], data["title"], data["slug"],
         data["number"], data["price"], data["seller_id"],
         data["seller_username"], data["seller_name"], int(alerted)),
    )
    conn.commit()

def mark_alerted(conn, gift_id: int):
    conn.execute("UPDATE listings SET alerted=1, last_seen_at=CURRENT_TIMESTAMP WHERE gift_id=?", (gift_id,))
    conn.commit()
