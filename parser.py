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
from database import connect, exists, seller_seen, mark_seller_seen, upsert_seen
from formatter import button_rows, format_listing
from sender import send_alert

log = logging.getLogger("gift-parser")


class GiftParser:
    def __init__(self, client):
        self.client = client
        self.conn = connect()
        self.base_gifts: Dict[int, object] = {}
        self.last_gift_refresh = 0.0
        self.sem = asyncio.Semaphore(config.CONCURRENCY)
        self.user_cache: Dict[int, object] = {}
        self.seller_info_cache: Dict[int, dict] = {}
        self._api_lock = asyncio.Lock()
        self._last_api_call = 0.0
        self._seller_send_lock = asyncio.Lock()

    async def _ensure_connected(self):
        if not self.client.is_connected():
            log.warning("Telegram disconnected; reconnecting...")
            await self.client.connect()

    async def _call(self, request, label: str):
        attempts = 0
        while True:
            attempts += 1
            try:
                async with self._api_lock:
                    now = asyncio.get_running_loop().time()
                    wait = config.MIN_API_REQUEST_INTERVAL - (now - self._last_api_call)
                    if wait > 0:
                        await asyncio.sleep(wait)
                    await self._ensure_connected()
                    result = await asyncio.wait_for(
                        self.client(request), timeout=config.API_REQUEST_TIMEOUT
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
            result = await self._call(payments.GetStarGiftsRequest(hash=0), "GetStarGiftsRequest")
        gifts = getattr(result, "gifts", []) or []
        candidates = {int(g.id): g for g in gifts if getattr(g, "availability_resale", None)}
        if config.GIFT_IDS:
            candidates = {gid: g for gid, g in candidates.items() if gid in config.GIFT_IDS}
        self.base_gifts = candidates
        self.last_gift_refresh = now
        log.info("Resale gift types: %d", len(self.base_gifts))

    @staticmethod
    def _ton_price(gift) -> Optional[float]:
        """Return resale price in TON only. Non-TON resale listings are ignored."""
        if not bool(getattr(gift, "resale_ton_only", False)):
            return None
        amounts = getattr(gift, "resell_amount", None) or []
        for amount in amounts:
            raw = getattr(amount, "amount", None)
            if raw is None:
                continue
            # Telegram's TON resale amount is represented in nanograms.
            return float(raw) / 1_000_000_000
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
        profile_nfts = getattr(full_user, "stargifts_count", None) if full_user is not None else None

        info = {
            "username": str(username),
            "first_name": str(first_name),
            "last_name": str(last_name),
            "bio": str(bio),
            "level": int(level) if level is not None else None,
            "profile_nfts": int(profile_nfts) if profile_nfts is not None else None,
        }
        self.seller_info_cache[owner_id] = info
        return info

    @staticmethod
    def _looks_female(username: str, first_name: str, last_name: str) -> bool:
        values = [str(username or "").lower().replace("_", " "), str(first_name or "").lower(), str(last_name or "").lower()]
        joined = " ".join(values)
        compact = re.sub(r"[^\wа-яё]", "", joined, flags=re.IGNORECASE)

        for name in config.FEMALE_NAMES:
            n = name.lower().strip()
            if not n:
                continue
            if re.search(rf"(?<![\wа-яё]){re.escape(n)}(?![\wа-яё])", joined, re.IGNORECASE):
                return True
            # Names in usernames often have digits or punctuation attached.
            if len(n) >= 4 and n in compact:
                return True

        for pattern in config.CAT_PATTERNS:
            p = pattern.lower().strip()
            if p and p in compact:
                return True
        return False

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
            profile_nfts = info["profile_nfts"]

            if self._seller_has_arabic(username, first_name, last_name, bio):
                return None
            if level is None and config.SKIP_UNKNOWN_SELLER_LEVEL:
                return None
            if level is not None and level > config.MAX_SELLER_LEVEL:
                return None
            if profile_nfts is None or profile_nfts > config.MAX_PROFILE_NFTS:
                return None

            name = " ".join(x for x in (first_name, last_name) if x)
            category = "female" if self._looks_female(username, first_name, last_name) else "male"
            return {
                "id": str(owner_id),
                "username": username,
                "name": name or str(owner_id),
                "category": category,
                "profile_nfts": profile_nfts,
            }
        return None

    async def _fetch_pages(self, base_id: int):
        offset = ""
        for page in range(config.MAX_PAGES_PER_GIFT):
            async with self.sem:
                if config.REQUEST_DELAY:
                    await asyncio.sleep(config.REQUEST_DELAY)
                result = await self._call(
                    payments.GetResaleStarGiftsRequest(
                        sort_by_price=True,
                        sort_by_num=False,
                        for_craft=False,
                        # Do NOT use stars_only: we need TON resale listings.
                        stars_only=False,
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
            next_offset = getattr(result, "next_offset", None)
            if not next_offset or next_offset == offset:
                return
            offset = next_offset

    def _make_data(self, base_id, gift, price, seller):
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
            "seller_id": seller["id"],
            "seller_username": seller["username"],
            "seller_name": seller["name"],
            "seller_category": seller["category"],
            "profile_nfts": seller["profile_nfts"],
            **attrs,
            "link": f"https://t.me/nft/{slug}" if slug else "",
            "seller_link": f"https://t.me/{seller['username']}" if seller["username"] else "",
        }

    async def _process_type(self, base_id: int, alert_new: bool):
        try:
            async for result, gifts in self._fetch_pages(base_id):
                for gift in gifts:
                    price = self._ton_price(gift)
                    if price is None or price >= config.MAX_TON_PRICE:
                        continue
                    if exists(self.conn, int(gift.id)):
                        continue

                    seller = await self._seller(gift, result)
                    if seller is None:
                        continue

                    data = self._make_data(base_id, gift, price, seller)

                    if not alert_new:
                        upsert_seen(self.conn, data, alerted=False)
                        continue

                    # One seller may appear in many gifts. Claim the seller only
                    # after a successful send, so a failed send can be retried.
                    async with self._seller_send_lock:
                        if seller_seen(self.conn, seller["id"]):
                            upsert_seen(self.conn, data, alerted=False)
                            continue
                        text = format_listing(data)
                        thread_id = (
                            config.FEMALE_THREAD_ID
                            if seller["category"] == "female"
                            else config.MALE_THREAD_ID
                        )
                        await send_alert(self.client, text, button_rows(data), thread_id=thread_id)
                        mark_seller_seen(self.conn, seller["id"], seller["username"], seller["name"])
                        upsert_seen(self.conn, data, alerted=True)
                        log.info(
                            "ALERT %s #%s — %.3f TON — seller=%s — %s",
                            data["title"], data["number"], price, seller["id"], seller["category"],
                        )
        except errors.FloodWaitError as e:
            log.warning("FloodWait %ss on gift type %s", e.seconds, base_id)
            await asyncio.sleep(int(e.seconds) + 3)
        except Exception:
            log.exception("Unexpected error on gift type %s", base_id)

    async def scan_once(self, alert_new: bool):
        await self.refresh_gift_types()
        ids = list(self.base_gifts)
        log.info("Scanning %d gift types for TON gifts below %s TON...", len(ids), config.MAX_TON_PRICE)
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
                    completed = len(ids) - queue.qsize()
                    if completed == len(ids) or completed % 10 == 0:
                        log.info("Scan progress: %d/%d gift types", completed, len(ids))

        workers = [asyncio.create_task(worker()) for _ in range(min(config.CONCURRENCY, len(ids)))]
        await queue.join()
        await asyncio.gather(*workers, return_exceptions=True)

    async def run(self):
        log.info(
            "Started. TON price < %s, max profile NFTs=%d, male topic=%d, female topic=%d",
            config.MAX_TON_PRICE, config.MAX_PROFILE_NFTS, config.MALE_THREAD_ID, config.FEMALE_THREAD_ID,
        )
        await self.scan_once(alert_new=config.ALERT_EXISTING_ON_START)
        log.info("Initial baseline complete; monitoring new listings")

        while True:
            started = asyncio.get_running_loop().time()
            await self.scan_once(alert_new=True)
            elapsed = asyncio.get_running_loop().time() - started
            await asyncio.sleep(max(1.0, config.SCAN_INTERVAL - elapsed))
