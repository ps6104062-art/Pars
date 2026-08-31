import asyncio
import json
import logging
import aiohttp
import config

log = logging.getLogger("gift-bot-worker")


async def run_worker_bot():
    if not config.BOT_TOKEN or not config.BOT_DELETE_ENABLED:
        log.info("Worker bot disabled")
        return

    api = f"https://api.telegram.org/bot{config.BOT_TOKEN}"
    offset = 0
    async with aiohttp.ClientSession() as session:
        # Polling does not work while a webhook is configured for the bot.
        # Remove it on startup so the callback button is reliably delivered here.
        try:
            async with session.post(
                f"{api}/deleteWebhook",
                json={"drop_pending_updates": False},
                timeout=20,
            ) as wr:
                webhook_result = await wr.json(content_type=None)
            if not webhook_result.get("ok"):
                log.warning("deleteWebhook failed: %s", webhook_result)
        except Exception:
            log.exception("Failed to reset bot webhook")

        while True:
            try:
                async with session.post(
                    f"{api}/getUpdates",
                    json={"timeout": 50, "offset": offset, "allowed_updates": ["callback_query"]},
                    timeout=60,
                ) as r:
                    data = await r.json(content_type=None)
                if not data.get("ok"):
                    await asyncio.sleep(3)
                    continue

                for update in data.get("result", []):
                    offset = int(update["update_id"]) + 1
                    cq = update.get("callback_query")
                    if not cq:
                        continue
                    callback_id = cq.get("id")
                    payload = cq.get("data", "")
                    message = cq.get("message") or {}
                    chat = message.get("chat", {})
                    msg_id = message.get("message_id")

                    if payload.startswith("delete:") and msg_id and chat.get("id"):
                        async with session.post(
                            f"{api}/deleteMessage",
                            json={"chat_id": chat["id"], "message_id": msg_id},
                            timeout=20,
                        ) as dr:
                            delete_body = await dr.json(content_type=None)
                        deleted = bool(delete_body.get("ok", False))
                        if deleted:
                            answer = "Лот удалён из канала ✅"
                        else:
                            log.warning("deleteMessage failed: %s", delete_body)
                            answer = "Не удалось удалить лот ❌"
                    else:
                        answer = "Готово"

                    # Answer immediately so Telegram stops showing the button spinner.
                    await session.post(
                        f"{api}/answerCallbackQuery",
                        json={"callback_query_id": callback_id, "text": answer, "show_alert": False},
                        timeout=20,
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Worker bot polling error")
                await asyncio.sleep(3)
