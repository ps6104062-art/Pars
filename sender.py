import aiohttp
import config


def _keyboard(buttons):
    rows = []
    for row in buttons or []:
        out = []
        for item in row:
            label = item[0]
            if len(item) >= 3 and item[2]:
                out.append({"text": label, "callback_data": item[2]})
            elif len(item) >= 2 and item[1]:
                out.append({"text": label, "url": item[1]})
        if out:
            rows.append(out)
    return {"inline_keyboard": rows} if rows else None


async def send_alert(client, text: str, buttons, thread_id=None):
    """Send an alert to the configured destination/forum topic."""
    if config.DRY_RUN:
        print("\n--- DRY RUN ---")
        print(text)
        print("--- END ---\n")
        return None

    if config.BOT_TOKEN and config.BOT_CHAT_ID:
        return await _send_bot_api(text, buttons, config.BOT_CHAT_ID, thread_id)

    if config.DESTINATION_CHAT:
        from telethon import Button
        telethon_buttons = []
        for row in buttons or []:
            out = []
            for item in row:
                label = item[0]
                if len(item) >= 3 and item[2]:
                    out.append(Button.inline(label, data=item[2].encode("utf-8")))
                elif len(item) >= 2 and item[1]:
                    out.append(Button.url(label, item[1]))
            if out:
                telethon_buttons.append(out)

        return await client.send_message(
            config.DESTINATION_CHAT,
            text,
            parse_mode="html",
            link_preview=False,
            buttons=telethon_buttons or None,
            reply_to=thread_id if thread_id and thread_id != 1 else None,
        )

    raise RuntimeError("No destination configured")


async def _send_bot_api(text, buttons, chat_id, thread_id=None):
    keyboard = _keyboard(buttons)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": keyboard,
    }
    if thread_id and int(thread_id) != 1:
        payload["message_thread_id"] = int(thread_id)

    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=20) as response:
            body = await response.json(content_type=None)
            if response.status != 200 or not body.get("ok"):
                raise RuntimeError(f"Bot API error {response.status}: {body}")
            return body.get("result")


async def delete_bot_message(chat_id, message_id):
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/deleteMessage"
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json={"chat_id": chat_id, "message_id": message_id},
            timeout=20,
        ) as response:
            body = await response.json(content_type=None)
            return response.status == 200 and body.get("ok", False)
