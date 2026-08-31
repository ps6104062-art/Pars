import asyncio
import logging
import re
from typing import Dict, Optional

from telethon import errors
from telethon.tl.functions import payments, users
from telethon.tl.types import (
    PeerUser,
    StarGiftAttributeBackdrop,
    StarGiftAttributeModel,
    StarGiftAttributePattern,
)

import config
from database import connect, exists, upsert_seen
from formatter import button_rows, format_listing
from sender import send_alert

log = logging.getLogger("gift-parser")


class GiftParser:
    def __init__(self, client):
        self.client = client
        self.conn = connect()
        self.base_gifts: Dict[int, object] = {}
        self.last_gift_refresh = 0.0
        # Keep Telegram traffic deliberately conservative.  One request at a time
        # is much safer for the large number of resale gift types.
        self.sem = asyncio.Semaphore(config.CONCURRENCY)
        self.user_cache: Dict[int, object] = {}
        self.seller_info_cache: Dict[int, dict] = {}
        self._api_lock = asyncio.Lock()
        self._last_api_call = 0.0

    async def _ensure_connected(self):
        if not self.client.is_connected():
            log.warning("Telegram disconnected; reconnecting...")
            await self.client.connect()

    async def _call(self, request, label: str):
        """Call Telegram with FloodWait/reconnect handling."""
        attempts = 0
        while True:
            attempts += 1
            try:
                # Global pacing: even with concurrency enabled, keep a minimum
                # interval between API calls for the new account.
                async with self._api_lock:
                    now = asyncio.get_running_loop().time()
                    wait = config.MIN_API_REQUEST_INTERVAL - (now - self._last_api_call)
                    if wait > 0:
                        await asyncio.sleep(wait)
                    await self._ensure_connected()
                    result = await asyncio.wait_for(
                        self.client(request),
                        timeout=config.API_REQUEST_TIMEOUT,
                    )
                    self._last_api_call = asyncio.get_running_loop().time()
                    return result
            except errors.FloodWaitError as e:
                wait = int(e.seconds) + 3
                log.warning("FloodWait %ss on %s; sleeping...", wait, label)
                await asyncio.sleep(wait)
            except asyncio.TimeoutError:
                log.warning("Telegram request timed out after %ss: %s", config.API_REQUEST_TIMEOUT, label)
                try:
                    await self.client.disconnect()
                except Exception:
                    pass
                if attempts >= 3:
                    raise
                await asyncio.sleep(min(5 * attempts, 15))
            except (errors.RPCError, ConnectionError, OSError) as e:
                if attempts >= 5:
                    raise
                log.warning("Telegram error on %s (attempt %d/5): %s", label, attempts, e)
                try:
                    await self.client.disconnect()
                except Exception:
                    pass
                await asyncio.sleep(min(10 * attempts, 30))

    async def refresh_gift_types(self, force=False):
        now = asyncio.get_running_loop().time()
        if self.base_gifts and not force and now - self.last_gift_refresh < config.GIFT_TYPES_REFRESH_SECONDS:
            return

        async with self.sem:
            result = await self._call(
                payments.GetStarGiftsRequest(hash=0),
                "GetStarGiftsRequest",
            )
        gifts = getattr(result, "gifts", []) or []
        candidates = {
            int(g.id): g for g in gifts if getattr(g, "availability_resale", None)
        }
        if config.GIFT_IDS:
            candidates = {gid: g for gid, g in candidates.items() if gid in config.GIFT_IDS}
        self.base_gifts = candidates
        self.last_gift_refresh = now
        log.info("Resale gift types: %d", len(self.base_gifts))

    @staticmethod
    def _stars_amount(value) -> Optional[float]:
        amount = getattr(value, "amount", None)
        if amount is None:
            return None
        nanos = getattr(value, "nanos", 0) or 0
        return float(amount) + float(nanos) / 1_000_000_000

    @classmethod
    def _price(cls, gift) -> Optional[float]:
        amounts = getattr(gift, "resell_amount", None) or []
        for amount in amounts:
            value = cls._stars_amount(amount)
            if value is not None:
                return value
        return None

    @staticmethod
    def _attrs(gift) -> dict:
        out = {"model": None, "symbol": None, "backdrop": None}
        for attr in getattr(gift, "attributes", []) or []:
            if isinstance(attr, StarGiftAttributeModel) and not getattr(attr, "crafted", False):
                out["model"] = attr.name
            elif isinstance(attr, StarGiftAttributePattern):
                out["symbol"] = attr.name
            elif isinstance(attr, StarGiftAttributeBackdrop):
                out["backdrop"] = attr.name
        return out

    @staticmethod
    def _peer_id(peer) -> Optional[int]:
        if isinstance(peer, PeerUser):
            return int(peer.user_id)
        value = getattr(peer, "user_id", None)
        return int(value) if value is not None else None

    @staticmethod
    def _has_arabic(text: str) -> bool:
        if not text:
            return False
        # Arabic, Arabic Supplement/Extended and Presentation Forms blocks.
        return bool(re.search(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]", text))

    @classmethod
    def _seller_has_arabic(cls, username: str, first_name: str, last_name: str, bio: str) -> bool:
        if not config.FILTER_ARABIC_TEXT:
            return False
        return any(cls._has_arabic(x or "") for x in (username, first_name, last_name, bio))

    async def _seller_info(self, owner_id: int, result):
        if owner_id in self.seller_info_cache:
            return self.seller_info_cache[owner_id]

        result_users = {int(u.id): u for u in (getattr(result, "users", []) or [])}
        user = result_users.get(owner_id) or self.user_cache.get(owner_id)
        full_user = None

        try:
            full_result = await self._call(
                users.GetFullUserRequest(id=owner_id),
                f"GetFullUserRequest user={owner_id}",
            )
            full_user = getattr(full_result, "full_user", None)
            extra_users = getattr(full_result, "users", []) or []
            for candidate in extra_users:
                if int(getattr(candidate, "id", 0)) == owner_id:
                    user = candidate
                    break
        except Exception as e:
            log.debug("Could not load full seller info for %s: %s", owner_id, e)

        if user is not None:
            self.user_cache[owner_id] = user

        username = (getattr(user, "username", None) or "") if user is not None else ""
        first_name = (getattr(user, "first_name", None) or "") if user is not None else ""
        last_name = (getattr(user, "last_name", None) or "") if user is not None else ""
        bio = (getattr(full_user, "about", None) or "") if full_user is not None else ""
        stars_rating = getattr(full_user, "stars_rating", None) if full_user is not None else None
        level = getattr(stars_rating, "level", None) if stars_rating is not None else None

        info = {
            "username": str(username),
            "first_name": str(first_name),
            "last_name": str(last_name),
            "bio": str(bio),
            "level": int(level) if level is not None else None,
        }
        self.seller_info_cache[owner_id] = info
        return info

    async def _seller(self, gift, result):
        owner = getattr(gift, "owner_id", None)
        owner_id = self._peer_id(owner)
        if owner_id:
            info = await self._seller_info(owner_id, result)
            username = info["username"]
            first_name = info["first_name"]
            last_name = info["last_name"]
            bio = info["bio"]
            level = info["level"]

            if self._seller_has_arabic(username, first_name, last_name, bio):
                return None
            if level is None and config.SKIP_UNKNOWN_SELLER_LEVEL:
                return None
            if level is not None and level > config.MAX_SELLER_LEVEL:
                return None

            name = " ".join(x for x in (first_name, last_name) if x)
            return str(owner_id), username, name or str(owner_id)
        return "", "", getattr(gift, "owner_name", None) or "Unknown"

    async def _fetch_pages(self, base_id: int):
        offset = ""
        for page in range(min(config.MAX_PAGES_PER_GIFT, 3)):
            async with self.sem:
                if config.REQUEST_DELAY:
                    await asyncio.sleep(config.REQUEST_DELAY)
                result = await self._call(
                    payments.GetResaleStarGiftsRequest(
                        sort_by_price=False,
                        sort_by_num=False,
                        for_craft=False,
                        stars_only=True,
                        attributes_hash=None,
                        gift_id=base_id,
                        attributes=None,
                        offset=offset,
                        limit=config.PAGE_LIMIT,
                    ),
                    f"GetResaleStarGiftsRequest gift={base_id} page={page + 1}",
                )
            gifts = getattr(result, "gifts", []) or []
            if not gifts:
                return
            yield result, gifts
            prices = [self._price(g) for g in gifts]
            # Results are sorted by price, so later pages cannot contain useful
            # listings once this page is already above our maximum.
            if any(p is not None and p > config.MAX_PRICE for p in prices):
                return
            next_offset = getattr(result, "next_offset", None)
            if not next_offset or next_offset == offset:
                return
            offset = next_offset

    def _make_data(self, base_id, gift, result, price, seller):
        seller_id, seller_username, seller_name = seller
        slug = getattr(gift, "slug", "") or ""
        base = self.base_gifts[base_id]
        attrs = self._attrs(gift)
        return {
            "gift_id": int(gift.id),
            "base_gift_id": int(base_id),
            "title": getattr(gift, "title", None) or getattr(base, "title", None) or "Unknown Gift",
            "slug": slug,
            "number": getattr(gift, "num", None),
            "price": price,
            "seller_id": seller_id,
            "seller_username": seller_username,
            "seller_name": seller_name,
            **attrs,
            "link": f"https://t.me/nft/{slug}" if slug else "",
            "seller_link": f"https://t.me/{seller_username}" if seller_username else "",
        }

    async def _process_type(self, base_id: int, alert_new: bool):
        try:
            async for result, gifts in self._fetch_pages(base_id):
                for gift in gifts:
                    price = self._price(gift)
                    if price is None or price > config.MAX_PRICE:
                        continue
                    if exists(self.conn, int(gift.id)):
                        continue
                    seller = await self._seller(gift, result)
                    if seller is None:
                        continue
                    data = self._make_data(base_id, gift, result, price, seller)

                    if not alert_new:
                        upsert_seen(self.conn, data, alerted=False)
                        continue

                    text = format_listing(data)
                    await send_alert(self.client, text, button_rows(data))
                    upsert_seen(self.conn, data, alerted=True)
                    log.info("ALERT %s #%s — %.3f Stars", data["title"], data["number"], price)
        except errors.FloodWaitError as e:
            # _call normally handles this, but keep a final guard here.
            log.warning("FloodWait %ss on gift type %s", e.seconds, base_id)
            await asyncio.sleep(int(e.seconds) + 3)
        except Exception:
            log.exception("Unexpected error on gift type %s", base_id)

    async def scan_once(self, alert_new: bool):
        await self.refresh_gift_types()
        ids = list(self.base_gifts)
        log.info("Scanning %d gift types...", len(ids))
        # Do not create 118 simultaneous coroutines that can all hit Telegram.
        # A small worker pool keeps memory low and traffic predictable.
        queue = asyncio.Queue()
        for gid in ids:
            await queue.put(gid)

        async def worker():
            while True:
                try:
                    gid = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    await self._process_type(gid, alert_new)
                finally:
                    queue.task_done()
                    # Progress logging makes long scans visible in Railway logs.
                    completed = len(ids) - queue.qsize()
                    if completed == len(ids) or completed % 10 == 0:
                        log.info("Scan progress: %d/%d gift types", completed, len(ids))

        workers = [asyncio.create_task(worker()) for _ in range(min(config.CONCURRENCY, len(ids)))]
        await queue.join()
        await asyncio.gather(*workers, return_exceptions=True)

    async def run(self):
        log.info(
            "Started. Price <= %s Stars, concurrency=%d, interval=%ss, delay=%ss, timeout=%ss",
            config.MAX_PRICE, config.CONCURRENCY, config.SCAN_INTERVAL, config.REQUEST_DELAY, config.API_REQUEST_TIMEOUT,
        )

        await self.scan_once(alert_new=config.ALERT_EXISTING_ON_START)
        log.info("Initial baseline complete; monitoring new listings")

        while True:
            started = asyncio.get_running_loop().time()
            await self.scan_once(alert_new=True)
            elapsed = asyncio.get_running_loop().time() - started
            await asyncio.sleep(max(1.0, config.SCAN_INTERVAL - elapsed))
