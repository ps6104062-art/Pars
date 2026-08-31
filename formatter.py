from html import escape


def format_price(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value):,}".replace(",", " ")
    return f"{value:,.9f}".rstrip("0").rstrip(".").replace(",", " ")


def _seller_text(g: dict) -> str:
    seller = g.get("seller_username")
    if seller:
        return f"@{escape(str(seller).lstrip('@'))}"
    return escape(str(g.get("seller_name") or "Unknown"))


def format_listing(g: dict) -> str:
    """Telegram-friendly listing layout inspired by the requested reference."""
    title = escape(str(g.get("title") or "Unknown Gift"))
    model = escape(str(g.get("model") or "—"))
    symbol = escape(str(g.get("symbol") or "—"))
    backdrop = escape(str(g.get("backdrop") or "—"))
    number = g.get("number")
    num_text = f"#{number}" if number is not None else "—"
    seller_text = _seller_text(g)

    # The NFT title itself is a clickable link when Telegram provides its slug.
    nft_link = str(g.get("link") or "").strip()
    title_line = (
        f'<blockquote><a href="{escape(nft_link, quote=True)}"><b>{title} {num_text}</b></a></blockquote>'
        if nft_link else
        f"<blockquote><b>{title} {num_text}</b></blockquote>"
    )

    return (
        "🎁 <b>Новый подарок!</b>\n\n"
        f"{title_line}\n\n"
        f"🔎 <b>Название:</b> {title}\n"
        f"🎨 <b>Модель:</b> {model}\n"
        f"🔹 <b>Символ:</b> {symbol}\n"
        f"🖼 <b>Фон:</b> {backdrop}\n"
        f"🔢 <b>Номер:</b> {num_text}\n\n"
        f"<blockquote>⭐ <b>Цена:</b> {format_price(g['price'])} ⭐\n"
        f"🌪 <b>Маркет:</b> Telegram\n"
        f"👤 <b>Продавец:</b> {seller_text}</blockquote>"
    )


def button_rows(g: dict):
    """Inline buttons: NFT first, then seller actions."""
    rows = []
    if g.get("link"):
        rows.append([("🎁 Открыть подарок", g["link"])])
    if g.get("seller_link"):
        rows.append([("👤 Открыть продавца", g["seller_link"])])
        rows.append([("📝 Написать продавцу", g["seller_link"])])
    rows.append([("✅ Отписал мамонту", "", f"delete:{int(g["gift_id"])}")])
    return rows
