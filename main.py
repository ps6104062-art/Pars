import asyncio
import logging

from telethon import TelegramClient
from telethon.sessions import StringSession

import config
from parser import GiftParser
from bot_worker import run_worker_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


async def main():
    # StringSession keeps the Telegram authorization in an environment variable,
    # so Railway does not need a persistent .session file.
    client = TelegramClient(
        StringSession(config.TELEGRAM_SESSION),
        config.API_ID,
        config.API_HASH,
        sequential_updates=True,
    )

    await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError(
            "TELEGRAM_SESSION is invalid or logged out. Generate a new session locally with: "
            "python generate_session.py"
        )

    me = await client.get_me()
    print(f"Authorized as: {getattr(me, 'username', None) or me.id}")

    parser = GiftParser(client)
    bot_task = asyncio.create_task(run_worker_bot()) if config.BOT_TOKEN else None
    try:
        await parser.run()
    finally:
        if bot_task:
            bot_task.cancel()
            await asyncio.gather(bot_task, return_exceptions=True)
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
