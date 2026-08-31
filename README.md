# Telegram Gift Marketplace Parser v2 — Railway + StringSession

Fast polling parser for Telegram's official collectible-gift resale API.

## Railway authentication

This version uses Telethon `StringSession` instead of a local `*.session` file. The session is supplied through the `TELEGRAM_SESSION` environment variable, which is suitable for Railway deployments.

### 1. Generate the session locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Create `.env` from `.env.example` and set:

```env
API_ID=your_api_id
API_HASH=your_api_hash
PHONE=+998XXXXXXXXX
```

Then run:

```bash
python generate_session.py
```

Telegram will ask for the login code and, if enabled, the 2FA password. The script prints a single-line StringSession.

**Treat the StringSession like a password. Anyone who gets it can use the Telegram authorization.**

### 2. Add variables to Railway

In **Service → Variables**, add:

```text
API_ID=...
API_HASH=...
TELEGRAM_SESSION=...
DESTINATION_CHAT=@your_channel_or_chat
```

`PHONE` is not required by the running Railway service once `TELEGRAM_SESSION` has been generated. It may remain in Railway if you want, but it is not used for authentication in `main.py`.

Alternatively, instead of `DESTINATION_CHAT`, you can use:

```text
BOT_TOKEN=...
BOT_CHAT_ID=...
```

Do not commit `.env` or the StringSession to GitHub.

## Local testing

With `TELEGRAM_SESSION` in `.env`, run:

```bash
python main.py
```

The program should print the authorized Telegram account and start monitoring.

## Speed settings

Default:

```env
MAX_PRICE=7000
SCAN_INTERVAL=10
CONCURRENCY=3
REQUEST_DELAY=0.15
```

For a new account, keep `CONCURRENCY=1` and `MIN_API_REQUEST_INTERVAL=2.5`. Do not optimize for maximum request speed; this version intentionally favors conservative traffic. Telegram may return `FloodWait`, so more concurrency is not always faster.

For the fastest possible monitoring, provide selected base gift IDs:

```env
GIFT_IDS=123,456,789
```

If empty, every resale-enabled base gift type returned by `payments.getStarGifts` is monitored.

## Important API limitation

`payments.getResaleStarGifts` requires a specific `gift_id`; it does not provide one global endpoint for every gift type. Therefore monitoring every gift type necessarily means multiple API requests. The parser parallelizes those requests but deliberately limits concurrency to reduce rate-limit pressure.

## Alert behavior

The first scan is a baseline by default. Existing listings are saved without an alert. New unseen gifts found afterward are sent to the destination.

Set `ALERT_EXISTING_ON_START=true` if you deliberately want the first scan to send all qualifying existing listings.

## Security

Never share `.env`, `TELEGRAM_SESSION`, API hash, or bot token. If a StringSession is exposed, revoke the Telegram session from an official Telegram client and generate a new one.

## Worker button: "Отписал мамонту"

To make the button delete the lot from the channel, configure `BOT_TOKEN` and `BOT_CHAT_ID` in Railway. The bot must be an administrator in the destination channel/chat and have permission to delete messages. When `BOT_TOKEN` is configured, alerts are sent by the bot so Telegram callback buttons work; the user account still handles the marketplace parser/session.

Set:
```env
BOT_TOKEN=123456:ABC...
BOT_CHAT_ID=@your_channel
BOT_DELETE_ENABLED=true
```


### Seller filters

The parser can skip sellers whose username/name/bio contains Arabic-script characters. It also reads the Telegram Stars profile level from `userFull.stars_rating.level` and keeps only sellers at or below `MAX_SELLER_LEVEL`.

```env
FILTER_ARABIC_TEXT=true
MAX_SELLER_LEVEL=2
SKIP_UNKNOWN_SELLER_LEVEL=true
```

If the seller's level cannot be read, `SKIP_UNKNOWN_SELLER_LEVEL=true` skips that listing instead of allowing an unknown level through.
